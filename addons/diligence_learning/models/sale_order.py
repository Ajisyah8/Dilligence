from datetime import timedelta

from odoo import Command, _, fields, models
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    diligence_referral_code = fields.Char('Referral Code', copy=False)
    diligence_referrer_id = fields.Many2one('res.partner', 'Referrer', copy=False, readonly=True)
    diligence_referral_id = fields.Many2one('diligence.referral', 'Referral Attribution', copy=False, readonly=True)
    diligence_commission_amount = fields.Monetary('Manual Affiliate Cashback', copy=False)
    diligence_commission_status = fields.Selection([
        ('none', 'Not Applicable'),
        ('eligible', 'Eligible'),
        ('paid', 'Paid Manually'),
    ], default='none', copy=False)
    diligence_consultation_status = fields.Selection([
        ('not_applicable', 'Not Applicable'),
        ('new', 'New - Contact Learner'),
        ('scheduled', 'Coaching Scheduled'),
        ('ongoing', 'Coaching Ongoing'),
        ('completed', 'Completed'),
    ], default='not_applicable', copy=False)
    diligence_coach_id = fields.Many2one('res.users', 'Coach', copy=False)
    diligence_next_coaching_date = fields.Datetime('Next Coaching / Q&A', copy=False)
    diligence_coaching_link = fields.Char('Coaching / Q&A Link', copy=False)
    diligence_coaching_note = fields.Text('Coach Progress Note', copy=False)

    def _diligence_package_lines(self):
        return self.order_line.filtered(lambda line: line.product_template_id._diligence_is_package())

    def _diligence_apply_referral(self):
        for order in self:
            code = (order.diligence_referral_code or '').strip().upper()
            if not code or order.diligence_referrer_id:
                continue
            package = order._diligence_package_lines()[:1].product_template_id
            referrer = self.env['res.partner'].search([
                ('diligence_referral_code', '=', code),
                ('diligence_is_affiliate', '=', True),
            ], limit=1)
            today = fields.Date.today()
            active_dates = referrer and (
                (not referrer.diligence_affiliate_start_date or referrer.diligence_affiliate_start_date <= today)
                and (not referrer.diligence_affiliate_end_date or referrer.diligence_affiliate_end_date >= today)
            )
            allowed_program = not referrer.diligence_affiliate_program_ids or package in referrer.diligence_affiliate_program_ids
            previous_referral = self.env['diligence.referral'].search([
                ('student_id', 'child_of', order.partner_id.commercial_partner_id.id),
                ('status', 'not in', ('cancelled', 'reversed')),
            ], limit=1)
            if referrer and active_dates and allowed_program and not previous_referral and referrer.commercial_partner_id != order.partner_id.commercial_partner_id:
                values = {
                    'diligence_referrer_id': referrer.id,
                    'diligence_commission_status': 'eligible',
                }
                order.write(values)
                referral = self.env['diligence.referral'].create({
                    'affiliate_id': referrer.id,
                    'student_id': order.partner_id.id,
                    'sale_order_id': order.id,
                    'program_id': package.id if package else False,
                    'referral_code': code,
                    'cashback_type': referrer.diligence_cashback_type,
                    'cashback_rate': referrer.diligence_cashback_rate,
                    'cashback_fixed': referrer.diligence_cashback_fixed,
                    'status': 'pending_payment',
                })
                order.diligence_referral_id = referral.id

    def _diligence_grant_package_access(self):
        community_group = self.env.ref('diligence_learning.group_diligence_community_member')
        for order in self:
            package_lines = order._diligence_package_lines()
            if not package_lines:
                continue
            package_products = package_lines.mapped('product_template_id')
            courses = package_products.mapped('diligence_course_ids')
            courses.sudo()._action_add_members(order.partner_id)
            for package in package_products:
                membership = self.env['slide.channel.partner'].search([
                    ('channel_id', 'in', package.diligence_course_ids.ids),
                    ('partner_id', '=', order.partner_id.id),
                ])
                expiration = False
                if package.diligence_access_duration_days:
                    base_date = order.date_order or fields.Datetime.now()
                    expiration = base_date + timedelta(days=package.diligence_access_duration_days)
                membership.write({
                    'diligence_package_id': package.id,
                    'diligence_access_expires_at': expiration,
                })

            if package_products.filtered('diligence_forum_access'):
                portal_users = order.partner_id.user_ids.filtered(lambda user: user.active and user.share)
                portal_users.write({'group_ids': [Command.link(community_group.id)]})

            if package_products.filtered('diligence_consultation'):
                order.diligence_consultation_status = 'new'
                order.activity_schedule(
                    'mail.mail_activity_data_todo',
                    summary=_('Contact Consultation learner'),
                    note=_('Arrange coaching, learning-progress review, and live Q&A via WhatsApp or Zoom.'),
                )

    def _action_confirm(self):
        result = super()._action_confirm()
        self._diligence_apply_referral()
        self._diligence_grant_package_access()
        return result

    def action_mark_diligence_cashback_paid(self):
        self.ensure_one()
        if not self.diligence_referrer_id:
            raise ValidationError(_('This order has no valid referral.'))
        if self.diligence_referral_id:
            self.diligence_referral_id.action_mark_paid()
        self.diligence_commission_status = 'paid'

    def action_refresh_diligence_referral_payment(self):
        self.ensure_one()
        if not self.diligence_referral_id:
            raise ValidationError(_('This order has no referral attribution.'))
        self.diligence_referral_id.action_refresh_payment()
        self.diligence_commission_amount = self.diligence_referral_id.cashback_amount
