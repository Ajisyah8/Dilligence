from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Restore all supported translations for the paired Events menu links."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    # Resolve the websites independently: their domain strings can contain
    # several aliases, so a single ilike conjunction would never match.
    websites = env['website'].sudo().search([
        '|', ('domain', 'ilike', 'diligenceenglish.com'),
        ('domain', 'ilike', 'diligencekursusbahasa.com'),
    ])
    if not websites:
        return
    menus = env['website.menu'].sudo().search([
        ('website_id', 'in', websites.ids), ('url', '=', '/event'),
    ])
    sync_context = {'diligence_website_syncing': True, 'no_cow': True}
    for menu in menus:
        menu.with_context(sync_context, lang='en_US').write({'name': 'Events'})
        menu.with_context(sync_context, lang='id_ID').write({'name': 'Acara'})
        menu.with_context(sync_context, lang='zh_CN').write({'name': '活动'})
