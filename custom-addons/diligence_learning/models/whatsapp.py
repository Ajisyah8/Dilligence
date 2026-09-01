import logging
import re

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class DiligenceWhatsAppService(models.AbstractModel):
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
            self._parameter('diligence.whatsapp.enabled', 'False').lower() == 'true',
            self._parameter('diligence.whatsapp.api_url'),
            self._parameter('diligence.whatsapp.instance'),
            self._parameter('diligence.whatsapp.api_key'),
        ))

    @api.model
    def send_text(self, number, message):
        if not self.is_configured():
            return {'sent': False, 'skipped': True}
        normalized = self.normalize_number(number)
        if not normalized:
            return {'sent': False, 'skipped': True}
        endpoint = '%s/message/sendText/%s' % (
            self._parameter('diligence.whatsapp.api_url').rstrip('/'),
            self._parameter('diligence.whatsapp.instance'),
        )
        try:
            response = requests.post(
                endpoint,
                json={'number': normalized, 'text': message or ''},
                headers={'Content-Type': 'application/json', 'apikey': self._parameter('diligence.whatsapp.api_key')},
                timeout=15,
            )
            response.raise_for_status()
        except requests.RequestException as error:
            _logger.warning('Evolution API WhatsApp send failed: %s', error.__class__.__name__)
            return {'sent': False, 'error': 'request_failed'}
        return {'sent': True, 'status_code': response.status_code}


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    diligence_whatsapp_enabled = fields.Boolean(string='Enable Evolution WhatsApp', config_parameter='diligence.whatsapp.enabled')
    diligence_whatsapp_api_url = fields.Char(string='Evolution API URL', config_parameter='diligence.whatsapp.api_url')
    diligence_whatsapp_instance = fields.Char(string='Evolution Instance', config_parameter='diligence.whatsapp.instance')
    diligence_whatsapp_api_key = fields.Char(string='Evolution API Key', config_parameter='diligence.whatsapp.api_key')
    diligence_whatsapp_default_country_code = fields.Char(string='Default Country Code', config_parameter='diligence.whatsapp.default_country_code', default='62')
    diligence_whatsapp_send_on_payment = fields.Boolean(string='Send Payment Confirmation', config_parameter='diligence.whatsapp.send_on_payment')
    diligence_whatsapp_signup_message = fields.Text(
        string='Signup Welcome Message',
        config_parameter='diligence.whatsapp.signup_message',
        help='Use %(name)s for the new user name.',
    )
    diligence_whatsapp_test_message = fields.Text(
        string='Test WhatsApp Message',
        config_parameter='diligence.whatsapp.test_message',
        help='Use %(name)s for the contact name.',
    )
    diligence_whatsapp_payment_message = fields.Text(
        string='Payment Confirmation Message',
        config_parameter='diligence.whatsapp.payment_message',
        default='Pembayaran order %(order)s berhasil divalidasi. Akses paket belajar Anda sudah aktif di Diligence Academy.%(group_message)s',
        help='Available placeholders: %(name)s, %(order)s, and %(group_message)s.',
    )


class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.model
    def signup(self, values, token=None):
        phone = (values.get('phone') or '').strip()
        result = super().signup(values, token)
        if not phone:
            return result
        login = result[0] if result else values.get('login')
        user = self.sudo().search([('login', '=', login)], limit=1)
        if not user or not user.partner_id:
            return result
        partner = user.partner_id.sudo()
        partner.write({'phone': phone})
        params = self.env['ir.config_parameter'].sudo()
        template = params.get_param(
            'diligence.whatsapp.signup_message',
            'Halo %(name)s, selamat datang di Diligence Academy. Akun Anda berhasil dibuat. Selamat belajar!',
        )
        message = template % {'name': partner.name}
        send_result = self.env['diligence.whatsapp.service'].sudo().send_text(phone, message)
        _logger.info('Signup WhatsApp welcome result sent=%s skipped=%s error=%s', send_result.get('sent'), send_result.get('skipped'), send_result.get('error'))
        return result


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def action_diligence_send_whatsapp_test(self):
        self.ensure_one()
        if not self.phone:
            raise UserError(_('Add a WhatsApp number before sending a test message.'))
        message = self.env['ir.config_parameter'].sudo().get_param(
            'diligence.whatsapp.test_message',
            'Hello %(name)s, this is a test message from Diligence Academy.',
        ) % {'name': self.name}
        result = self.env['diligence.whatsapp.service'].send_text(self.phone, message)
        if result.get('skipped'):
            raise UserError(_('Evolution API is disabled or not configured.'))
        if not result.get('sent'):
            raise UserError(_('The Evolution API request failed. Check the server log.'))
        return True
