import logging
import re

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError


_logger = logging.getLogger(__name__)


class DiligenceWhatsAppService(models.AbstractModel):
    """Small Evolution API adapter kept outside Odoo's core WhatsApp code."""

    _name = 'diligence.whatsapp.service'
    _description = 'Diligence Evolution WhatsApp Service'

    @api.model
    def _parameter(self, key, default=False):
        return self.env['ir.config_parameter'].sudo().get_param(key, default)

    @api.model
    def normalize_number(self, number):
        value = re.sub(r'[^0-9+]', '', number or '')
        if value.startswith('+'):
            value = value[1:]
        if value.startswith('00'):
            value = value[2:]
        if value.startswith('0'):
            value = self._parameter('diligence.whatsapp.default_country_code', '62') + value[1:]
        return value if len(value) >= 8 else False

    @api.model
    def is_configured(self):
        return all((
            self._parameter('diligence.whatsapp.enabled', 'False') == 'True',
            self._parameter('diligence.whatsapp.api_url'),
            self._parameter('diligence.whatsapp.instance'),
            self._parameter('diligence.whatsapp.api_key'),
        ))

    @api.model
    def send_text(self, number, message):
        """Send one text through Evolution API and return a safe result.

        The API key is never included in logs or error messages. A disabled or
        incomplete connector is deliberately a no-op for local development.
        """
        if not self.is_configured():
            return {'sent': False, 'skipped': True, 'reason': 'not_configured'}
        normalized = self.normalize_number(number)
        if not normalized:
            return {'sent': False, 'skipped': True, 'reason': 'invalid_number'}
        base_url = self._parameter('diligence.whatsapp.api_url').rstrip('/')
        instance = self._parameter('diligence.whatsapp.instance')
        endpoint = f'{base_url}/message/sendText/{instance}'
        try:
            response = requests.post(
                endpoint,
                json={'number': normalized, 'text': message or ''},
                headers={
                    'Content-Type': 'application/json',
                    'apikey': self._parameter('diligence.whatsapp.api_key'),
                },
                timeout=15,
            )
            response.raise_for_status()
        except requests.RequestException as error:
            _logger.warning('Evolution API WhatsApp send failed: %s', error.__class__.__name__)
            return {'sent': False, 'error': 'request_failed'}
        return {'sent': True, 'status_code': response.status_code}


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    diligence_whatsapp_enabled = fields.Boolean(
        string='Enable Evolution WhatsApp',
        config_parameter='diligence.whatsapp.enabled',
        help='Enable only after the Evolution API instance has been tested.',
    )
    diligence_whatsapp_api_url = fields.Char(
        string='Evolution API URL', config_parameter='diligence.whatsapp.api_url',
        help='Example: http://127.0.0.1:8080',
    )
    diligence_whatsapp_instance = fields.Char(
        string='Evolution Instance', config_parameter='diligence.whatsapp.instance',
    )
    diligence_whatsapp_api_key = fields.Char(
        string='Evolution API Key', config_parameter='diligence.whatsapp.api_key',
        password=True,
    )
    diligence_whatsapp_default_country_code = fields.Char(
        string='Default Country Code', default='62',
        config_parameter='diligence.whatsapp.default_country_code',
        help='Used to convert local numbers such as 0812... into 62812...',
    )
    diligence_whatsapp_send_on_payment = fields.Boolean(
        string='Send Payment Confirmation',
        config_parameter='diligence.whatsapp.send_on_payment',
    )


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def action_diligence_send_whatsapp_test(self):
        self.ensure_one()
        if not self.phone and not self.mobile:
            raise UserError(_('Add a WhatsApp number before sending a test message.'))
        result = self.env['diligence.whatsapp.service'].send_text(
            self.mobile or self.phone,
            _('Hello %(name)s, this is a test message from Diligence Academy.', name=self.name),
        )
        if result.get('skipped'):
            raise UserError(_('Evolution API is disabled or not configured.'))
        if not result.get('sent'):
            raise UserError(_('The Evolution API request failed. Check the server log.'))
        return True
