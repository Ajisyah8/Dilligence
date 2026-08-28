import hashlib
import hmac
import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class DiligenceWhatsAppWebhookController(http.Controller):
    @http.route('/webhook/evolution', type='http', auth='public', methods=['POST'], csrf=False)
    def evolution_webhook(self, **kwargs):
        secret = request.env['ir.config_parameter'].sudo().get_param('diligence.whatsapp.webhook_secret')
        supplied = request.httprequest.headers.get('X-Evolution-Secret', '')
        if not secret or not hmac.compare_digest(supplied, secret):
            return request.make_json_response({'ok': False, 'error': 'unauthorized'}, status=401)

        raw = request.httprequest.get_data(cache=True)
        try:
            payload = json.loads(raw.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return request.make_json_response({'ok': False, 'error': 'invalid_json'}, status=400)
        if not isinstance(payload, dict):
            return request.make_json_response({'ok': False, 'error': 'invalid_payload'}, status=400)

        event_name = str(payload.get('event') or payload.get('type') or '').upper()
        if event_name not in {'CONNECTION_UPDATE', 'MESSAGES_UPSERT', 'MESSAGES_UPDATE', 'SEND_MESSAGE'}:
            return request.make_json_response({'ok': True, 'ignored': True})

        data = payload.get('data') if isinstance(payload.get('data'), dict) else payload
        key = data.get('key') if isinstance(data.get('key'), dict) else {}
        message_id = key.get('id') or data.get('messageId') or payload.get('messageId')
        event_key = str(message_id or payload.get('id') or '').strip() or hashlib.sha256(raw).hexdigest()
        instance_name = str(payload.get('instance') or data.get('instance') or '').strip() or False

        Event = request.env['diligence.whatsapp.webhook.event'].sudo()
        if Event.search_count([('event_key', '=', event_key)]):
            return request.make_json_response({'ok': True, 'duplicate': True})
        try:
            Event.create({
                'event_key': event_key,
                'event_name': event_name,
                'instance_name': instance_name,
                'message_id': str(message_id).strip() if message_id else False,
            })
        except Exception as error:
            request.env.cr.rollback()
            if Event.search_count([('event_key', '=', event_key)]):
                return request.make_json_response({'ok': True, 'duplicate': True})
            _logger.warning('Evolution webhook persistence failed: %s', error.__class__.__name__)
            return request.make_json_response({'ok': False, 'error': 'persistence_failed'}, status=500)
        return request.make_json_response({'ok': True, 'duplicate': False})
