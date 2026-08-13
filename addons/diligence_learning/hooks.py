from odoo import SUPERUSER_ID, api


def post_init_hook(cr, registry):
    _ensure_package_template(api.Environment(cr, SUPERUSER_ID, {}))


def _ensure_package_template(env):
    filter_record = env.ref('diligence_learning.diligence_package_snippet_filter', raise_if_not_found=False)
    if not filter_record:
        return
    arch = f'''<div id="wrap">
    <section class="s_dynamic_snippet_products s_dynamic pt48 pb48 o_colored_level o_wsale_products_opt_layout_catalog o_wsale_products_opt_design_cards o_wsale_products_opt_has_cta o_wsale_products_opt_has_description"
        data-snippet="s_dynamic_snippet_products" data-name="Diligence Learning Packages"
        data-filter-id="{filter_record.id}"
        data-template-key="website_sale.dynamic_filter_template_product_product_products_item"
        data-product-category-id="all" data-show-variants="false"
        data-number-of-elements="3" data-number-of-elements-small-devices="1"
        data-number-of-records="16" data-carousel-interval="5000">
        <div class="container">
            <div class="s_dynamic_snippet_title mb-4">
                <h1>Paket Belajar</h1>
                <p class="lead">Pilih paket belajar yang sesuai dengan kebutuhan Anda.</p>
            </div>
            <div class="o_not_editable"><div class="dynamic_snippet_template"/></div>
        </div>
    </section>
</div>'''
    Page = env['website.page'].sudo().with_context(active_test=False)
    page = Page.search(['|', ('key', '=', 'diligence_learning.new_page_template_sections_custom_package_shop'), '&', ('name', '=', 'Diligence Package Shop'), ('url', '=', '/template-diligence-package-shop')], limit=1)
    if page:
        page.view_id.with_context(lang=None).write({'arch': arch})
        page.write({'name': 'Diligence Package Shop', 'is_new_page_template': True, 'website_published': False})
        return
    view = env['ir.ui.view'].sudo().create({'name': 'Diligence Package Shop Template', 'type': 'qweb', 'arch': arch, 'website_id': env.ref('website.default_website').id, 'key': 'diligence_learning.new_page_template_sections_custom_package_shop'})
    Page.create({'name': 'Diligence Package Shop', 'url': '/template-diligence-package-shop', 'view_id': view.id, 'website_id': env.ref('website.default_website').id, 'is_new_page_template': True, 'website_published': False})
