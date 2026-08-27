from datetime import timedelta
import logging

from odoo import api, fields, models, _


_logger = logging.getLogger(__name__)


class DiligenceNewsletterStage(models.Model):
    _name = 'diligence.newsletter.stage'
    _description = 'Diligence Newsletter Drip Stage'
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    delay_days = fields.Integer(
        required=True, default=0,
        help='Number of days after the student registration date.',
    )
    template_id = fields.Many2one(
        'mail.template', required=True, ondelete='restrict',
        domain="[('model', '=', 'diligence.newsletter.delivery')]",
    )
    active = fields.Boolean(default=True)

    _delay_nonnegative = models.Constraint(
        'CHECK(delay_days >= 0)',
        'A newsletter delay cannot be negative.',
    )


class DiligenceNewsletterDelivery(models.Model):
    _name = 'diligence.newsletter.delivery'
    _description = 'Diligence Newsletter Delivery'
    _order = 'scheduled_date, id'

    partner_id = fields.Many2one('res.partner', required=True, index=True, ondelete='cascade')
    stage_id = fields.Many2one('diligence.newsletter.stage', required=True, index=True, ondelete='restrict')
    scheduled_date = fields.Datetime(required=True, index=True)
    state = fields.Selection([
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('skipped', 'Skipped'),
    ], required=True, default='pending', index=True)
    attempt_count = fields.Integer(default=0)
    sent_at = fields.Datetime(readonly=True)
    last_error = fields.Text(readonly=True)

    _partner_stage_uniq = models.Constraint(
        'unique(partner_id, stage_id)',
        'A student can only have one delivery record for each newsletter stage.',
    )

    @api.model
    def _newsletter_list(self):
        return self.env['mailing.list'].sudo().search([
            ('name', '=', 'Diligence Academy Newsletter'),
        ], limit=1)

    @api.model
    def _is_subscribed(self, partner):
        mailing_list = self._newsletter_list()
        if not mailing_list or not partner.email:
            return False
        contact = self.env['mailing.contact'].sudo().search([
            ('email', '=ilike', partner.email),
        ], limit=1)
        subscription = contact.subscription_ids.filtered(
            lambda record: record.list_id == mailing_list
        )
        return bool(subscription and not subscription[-1].opt_out)

    @api.model
    def _ensure_deliveries(self):
        stages = self.env['diligence.newsletter.stage'].sudo().search([('active', '=', True)])
        partners = self.env['res.partner'].sudo().search([
            ('diligence_newsletter_opt_in', '=', True),
            ('email', '!=', False),
            ('active', '=', True),
        ])
        for partner in partners:
            if not self._is_subscribed(partner):
                continue
            registration_date = partner.create_date or fields.Datetime.now()
            for stage in stages:
                if self.search_count([
                    ('partner_id', '=', partner.id), ('stage_id', '=', stage.id),
                ]):
                    continue
                self.create({
                    'partner_id': partner.id,
                    'stage_id': stage.id,
                    'scheduled_date': registration_date + timedelta(days=stage.delay_days),
                })

    @api.model
    def _cron_process(self):
        self._ensure_deliveries()
        now = fields.Datetime.now()
        deliveries = self.sudo().search([
            ('state', 'in', ('pending', 'failed')),
            ('scheduled_date', '<=', now),
            ('attempt_count', '<', 3),
        ], order='scheduled_date, id', limit=100)
        test_mode = self.env['ir.config_parameter'].sudo().get_param(
            'diligence.email_test_mode', 'True',
        ).lower() in ('1', 'true', 'yes', 'on')
        for delivery in deliveries:
            if not delivery.partner_id.diligence_newsletter_opt_in or not self._is_subscribed(delivery.partner_id):
                delivery.write({'state': 'skipped', 'last_error': _('Student is not subscribed.')})
                continue
            if test_mode:
                delivery.write({'last_error': _('Email test mode is enabled; no email was sent.')})
                continue
            try:
                delivery.stage_id.template_id.sudo().send_mail(
                    delivery.id,
                    force_send=False,
                    raise_exception=True,
                )
                delivery.write({
                    'state': 'sent',
                    'sent_at': now,
                    'attempt_count': delivery.attempt_count + 1,
                    'last_error': False,
                })
            except Exception as error:
                _logger.exception('Newsletter drip failed for delivery %s', delivery.id)
                delivery.write({
                    'state': 'failed',
                    'attempt_count': delivery.attempt_count + 1,
                    'last_error': str(error),
                })
        return True
