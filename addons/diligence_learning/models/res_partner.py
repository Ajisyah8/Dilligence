from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    diligence_contact_segment = fields.Selection([
        ('student', 'Student'),
        ('customer', 'Customer'),
        ('newsletter', 'Newsletter Subscriber'),
        ('referral_non_student', 'Referral - Non Student'),
        ('affiliate', 'Affiliate / Referrer'),
        ('other', 'Other'),
    ], string='Diligence Contact Segment', default='other', index=True, copy=False)
    diligence_contact_segment_id = fields.Many2one('diligence.contact.segment', string='Contact Segment', ondelete='restrict', index=True)

    diligence_referral_code = fields.Char('Referral Code', copy=False, index=True)
    diligence_referral_link = fields.Char('Affiliate Link', compute='_compute_diligence_referral_link')
    diligence_is_affiliate = fields.Boolean('Active Affiliate', default=False, copy=False)
    diligence_affiliate_type = fields.Selection([
        ('student', 'Student'),
        ('alumni', 'Alumni'),
        ('parent', 'Parent'),
        ('tutor', 'Tutor'),
        ('agent', 'Agent'),
        ('school', 'School'),
    ], string='Affiliate Type', copy=False)
    diligence_affiliate_type_id = fields.Many2one('diligence.affiliate.type', string='Affiliate Type', ondelete='restrict', copy=False)
    diligence_affiliate_bank_name = fields.Char('Bank Name', copy=False)
    diligence_affiliate_bank_account = fields.Char('Bank Account Number', copy=False)
    diligence_affiliate_bank_holder = fields.Char('Bank Account Holder', copy=False)
    diligence_cashback_type = fields.Selection([
        ('percent', 'Percentage'),
        ('fixed', 'Fixed Amount'),
    ], string='Cashback Type', default='percent', copy=False)
    diligence_cashback_type_id = fields.Many2one('diligence.cashback.type', string='Cashback Type', ondelete='restrict', copy=False)

    def _diligence_cashback_type_code(self):
        self.ensure_one()
        return self.diligence_cashback_type_id.code if self.diligence_cashback_type_id else self.diligence_cashback_type
    diligence_cashback_rate = fields.Float('Cashback Rate (%)', copy=False)
    diligence_cashback_fixed = fields.Monetary('Fixed Cashback', copy=False)
    diligence_affiliate_start_date = fields.Date('Agreement Start Date', copy=False)
    diligence_affiliate_end_date = fields.Date('Agreement End Date', copy=False)
    diligence_affiliate_min_payout = fields.Monetary('Minimum Payout', copy=False)
    diligence_affiliate_waiting_days = fields.Integer('Waiting Period (Days)', default=14, copy=False)
    diligence_affiliate_notes = fields.Text('Affiliate Notes', copy=False)
    diligence_affiliate_program_ids = fields.Many2many(
        'product.template',
        'diligence_affiliate_program_rel',
        'partner_id', 'product_tmpl_id',
        string='Allowed Referral Programs',
        copy=False,
    )
    diligence_forum_access = fields.Boolean(
        'Diligence Forum Access',
        compute='_compute_diligence_forum_access',
        help='Granted when the partner has a confirmed Community or Consultation package.',
    )
    diligence_referral_count = fields.Integer(
        'Total Referrals', compute='_compute_diligence_referral_summary',
    )
    diligence_valid_referral_count = fields.Integer(
        'Valid Referrals', compute='_compute_diligence_referral_summary',
    )
    diligence_cashback_total = fields.Monetary(
        'Total Cashback', compute='_compute_diligence_referral_summary',
    )
    diligence_cashback_outstanding = fields.Monetary(
        'Outstanding Cashback', compute='_compute_diligence_referral_summary',
    )

    _diligence_referral_code_uniq = models.Constraint(
        'unique(diligence_referral_code)',
        'Referral codes must be unique.',
    )
    diligence_newsletter_opt_in = fields.Boolean(
        'Receive Diligence Newsletter',
        default=False,
        copy=False,
        help='The student explicitly agreed to receive the Diligence Academy email sequence.',
    )
    diligence_newsletter_opt_in_date = fields.Datetime(
        'Newsletter Consent Date', copy=False, readonly=True,
    )

    @api.depends('diligence_referral_code')
    def _compute_diligence_referral_link(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '').rstrip('/')
        for partner in self:
            partner.diligence_referral_link = (
                f'{base_url}/diligence/referral/{partner.diligence_referral_code}'
                if base_url and partner.diligence_referral_code else False
            )

    def _compute_diligence_forum_access(self):
        orders = self.env['sale.order'].search([
            ('partner_id', 'child_of', self.commercial_partner_id.ids),
            ('state', 'in', ('sale', 'done')),
            ('order_line.product_template_id.diligence_forum_access', '=', True),
        ])
        entitled_partner_ids = set(orders.mapped('partner_id.commercial_partner_id').ids)
        for partner in self:
            partner.diligence_forum_access = partner.commercial_partner_id.id in entitled_partner_ids

    def _compute_diligence_referral_summary(self):
        Referral = self.env['diligence.referral'].sudo()
        for partner in self:
            referrals = Referral.search([('affiliate_id', '=', partner.commercial_partner_id.id)])
            valid = referrals.filtered(lambda referral: referral.status not in ('draft', 'pending_payment', 'cancelled', 'reversed'))
            total = sum(valid.mapped('cashback_amount'))
            outstanding = sum(valid.filtered(lambda referral: referral.status != 'paid').mapped('cashback_amount'))
            partner.diligence_referral_count = len(referrals)
            partner.diligence_valid_referral_count = len(valid)
            partner.diligence_cashback_total = total
            partner.diligence_cashback_outstanding = outstanding

    @api.model_create_multi
    def create(self, vals_list):
        partners = super().create(vals_list)
        for partner in partners.filtered(lambda record: not record.diligence_referral_code):
            partner.diligence_referral_code = f'DIL{partner.id:05d}'
        opted_in = partners.filtered(lambda record: record.diligence_newsletter_opt_in)
        if opted_in:
            opted_in.write({'diligence_newsletter_opt_in_date': fields.Datetime.now()})
            opted_in._sync_diligence_newsletter_subscription()
        return partners

    def write(self, vals):
        if vals.get('diligence_newsletter_opt_in'):
            vals = dict(vals, diligence_newsletter_opt_in_date=fields.Datetime.now())
        elif vals.get('diligence_newsletter_opt_in') is False:
            vals = dict(vals, diligence_newsletter_opt_in_date=False)
        result = super().write(vals)
        if 'diligence_newsletter_opt_in' in vals:
            self._sync_diligence_newsletter_subscription()
        return result

    def _sync_diligence_newsletter_subscription(self):
        newsletter = self.env['mailing.list'].sudo().search([
            ('name', '=', 'Diligence Academy Newsletter'),
        ], limit=1)
        if newsletter:
            for partner in self.filtered(lambda record: record.email):
                contact = self.env['mailing.contact'].sudo().search([
                    ('email_normalized', '=', partner.email_normalized),
                ], limit=1)
                if not contact:
                    contact = self.env['mailing.contact'].sudo().create({
                        'name': partner.name,
                        'email': partner.email,
                        'list_ids': [(4, newsletter.id)],
                    })
                newsletter._update_subscription_from_email(
                    partner.email,
                    opt_out=not partner.diligence_newsletter_opt_in,
                    force_message=False,
                )

    def _diligence_ensure_referral_code(self):
        for partner in self:
            if not partner.diligence_referral_code:
                partner.diligence_referral_code = f'DIL{partner.id:05d}'
        return self
