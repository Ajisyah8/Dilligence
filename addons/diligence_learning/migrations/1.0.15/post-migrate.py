from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    snippet = env.ref('diligence_learning.diligence_package_snippet_filter', raise_if_not_found=False)
    if snippet:
        snippet.write({'field_names': 'name,description_sale,image_512,list_price,website_url'})
