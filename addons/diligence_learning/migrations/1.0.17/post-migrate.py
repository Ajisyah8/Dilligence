from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    primary = env['blog.blog'].search([('name', '=', 'Our blog')], limit=1)
    if primary:
        primary.write({'name': 'Diligence Insights'})
    secondary = env['blog.blog'].search([('name', '=', 'News')], limit=1)
    if secondary and secondary != primary:
        secondary.write({'active': False})
