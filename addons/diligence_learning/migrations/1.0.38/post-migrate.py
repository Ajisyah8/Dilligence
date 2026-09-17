from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Add course segments to existing learners with valid active access."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['slide.channel'].with_context(active_test=False).search([])._diligence_sync_active_member_segments()
