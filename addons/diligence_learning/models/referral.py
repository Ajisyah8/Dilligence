from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class DiligenceReferral(models.Model):
    _name = 'diligence.referral'
    _description = 'Diligence Affiliate Referral'
    _order = 'create_date desc'

    name = fields.Char('Reference', required=True, default='New', copy=False)
    affiliate_id = fields.Many2one('res.partner', 'Affiliate', required=True, index=True)
    student_id = fields.Many2one('res.partner', 'Student', required=True, index=True)
    sale_order_id = fields.Many2one('sale.order', 'Sale Order', required=True, ondelete='restrict', index=True)
    invoice_id = fields.Many2one('account.move', 'Paid Invoice', copy=False)
    program_id = fields.Many2one('product.template', 'Program / Package')
    referral_code = fields.Char('Referral Code', required=True, index=True)
    registration_date = fields.Datetime('Registration Date', default=fields.Datetime.now, required=True)
    payment_date = fields.Datetime('Payment Date', copy=False)
    waiting_until = fields.Date('Waiting Until', copy=False)
    approved_date = fields.Datetime('Approved Date', copy=False)
    ready_to_pay_date = fields.Datetime('Ready to Pay Date', copy=False)
    paid_date = fields.Datetime('Paid Date', copy=False)
    payment_amount = fields.Monetary('Payment Received', currency_field='currency_id', copy=False)
    net_payment = fields.Monetary('Net Payment', currency_field='currency_id', copy=False)
    cashback_type = fields.Selection([
        ('percent', 'Percentage'),
        ('fixed', 'Fixed Amount'),
    ], default='percent', required=True)
    cashback_rate = fields.Float('Cashback Rate (%)', copy=False)
    cashback_fixed = fields.Monetary('Fixed Cashback', currency_field='currency_id', copy=False)
    cashback_amount = fields.Monetary('Cashback Amount', currency_field='currency_id', copy=False)
    status = fields.Selection([
        ('draft', 'Draft'),
        ('pending_payment', 'Pending Payment'),
        ('eligible', 'Eligible'),
        ('waiting_period', 'Waiting Period'),
        ('approved', 'Approved'),
        ('ready_to_pay', 'Ready to Pay'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
        ('reversed', 'Reversed'),
    ], default='draft', required=True, index=True)
    payout_reference = fields.Char('Payout Transfer Reference', copy=False)
    notes = fields.Text('Notes', copy=False)
    settlement_id = fields.Many2one('diligence.referral.settlement', 'Settlement Batch', copy=False)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    currency_id = fields.Many2one(related='company_id.currency_id', store=True)

    _sql_constraints = [
        ('sale_order_unique', 'unique(sale_order_id)', 'Only one referral attribution is allowed per order.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('diligence.referral') or 'REF'
        return super().create(vals_list)

    def _compute_cashback(self):
        for referral in self:
            if referral.cashback_type == 'fixed':
                referral.cashback_amount = referral.cashback_fixed
            else:
                referral.cashback_amount = referral.net_payment * referral.cashback_rate / 100

    def _find_paid_invoice(self):
        self.ensure_one()
        invoices = self.sale_order_id.invoice_ids.filtered(
            lambda invoice: invoice.state == 'posted' and invoice.move_type in ('out_invoice', 'out_receipt')
        )
        paid = invoices.filtered(lambda invoice: invoice.payment_state == 'paid')
        return paid[:1], sum(paid.mapped('amount_total'))

    @api.model
    def _cron_refresh_payments(self):
        referrals = self.search([('status', 'not in', ('cancelled', 'reversed'))])
        referrals.action_refresh_payment()

    def action_refresh_payment(self):
        for referral in self:
            refunds = referral.sale_order_id.invoice_ids.filtered(
                lambda invoice: invoice.state == 'posted' and invoice.move_type == 'out_refund'
            )
            if refunds and referral.status not in ('cancelled', 'reversed'):
                referral.write({'status': 'reversed', 'notes': _('Reversed because a refund invoice was posted.')})
                continue
            if referral.status in ('cancelled', 'reversed', 'paid'):
                continue
            invoice, amount = referral._find_paid_invoice()
            if not invoice:
                referral.write({'status': 'pending_payment'})
                continue
            waiting_days = referral.affiliate_id.diligence_affiliate_waiting_days or 0
            payment_date = fields.Datetime.now()
            waiting_until = (payment_date + timedelta(days=waiting_days)).date()
            referral.write({
                'invoice_id': invoice.id,
                'payment_amount': amount,
                'net_payment': amount,
                'payment_date': payment_date,
                'waiting_until': waiting_until,
                'status': 'waiting_period' if waiting_days else 'eligible',
            })
            referral._compute_cashback()
        return True

    def action_approve(self):
        for referral in self:
            if referral.status not in ('eligible', 'waiting_period'):
                raise UserError(_('Only eligible referrals can be approved.'))
            if referral.waiting_until and referral.waiting_until > fields.Date.today():
                raise UserError(_('The waiting period has not ended yet.'))
            referral.write({'status': 'approved', 'approved_date': fields.Datetime.now()})

    def action_ready_to_pay(self):
        self.write({'status': 'ready_to_pay', 'ready_to_pay_date': fields.Datetime.now()})

    def action_mark_paid(self):
        for referral in self:
            if referral.status not in ('approved', 'ready_to_pay'):
                raise UserError(_('Referral must be approved before it can be paid.'))
            referral.write({'status': 'paid', 'paid_date': fields.Datetime.now()})

    def action_cancel(self):
        self.write({'status': 'cancelled'})

    def action_reverse(self):
        self.write({'status': 'reversed'})


class DiligenceReferralSettlement(models.Model):
    _name = 'diligence.referral.settlement'
    _description = 'Diligence Affiliate Settlement'
    _order = 'period_end desc, id desc'

    name = fields.Char('Settlement Reference', required=True, default='New', copy=False)
    affiliate_id = fields.Many2one('res.partner', 'Affiliate', required=True, index=True)
    period_start = fields.Date('Period Start', required=True)
    period_end = fields.Date('Period End', required=True)
    referral_ids = fields.One2many('diligence.referral', 'settlement_id', string='Referrals')
    total_payment = fields.Monetary('Total Student Payments', compute='_compute_totals', currency_field='currency_id')
    total_cashback = fields.Monetary('Total Cashback', compute='_compute_totals', currency_field='currency_id')
    referral_count = fields.Integer('Referral Count', compute='_compute_totals')
    status = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
    ], default='draft', required=True)
    payout_reference = fields.Char('Payout Transfer Reference', copy=False)
    currency_id = fields.Many2one(related='affiliate_id.company_id.currency_id', store=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('diligence.referral.settlement') or 'SET'
        return super().create(vals_list)

    @api.depends('referral_ids', 'referral_ids.net_payment', 'referral_ids.cashback_amount')
    def _compute_totals(self):
        for settlement in self:
            settlement.total_payment = sum(settlement.referral_ids.mapped('net_payment'))
            settlement.total_cashback = sum(settlement.referral_ids.mapped('cashback_amount'))
            settlement.referral_count = len(settlement.referral_ids)

    def action_load_eligible(self):
        for settlement in self:
            referrals = self.env['diligence.referral'].search([
                ('affiliate_id', '=', settlement.affiliate_id.id),
                ('status', 'in', ('approved', 'ready_to_pay')),
                ('payment_date', '>=', settlement.period_start),
                ('payment_date', '<=', settlement.period_end),
                ('settlement_id', '=', False),
            ])
            referrals.write({'settlement_id': settlement.id})

    def action_approve(self):
        for settlement in self:
            if not settlement.referral_ids:
                raise UserError(_('Load eligible referrals before approving the settlement.'))
            settlement.referral_ids.filtered(lambda referral: referral.status == 'approved').action_ready_to_pay()
            settlement.status = 'approved'

    def action_mark_paid(self):
        for settlement in self:
            settlement.referral_ids.filtered(lambda referral: referral.status in ('approved', 'ready_to_pay')).action_mark_paid()
            settlement.status = 'paid'

    def action_cancel(self):
        for settlement in self:
            settlement.referral_ids.write({'settlement_id': False})
            settlement.status = 'cancelled'
