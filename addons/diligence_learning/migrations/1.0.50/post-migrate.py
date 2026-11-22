from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Classify existing event registrations using each contact's Student segment."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    student_partners = env['res.partner'].with_context(active_test=False).search([
        '|', '|',
        ('diligence_contact_segment', '=', 'student'),
        ('diligence_contact_segment_id.code', '=', 'student'),
        ('diligence_contact_segment_ids.code', '=', 'student'),
    ])
    if student_partners:
        env['event.registration'].with_context(active_test=False).search([
            ('partner_id', 'in', student_partners.ids),
        ]).write({'diligence_participant_type': 'student'})
