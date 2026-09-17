from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Create a contact segment for every existing course."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['slide.channel'].with_context(active_test=False).search([])._diligence_ensure_contact_segment()
