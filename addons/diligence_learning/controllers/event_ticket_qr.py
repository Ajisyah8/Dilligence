import io

import qrcode

from odoo import http
from odoo.http import request
from werkzeug.exceptions import NotFound


class DiligenceEventTicketQrController(http.Controller):

    @http.route('/diligence/event/qr/<string:barcode>', type='http', auth='public',
                website=True, sitemap=False, readonly=True)
    def event_ticket_qr(self, barcode, **kwargs):
        if barcode != '12345678901234567890' and not request.env[
                'event.registration'].sudo().search_count([('barcode', '=', barcode)]):
            raise NotFound()
        image = qrcode.make(barcode)
        output = io.BytesIO()
        image.save(output, format='PNG')
        return request.make_response(output.getvalue(), headers=[
            ('Content-Type', 'image/png'),
            ('Cache-Control', 'public, max-age=86400'),
        ])
