from odoo import api, fields, models
from odoo.exceptions import UserError


class SlideChannelPartner(models.Model):
    _inherit = 'slide.channel.partner'

    diligence_package_id = fields.Many2one('product.template', 'Access Package', copy=False)
    diligence_access_expires_at = fields.Datetime('Access Expires At', copy=False)
    diligence_level = fields.Selection([
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
    ], string='Learning Level', compute='_compute_diligence_achievement', store=True)
    diligence_certificate_eligible = fields.Boolean(
        'Certificate Eligible', compute='_compute_diligence_achievement', store=True,
    )
    diligence_certificate_issued = fields.Boolean('Certificate Issued', copy=False)
    diligence_certificate_code = fields.Char('Certificate Code', copy=False)

    @api.depends('completion')
    def _compute_diligence_achievement(self):
        for membership in self:
            if membership.completion >= 67:
                membership.diligence_level = 'advanced'
            elif membership.completion >= 34:
                membership.diligence_level = 'intermediate'
            else:
                membership.diligence_level = 'beginner'
            membership.diligence_certificate_eligible = membership.completion >= 100

    def _diligence_access_is_valid(self):
        self.ensure_one()
        return not self.diligence_access_expires_at or self.diligence_access_expires_at >= fields.Datetime.now()

    def action_issue_diligence_certificate(self):
        for membership in self:
            if not membership.diligence_certificate_eligible:
                raise UserError('The learner must complete 100% of the course before a certificate can be issued.')
            if not membership.diligence_certificate_code:
                membership.diligence_certificate_code = (
                    f'DIL-{membership.channel_id.id:04d}-{membership.partner_id.id:06d}'
                )
            membership.diligence_certificate_issued = True

    def action_print_diligence_certificate(self):
        for membership in self:
            if not membership.diligence_certificate_issued:
                raise UserError('Issue the certificate before printing it.')
        return self.env.ref('diligence_learning.action_report_diligence_certificate').report_action(self)
