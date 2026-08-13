from odoo import http
from odoo.http import request


class DiligenceReferralController(http.Controller):

    @http.route('/diligence/referral/<string:code>', type='http', auth='public', website=True, sitemap=False)
    def apply_referral(self, code, **kwargs):
        referral_code = code.strip().upper()
        referrer = request.env['res.partner'].sudo().search([
            ('diligence_referral_code', '=', referral_code),
        ], limit=1)
        if referrer:
            # Odoo 19 exposes the current cart through ``request.cart``;
            # ``website.sale_get_order`` was removed from the website API.
            order = request.cart or request.website._create_cart()
            order.sudo().write({'diligence_referral_code': referral_code})
            request.session['diligence_referral_code'] = referral_code
        return request.redirect('/paket-belajar')
