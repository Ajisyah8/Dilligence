from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SurveyInvite(models.TransientModel):
    _inherit = 'survey.invite'

    diligence_segment_id = fields.Many2one(
        'diligence.contact.segment',
        string='Contact Segment',
        domain=[('active', '=', True)],
        help='Load contacts from this Diligence audience before sending the survey.',
    )
    diligence_recipient_count = fields.Integer(
        string='Matching Contacts',
        compute='_compute_diligence_recipient_count',
    )

    @api.depends('diligence_segment_id')
    def _compute_diligence_recipient_count(self):
        for wizard in self:
            wizard.diligence_recipient_count = wizard._diligence_segment_partners_count()

    def _diligence_segment_domain(self):
        self.ensure_one()
        if not self.diligence_segment_id:
            raise UserError(_('Select a contact segment first.'))
        return [
            '|',
            ('diligence_contact_segment_id', '=', self.diligence_segment_id.id),
            ('diligence_contact_segment', '=', self.diligence_segment_id.code),
            ('active', '=', True),
            ('email', '!=', False),
        ]

    def _diligence_segment_partners(self):
        self.ensure_one()
        return self.env['res.partner'].search(
            self._diligence_segment_domain(), order='name, id'
        )

    def _diligence_segment_partners_count(self):
        return len(self._diligence_segment_partners()) if self.diligence_segment_id else 0

    def action_load_diligence_segment(self):
        self.ensure_one()
        partners = self._diligence_segment_partners()
        self.partner_ids = [(6, 0, partners.ids)]
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }
