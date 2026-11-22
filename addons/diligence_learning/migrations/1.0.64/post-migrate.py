from odoo import SUPERUSER_ID, api


ENGLISH_LABELS_BY_URL = {
    '/': 'Home',
    '/about-us': 'About Us',
    '/blog': 'Blog',
    '/contactus': 'Contact Us',
    '/event': 'Events',
    '/our-services': 'Services',
    '/pricing': 'Pricing',
    '/blog/2': 'News',
    '/slides?all_courses=1': 'All Courses',
    '/slides?search=English': 'English',
    '/slides?search=Mandarin': 'Mandarin',
}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    english_site = env['website'].sudo().search([
        ('domain', 'ilike', 'diligenceenglish.com'),
    ], limit=1)
    if not english_site:
        return

    sync_context = {'diligence_website_syncing': True, 'no_cow': True}
    menus = env['website.menu'].sudo().search([
        ('website_id', '=', english_site.id),
    ])
    root_labels = {
        'Menu Utama': 'Main Menu',
        'Program': 'Programs',
        'Tentang Kami': 'About Us',
    }
    for menu in menus:
        label = ENGLISH_LABELS_BY_URL.get(menu.url)
        if menu.url == '#':
            label = root_labels.get(menu.with_context(lang='id_ID').name, label)
        if label:
            menu.with_context(sync_context, lang='en_US').write({'name': label})
