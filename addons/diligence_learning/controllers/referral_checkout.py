from odoo import http
from odoo.http import request


class DiligenceReferralCheckoutController(http.Controller):

    @http.route('/shop/referral/apply', type='http', auth='public', website=True,
                methods=['POST'], sitemap=False)
    def apply_checkout_referral(self, referral_code='', **kwargs):
        order = request.cart
        code = (referral_code or '').strip().upper()
        if order and code:
            referrer = order.sudo()._diligence_referrer_for_code(code)
            if referrer:
                order.sudo().write({'diligence_referral_code': code})
                request.session['diligence_referral_code'] = code
                return request.redirect('/shop/payment?referral_status=valid')
        return request.redirect('/shop/payment?referral_status=invalid')
