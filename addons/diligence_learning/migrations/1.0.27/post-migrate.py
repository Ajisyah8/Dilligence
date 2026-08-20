from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Expose the automatic score on attempts waiting for manual grading."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    attempts = env['diligence.quiz.attempt'].search([
        ('state', '=', 'pending_review'),
    ])
    attempts._compute_final_score()
