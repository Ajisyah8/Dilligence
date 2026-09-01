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

    @api.model
    def render_message(self, template, partner=None, **values):
        """Render a configured message without leaking configuration values."""
        values = dict(values, name=partner.name if partner else '')
        try:
            return (template or '') % values
        except (KeyError, TypeError, ValueError):
            _logger.warning('WhatsApp message template could not be rendered')
            return template or ''

    @api.model
    def queue_payment_confirmation(self, order):
        """Create one delivery per order and send it once after valid payment."""
        delivery = self.env['diligence.whatsapp.delivery'].sudo().search([
            ('sale_order_id', '=', order.id),
            ('kind', '=', 'payment_confirmation'),
        ], limit=1)
        if not delivery:
            group_links = order.order_line.mapped(
                'product_template_id.diligence_whatsapp_group_link'
            )
            group_message = (
                _('\nWhatsApp Community Group: %(link)s', link=group_links[0])
                if group_links else ''
            )
            template = self._parameter(
                'diligence.whatsapp.payment_message',
                'Pembayaran order %(order)s berhasil divalidasi. '
                'Akses paket belajar Anda sudah aktif di Diligence Academy.'
                '%(group_message)s',
            )
            delivery = self.env['diligence.whatsapp.delivery'].sudo().create({
                'sale_order_id': order.id,
                'partner_id': order.partner_id.commercial_partner_id.id,
                'kind': 'payment_confirmation',
                'message': self.render_message(
                    template,
                    order.partner_id,
                    order=order.name,
                    group_message=group_message,
                ),
            })
        return delivery.action_send()


class DiligenceWhatsAppDelivery(models.Model):
    _name = 'diligence.whatsapp.delivery'
    _description = 'Diligence WhatsApp Delivery'
    _order = 'create_date desc'

    partner_id = fields.Many2one('res.partner', required=True, index=True, ondelete='restrict')
    sale_order_id = fields.Many2one('sale.order', index=True, ondelete='set null')
    kind = fields.Selection([
        ('payment_confirmation', 'Payment Confirmation'),
        ('survey', 'Bulk Survey'),
        ('test', 'Test'),
    ], required=True, index=True)
    phone = fields.Char(compute='_compute_phone', store=True)
    message = fields.Text(required=True)
    state = fields.Selection([
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('skipped', 'Skipped'),
        ('error', 'Error'),
    ], default='pending', required=True, index=True, copy=False)
    sent_at = fields.Datetime(copy=False, readonly=True)
    error_message = fields.Char(copy=False, readonly=True)

    _payment_delivery_uniq = models.Constraint(
        'unique(sale_order_id, kind)',
        'Only one WhatsApp delivery of each type is allowed per order.',
    )

    @api.depends('partner_id.phone')
    def _compute_phone(self):
        for delivery in self:
            delivery.phone = self.env['diligence.whatsapp.service'].normalize_number(
                delivery.partner_id.phone
            ) if delivery.partner_id else False

    def action_send(self):
        service = self.env['diligence.whatsapp.service'].sudo()
        for delivery in self.filtered(lambda record: record.state not in ('sent',)):
            result = service.send_text(delivery.phone, delivery.message)
            values = {
                'state': 'sent' if result.get('sent') else 'skipped' if result.get('skipped') else 'error',
                'error_message': result.get('error') or False,
                'sent_at': fields.Datetime.now() if result.get('sent') else False,
            }
            delivery.write(values)
        return True


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    diligence_whatsapp_enabled = fields.Boolean(string='Enable Evolution WhatsApp', config_parameter='diligence.whatsapp.enabled')
    diligence_whatsapp_api_url = fields.Char(string='Evolution API URL', config_parameter='diligence.whatsapp.api_url')
    diligence_whatsapp_instance = fields.Char(string='Evolution Instance', config_parameter='diligence.whatsapp.instance')
    diligence_whatsapp_api_key = fields.Char(string='Evolution API Key', config_parameter='diligence.whatsapp.api_key')
    diligence_whatsapp_default_country_code = fields.Char(string='Default Country Code', config_parameter='diligence.whatsapp.default_country_code', default='62')
    diligence_whatsapp_send_on_payment = fields.Boolean(string='Send Payment Confirmation', config_parameter='diligence.whatsapp.send_on_payment')
    # res.config.settings config_parameter fields must use a supported
    # persisted scalar type; Text fields are rejected by Odoo's settings
    # classifier before the form is rendered.
    diligence_whatsapp_signup_message = fields.Char(
        string='Signup Welcome Message',
        config_parameter='diligence.whatsapp.signup_message',
        default='Halo %(name)s, selamat datang di Diligence Academy. Akun Anda berhasil dibuat. Selamat belajar!',
        help='Use %(name)s for the new user name.',
    )
    diligence_whatsapp_test_message = fields.Char(
        string='Test WhatsApp Message',
        config_parameter='diligence.whatsapp.test_message',
        default='Hello %(name)s, this is a test message from Diligence Academy.',
        help='Use %(name)s for the contact name.',
    )
    diligence_whatsapp_payment_message = fields.Char(
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
        login = result[0] if result else values.get('login')
        user = self.sudo().search([('login', '=', login)], limit=1)
        if not user or not user.partner_id:
            return result
        partner = user.partner_id.sudo()
        service = self.env['diligence.whatsapp.service'].sudo()
        normalized_phone = service.normalize_number(phone)
        partner.write({
            'phone': normalized_phone or phone,
            'diligence_whatsapp_signup_status': 'skipped' if not normalized_phone else 'pending',
            'diligence_whatsapp_signup_error': False,
        })
        if not normalized_phone:
            return result
        params = self.env['ir.config_parameter'].sudo()
        template = params.get_param(
            'diligence.whatsapp.signup_message',
            'Halo %(name)s, selamat datang di Diligence Academy. Akun Anda berhasil dibuat. Selamat belajar!',
        )
        message = template % {'name': partner.name}
        send_result = service.send_text(normalized_phone, message)
        status = 'sent' if send_result.get('sent') else 'skipped' if send_result.get('skipped') else 'error'
        partner.write({
            'diligence_whatsapp_signup_status': status,
            'diligence_whatsapp_signup_error': send_result.get('error') or False,
        })
        _logger.info('Signup WhatsApp welcome result status=%s', status)
        return result


class ResPartner(models.Model):
    _inherit = 'res.partner'

    diligence_whatsapp_signup_status = fields.Selection([
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('skipped', 'Skipped'),
        ('error', 'Error'),
    ], string='Signup WhatsApp Status', copy=False, readonly=True)
    diligence_whatsapp_signup_error = fields.Char(
        string='Signup WhatsApp Error', copy=False, readonly=True,
    )

    def action_diligence_send_whatsapp_test(self):
        self.ensure_one()
        if not self.phone:
            raise UserError(_('Add a WhatsApp number before sending a test message.'))
        message = self.env['ir.config_parameter'].sudo().get_param(
            'diligence.whatsapp.test_message',
            'Hello %(name)s, this is a test message from Diligence Academy.',
        ) % {'name': self.name}
        result = self.env['diligence.whatsapp.service'].sudo().send_text(self.phone, message)
        if result.get('skipped'):
            raise UserError(_('Evolution API is disabled or not configured.'))
        if not result.get('sent'):
            raise UserError(_('The Evolution API request failed. Check the server log.'))
        return True
