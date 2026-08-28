from odoo import fields, models


class DiligenceWhatsAppWebhookEvent(models.Model):
    _name = 'diligence.whatsapp.webhook.event'
    _description = 'Evolution WhatsApp Webhook Event'
    _order = 'received_at desc, id desc'

    event_key = fields.Char(required=True, index=True, copy=False)
    event_name = fields.Char(required=True, index=True, copy=False)
    instance_name = fields.Char(index=True, copy=False)
    message_id = fields.Char(index=True, copy=False)
    received_at = fields.Datetime(required=True, default=fields.Datetime.now, copy=False)
    state = fields.Selection([('received', 'Received'), ('ignored', 'Ignored')], required=True, default='received', copy=False)

    _event_key_unique = models.Constraint('unique(event_key)', 'This Evolution webhook event has already been received.')
