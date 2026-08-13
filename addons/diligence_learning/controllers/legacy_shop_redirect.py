from odoo import http
from odoo.http import request


class DiligenceLegacyShopRedirect(http.Controller):
    """Keep old checkout links compatible with the package-friendly URLs."""

    @http.route('/shop', type='http', auth='public', website=True, sitemap=False)
    def redirect_shop_root(self, **kwargs):
        query = request.httprequest.query_string.decode()
        return request.redirect('/paket-belajar' + (f'?{query}' if query else ''), code=301)

    @http.route('/shop/<model("product.template"):product>', type='http', auth='public', website=True, sitemap=False)
    def redirect_package_product(self, product, **kwargs):
        if product.diligence_package_type:
            return request.redirect(product._get_product_url(), code=301)
        return request.redirect('/paket-belajar', code=301)

    @http.route('/shop/cart', type='http', auth='public', website=True, sitemap=False)
    def redirect_cart(self, **kwargs):
        query = request.httprequest.query_string.decode()
        return request.redirect('/paket-belajar/cart' + (f'?{query}' if query else ''))

    @http.route('/shop/address', type='http', auth='public', website=True, sitemap=False)
    def redirect_address(self, **kwargs):
        query = request.httprequest.query_string.decode()
        return request.redirect('/paket-belajar/address' + (f'?{query}' if query else ''))

    @http.route('/shop/checkout', type='http', auth='public', website=True, sitemap=False)
    def redirect_checkout(self, **kwargs):
        query = request.httprequest.query_string.decode()
        return request.redirect('/paket-belajar/checkout' + (f'?{query}' if query else ''))

    @http.route('/shop/payment', type='http', auth='public', website=True, sitemap=False)
    def redirect_payment(self, **kwargs):
        query = request.httprequest.query_string.decode()
        return request.redirect('/paket-belajar/payment' + (f'?{query}' if query else ''))

    @http.route('/shop/confirmation', type='http', auth='public', website=True, sitemap=False)
    def redirect_confirmation(self, **kwargs):
        query = request.httprequest.query_string.decode()
        return request.redirect('/paket-belajar/confirmation' + (f'?{query}' if query else ''))
