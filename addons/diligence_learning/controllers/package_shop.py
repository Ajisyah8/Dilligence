from odoo import http
from odoo.addons.website_sale.controllers.cart import Cart
from odoo.addons.website_sale.controllers.main import WebsiteSale


class DiligencePackageShop(WebsiteSale):
    """Public, human-friendly alias for the learning package catalogue."""

    @staticmethod
    def _get_shop_path(category=None, page=0):
        path = '/paket-belajar'
        if category:
            path += f'/category/{http.request.env["ir.http"]._slug(category)}'
        if page:
            path += f'/page/{page}'
        return path

    @http.route('/paket-belajar/<model("product.template"):product>', type='http', auth='public', website=True, sitemap=True)
    def paket_belajar_product(self, product, category=None, pricelist=None, **kwargs):
        return super().product(product, category=category, pricelist=pricelist, **kwargs)

    @http.route('/paket-belajar/checkout', type='http', methods=['GET'], auth='public', website=True, sitemap=False)
    def paket_checkout(self, try_skip_step=None, **query_params):
        return super().shop_checkout(try_skip_step=try_skip_step, **query_params)

    @http.route('/paket-belajar/address', type='http', methods=['GET'], auth='public', website=True, sitemap=False)
    def paket_address(self, **query_params):
        return super().shop_address(**query_params)

    @http.route('/paket-belajar/address/submit', type='http', methods=['POST'], auth='public', website=True, sitemap=False)
    def paket_address_submit(self, **form_data):
        return super().shop_address_submit(**form_data)

    @http.route('/paket-belajar/payment', type='http', auth='public', website=True, sitemap=False)
    def paket_payment(self, **post):
        return super().shop_payment(**post)

    @http.route('/paket-belajar/extra_info', type='http', auth='public', website=True, sitemap=False)
    def paket_extra_info(self, **post):
        return super().extra_info(**post)

    @http.route('/paket-belajar/payment/validate', type='http', auth='public', website=True, sitemap=False)
    def paket_payment_validate(self, sale_order_id=None, **post):
        return super().shop_payment_validate(sale_order_id=sale_order_id, **post)

    @http.route('/paket-belajar/confirmation', type='http', auth='public', website=True, sitemap=False)
    def paket_confirmation(self, **post):
        return super().shop_payment_confirmation(**post)


class DiligencePackageCart(Cart):
    @http.route('/paket-belajar/cart', type='http', auth='public', website=True, sitemap=False)
    def paket_cart(self, **post):
        return super().cart(**post)
