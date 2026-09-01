from odoo import http
from odoo.http import request

from odoo.addons.website_sale.controllers.main import WebsiteSale


class DiligenceWebsiteSale(WebsiteSale):
    """Keep QRIS checkout on the proof-upload step while payment is pending."""

    @http.route('/shop/payment/validate', type='http', auth='public', website=True, sitemap=False)
    def shop_payment_validate(self, sale_order_id=None, **post):
        order = request.cart
        if not order and request.session.get('sale_last_order_id'):
            order = request.env['sale.order'].sudo().browse(
                request.session['sale_last_order_id']
            ).exists()
        transaction = order.get_portal_last_transaction() if order else False
        if (
            transaction
            and transaction.state == 'pending'
            and transaction.provider_id.custom_mode == 'qris_static'
        ):
            return request.redirect('/payment/status')
        return super().shop_payment_validate(sale_order_id=sale_order_id, **post)
