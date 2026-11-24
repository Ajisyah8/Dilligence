from odoo import SUPERUSER_ID, api, fields


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Segment = env['diligence.contact.segment'].sudo()
    active_student = Segment.search([('code', '=', 'active_student')], limit=1)
    if not active_student:
        return
    teacher_segment = Segment.search([('code', '=', 'teacher')], limit=1)
    if teacher_segment:
        teacher_segment.write({'name': 'Teachers', 'sequence': 12})

    memberships = env['slide.channel.partner'].sudo().search([
        ('diligence_package_id', '!=', False),
        '|', ('diligence_access_expires_at', '=', False),
        ('diligence_access_expires_at', '>=', fields.Datetime.now()),
    ])
    partners = memberships.mapped('partner_id.commercial_partner_id')
    for partner in partners:
        partner._diligence_set_primary_contact_segment('active_student')
