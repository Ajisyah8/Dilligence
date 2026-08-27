from datetime import date

from odoo import http
from odoo.http import request


class DiligenceReferralController(http.Controller):

    @http.route('/diligence/referral/<string:code>', type='http', auth='public', website=True, sitemap=False)
    def apply_referral(self, code, **kwargs):
        referral_code = code.strip().upper()
        referrer = request.env['res.partner'].sudo().search([
            ('diligence_referral_code', '=', referral_code),
            ('diligence_is_affiliate', '=', True),
        ], limit=1)
        today = date.today()
        if referrer and (
            (referrer.diligence_affiliate_start_date and referrer.diligence_affiliate_start_date > today)
            or (referrer.diligence_affiliate_end_date and referrer.diligence_affiliate_end_date < today)
        ):
            referrer = request.env['res.partner'].sudo().browse()
        if referrer:
            # Odoo 19 exposes the current cart through ``request.cart``;
            # ``website.sale_get_order`` was removed from the website API.
            order = request.cart or request.website._create_cart()
            order.sudo().write({'diligence_referral_code': referral_code})
            request.session['diligence_referral_code'] = referral_code
        return request.redirect('/shop')
