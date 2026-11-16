from odoo import fields, http
from odoo.http import request
from werkzeug.exceptions import NotFound


class DiligencePackageRenewalController(http.Controller):

    def _get_order(self, token):
        order = request.env['sale.order'].sudo().search([
            ('diligence_renewal_token', '=', token),
            ('diligence_renewal_package_id', '!=', False),
        ], limit=1)
        if not order:
            raise NotFound()
        return order

    @http.route(
        '/diligence/package-renewal/<string:token>',
        type='http', auth='public', website=True, sitemap=False,
    )
    def package_renewal_choice(self, token, **kwargs):
        order = self._get_order(token)
        intent = kwargs.get('intent') if kwargs.get('intent') in ('continue', 'not_continue') else False
        return request.render('diligence_learning.package_renewal_choice', {
            'order': order,
            'whatsapp_phone': order.diligence_renewal_whatsapp_phone or order.partner_id.phone or '',
            'expired': bool(
                order.diligence_access_expires_at
                and order.diligence_access_expires_at < fields.Datetime.now()
            ),
            'saved_choice': kwargs.get('saved_choice'),
            'intent': intent,
        })

    @http.route(
        '/diligence/package-renewal/respond',
        type='http', auth='public', website=True, methods=['POST'], sitemap=False,
    )
    def package_renewal_respond(self, token=None, choice=None, **post):
        if choice not in ('continue', 'not_continue'):
            raise NotFound()
        order = self._get_order(token)
        if (
            not order.diligence_access_expires_at
            or order.diligence_access_expires_at < fields.Datetime.now()
            or order.diligence_renewal_status in ('renewed', 'expired')
        ):
            return request.redirect('/diligence/package-renewal/%s' % token)

        if choice == 'not_continue':
            reason = post.get('reason')
            allowed_reasons = {'completed_material', 'no_time', 'not_interested', 'other'}
            reason_note = (post.get('reason_note') or '').strip()
            whatsapp_phone = (post.get('whatsapp_phone') or '').strip()
            normalized_phone = request.env['diligence.whatsapp.service'].sudo().normalize_number(whatsapp_phone)
            if (
                reason not in allowed_reasons
                or (reason == 'other' and not reason_note)
                or not normalized_phone
            ):
                return request.redirect(
                    '/diligence/package-renewal/%s?intent=not_continue&invalid_reason=1' % token
                )
            order.write({
                'diligence_renewal_status': 'not_continue',
                'diligence_renewal_response_at': fields.Datetime.now(),
                'diligence_renewal_reason': reason,
                'diligence_renewal_reason_note': reason_note if reason == 'other' else False,
                'diligence_renewal_whatsapp_phone': normalized_phone,
                'diligence_whatsapp_group_removal_state': 'pending',
            })
            order._diligence_remove_from_whatsapp_group()
            return request.redirect(
                '/diligence/package-renewal/%s?saved_choice=not_continue' % token
            )

        package = order.diligence_renewal_package_id
        product = package.product_variant_id
        if (
            not product or not product.active or not product.sale_ok
            or not product.website_published
            or package.diligence_sales_status != 'available'
            or not package.diligence_has_available_course
            or not product._is_add_to_cart_allowed()
        ):
            return request.redirect(
                '/diligence/package-renewal/%s?saved_choice=unavailable' % token
            )

        order.write({
            'diligence_renewal_status': 'continue',
            'diligence_renewal_response_at': fields.Datetime.now(),
            'diligence_renewal_reason': False,
            'diligence_renewal_reason_note': False,
            'diligence_whatsapp_group_removal_state': 'not_required',
        })
        cart = request.cart or request.website._create_cart()
        if not cart.order_line.filtered(lambda line: line.product_id == product and not line.display_type):
            cart.sudo()._cart_add(product.id, 1)
        return request.redirect('/shop/cart')
