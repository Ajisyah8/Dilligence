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
    def upload_qris_proof(self, proof_file=None, **post):
        transaction_id = request.session.get('__payment_monitored_tx_id__')
        transaction = request.env['payment.transaction'].sudo().browse(transaction_id).exists()
        if not transaction:
            return request.redirect('/payment/status')

        if transaction.provider_id.custom_mode != 'qris_static':
            return request.redirect('/payment/status')

        try:
            transaction._save_qris_proof(proof_file)
            # Do not depend on the browser polling /payment/status: a successful
            # QRIS proof must immediately confirm its order and grant course access.
            transaction._post_process()
        except ValidationError as error:
            request.session['qris_upload_error'] = str(error)

        return request.redirect('/payment/status')
