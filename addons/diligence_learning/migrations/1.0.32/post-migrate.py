def migrate(cr, version):
    from odoo.api import Environment

    env = Environment(cr, 1, {})
    products = env['product.template'].with_context(active_test=False)

    community_candidates = products.search([
        ('diligence_package_type', '=', 'community'),
    ], order='id asc')
    community = community_candidates.filtered('website_published')[:1] or community_candidates[:1]
    if community:
        community.write({
            'list_price': 269000.0,
            'diligence_early_bird_enabled': True,
            'diligence_early_bird_price': 239000.0,
            'diligence_early_bird_start_date': False,
        })

    coaching_candidates = products.search([
        ('diligence_package_type', '=', 'consultation'),
    ], order='id asc')
    coaching = coaching_candidates.filtered('website_published')[:1] or coaching_candidates[:1]
    if coaching:
        coaching.diligence_sales_status = 'full'
