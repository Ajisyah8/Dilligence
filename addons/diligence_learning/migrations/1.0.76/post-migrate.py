from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    parameters = env['ir.config_parameter'].sudo()

    # Seed only confirmed contact numbers, and never overwrite a value an
    # administrator has already configured. Payment remains unset until its
    # dedicated number is provided.
    confirmed_numbers = {
        'diligence.contact_hub.course_phone': '6285935113213',
        'diligence.contact_hub.video_phone': '6282164629873',
        'diligence.contact_hub.study_phone': '6282181362834',
    }
    for key, number in confirmed_numbers.items():
        if not parameters.get_param(key):
            parameters.set_param(key, number)

    website = env['website'].sudo().search([
        ('domain', 'ilike', 'diligencekursusbahasa.com'),
    ], limit=1)
    page = env.ref('diligence_learning.page_diligence_contact_link_hub', raise_if_not_found=False)
    if website and page:
        page.sudo().write({'website_id': website.id})
