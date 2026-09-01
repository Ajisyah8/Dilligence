from odoo import _, http
from odoo.exceptions import ValidationError
from odoo.http import request


class StaticQrisController(http.Controller):

    @http.route(
        '/payment/qris_static/upload',
        type='http',
        auth='public',
        methods=['POST'],
        website=True,
        csrf=True,
    )
    def upload_qris_proof(self, proof_file=None, paid_amount=None, **post):
        transaction_id = request.session.get('__payment_monitored_tx_id__')
        transaction = request.env['payment.transaction'].sudo().browse(transaction_id).exists()
        if not transaction:
            return request.redirect('/payment/status')

        if transaction.provider_id.custom_mode != 'qris_static':
            return request.redirect('/payment/status')

        # A logged-in customer may only submit proof for their own order. For
        # public checkout, the monitored transaction in the current session is
        # the ownership token and no transaction id is accepted from the form.
        uploaded = False
        try:
            if not request.env.user._is_public():
                partner = transaction.sale_order_ids[:1].partner_id.commercial_partner_id
                if partner != request.env.user.partner_id.commercial_partner_id:
                    raise ValidationError(_('You can only submit proof for your own order.'))
            transaction._save_qris_proof(proof_file, paid_amount)
            uploaded = True
        except ValidationError as error:
            request.session['qris_upload_error'] = str(error)

        if uploaded:
            return request.redirect('/shop/confirmation')
        return request.redirect('/payment/status')
