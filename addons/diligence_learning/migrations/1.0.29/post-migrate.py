from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Make every existing Diligence quiz repeatable without an attempt limit."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    quizzes = env['slide.slide'].search([
        '|',
        ('slide_category', '=', 'quiz'),
        ('question_ids', '!=', False),
    ])
    quizzes.write({'quiz_max_attempts': 0})
