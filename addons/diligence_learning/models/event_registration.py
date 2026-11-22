from odoo import api, fields, models


class EventRegistration(models.Model):
    _inherit = 'event.registration'

    diligence_participant_type = fields.Selection(
        [('student', 'Student'), ('general', 'General Public')],
        string='Participant Type', default='general', required=True, index=True,
        help='Automatically follows the attendee contact segment: Student means Student; any other segment means General Public. You can override it for this registration.',
    )

    @api.model
    def _diligence_is_student(self, partner):
        if not partner:
            return False
        partner = partner.sudo()
        return (
            partner.diligence_contact_segment == 'student'
            or partner.diligence_contact_segment_id.code == 'student'
            or 'student' in partner.diligence_contact_segment_ids.mapped('code')
        )

    @api.model_create_multi
    def create(self, vals_list):
        registrations = super().create(vals_list)
        for registration, vals in zip(registrations, vals_list):
            if not vals.get('diligence_participant_type'):
                registration.diligence_participant_type = (
                    'student' if self._diligence_is_student(registration.partner_id) else 'general'
                )
        return registrations

    def _update_mail_schedulers(self):
        """Defer attendee mail while Odoo is importing records.

        Odoo's base importer wraps dry-run/test imports in a savepoint. The
        standard after-subscription event scheduler commits its cursor while
        sending mail, which destroys that savepoint and can persist a test
        import. Queue the scheduler instead; it will process registrations
        after the import transaction commits (and the trigger rolls back for a
        dry run).
        """
        if not self.env.context.get('import_file'):
            return super()._update_mail_schedulers()

        open_registrations = self.filtered(lambda registration: registration.state == 'open')
        if not open_registrations:
            return
        schedulers = self.env['event.mail'].sudo().search([
            ('event_id', 'in', open_registrations.event_id.ids),
            ('interval_type', '=', 'after_sub'),
        ])
        if schedulers:
            cron = self.env.ref('event.event_mail_scheduler', raise_if_not_found=False)
            if cron:
                cron._trigger()
        return True
