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
    diligence_segment_ids = fields.Many2many(
        'diligence.contact.segment',
        string='Contact Segments',
        domain=[('active', '=', True)],
        help='Load contacts belonging to any of the selected Diligence audiences.',
    )
    diligence_recipient_count = fields.Integer(
        string='Matching Contacts',
        compute='_compute_diligence_recipient_count',
    )

    @api.depends('diligence_segment_id', 'diligence_segment_ids')
    def _compute_diligence_recipient_count(self):
        for wizard in self:
            wizard.diligence_recipient_count = wizard._diligence_segment_partners_count()

    def _diligence_segment_domain(self):
        self.ensure_one()
        segments = self.diligence_segment_ids or self.diligence_segment_id
        if not segments:
            raise UserError(_('Select a contact segment first.'))
        segment_ids = segments.ids
        codes = segments.mapped('code')
        return [
            '&', '&',
            ('active', '=', True),
            ('email', '!=', False),
            '|', '|',
            ('diligence_contact_segment_ids', 'in', segment_ids),
            ('diligence_contact_segment_id', 'in', segment_ids),
            ('diligence_contact_segment', 'in', codes),
        ]

    def _diligence_segment_partners(self):
        self.ensure_one()
        return self.env['res.partner'].search(
            self._diligence_segment_domain(), order='name, id'
        )

    def _diligence_segment_partners_count(self):
        return len(self._diligence_segment_partners()) if (self.diligence_segment_ids or self.diligence_segment_id) else 0

    @api.onchange('diligence_segment_ids', 'diligence_segment_id')
    def _onchange_diligence_segments(self):
        for wizard in self:
            if wizard.diligence_segment_ids or wizard.diligence_segment_id:
                wizard.partner_ids = [(6, 0, wizard._diligence_segment_partners().ids)]

    def action_load_diligence_segment(self):
        self.ensure_one()
        partners = self._diligence_segment_partners()
        self.write({'partner_ids': [(6, 0, partners.ids)]})
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    def action_invite(self):
        """Keep a selected Diligence audience as the authoritative recipient set."""
        self.ensure_one()
        if self.diligence_segment_ids or self.diligence_segment_id:
            if self.emails and self.emails.strip():
                raise UserError(_(
                    'Clear Additional emails when sending to a Diligence Contact Segment. '
                    'Only contacts in the selected segment(s) may receive this survey.'
                ))
            partners = self._diligence_segment_partners()
            self.write({'partner_ids': [(6, 0, partners.ids)]})
        return super().action_invite()
