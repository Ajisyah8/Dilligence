from odoo import http
from odoo.http import request

from odoo.addons.website_sale.controllers.main import WebsiteSale


class DiligenceWebsiteSale(WebsiteSale):
    """Keep QRIS checkout on the proof-upload step while payment is pending."""

    def _create_or_update_address(
        self,
        partner_sudo,
        address_type="billing",
        use_delivery_as_billing=False,
        callback="/my/addresses",
        required_fields=False,
        verify_address_values=True,
        order_sudo=False,
        **form_data
    ):
        """Also synchronize checkout data to the student's main contact.

        Odoo may store billing/delivery data on a child address. Diligence
        uses the student's main contact for the student directory and
        WhatsApp, so keep submitted contact details synchronized there too.
        """
        partner_sudo, feedback_dict = super()._create_or_update_address(
            partner_sudo,
            address_type=address_type,
            use_delivery_as_billing=use_delivery_as_billing,
            callback=callback,
            required_fields=required_fields,
            verify_address_values=verify_address_values,
            order_sudo=order_sudo,
            **form_data
        )
        if feedback_dict.get("invalid_fields") or not partner_sudo:
            return partner_sudo, feedback_dict

        address_values, _extra_form_data = self._parse_form_data(form_data)
        contact = partner_sudo.commercial_partner_id
        sync_fields = {
            field: address_values[field]
            for field in (
                "name", "email", "phone", "street", "street2", "city",
                "zip", "country_id", "state_id",
            )
            if field in address_values
        }
        if contact and sync_fields and not contact.is_company:
            contact.sudo().write(sync_fields)

        return partner_sudo, feedback_dict


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
