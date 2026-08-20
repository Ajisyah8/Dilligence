from odoo import SUPERUSER_ID, api


REMOVED_COURSE_NAMES = (
    'Business Mandarin',
    'Travel Mandarin',
    'HSK Preparation',
)

REMOVED_XMLIDS = (
    'course_diligence_business_mandarin',
    'course_diligence_travel_mandarin',
    'course_diligence_hsk_preparation',
    'section_business_mandarin_foundations',
    'section_business_mandarin_workplace',
    'section_business_mandarin_presentations',
    'section_travel_mandarin_foundations',
    'section_travel_mandarin_transport',
    'section_travel_mandarin_daily',
    'section_hsk_foundations',
    'section_hsk_listening_reading',
    'section_hsk_mock_tests',
)


def migrate(cr, version):
    """Permanently remove discontinued seeded courses and their content."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    channels = env['slide.channel'].with_context(active_test=False).search([
        ('name', 'in', REMOVED_COURSE_NAMES),
    ])
    if channels:
        channels.unlink()

    env['ir.model.data'].search([
        ('module', '=', 'diligence_learning'),
        ('name', 'in', REMOVED_XMLIDS),
    ]).unlink()
