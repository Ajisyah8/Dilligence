from datetime import timedelta
import hashlib
import hmac
import logging
import re

from markupsafe import Markup
from odoo.tools import config

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

    partner_id = fields.Many2one('res.partner', index=True, ondelete='cascade')
    mailing_contact_id = fields.Many2one(
        'mailing.contact', index=True, ondelete='cascade',
        help='The public newsletter subscriber. A partner is optional.',
    )
    email = fields.Char(compute='_compute_recipient', store=True, index=True)
    contact_name = fields.Char(compute='_compute_recipient', store=True)
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
    _mailing_contact_stage_uniq = models.Constraint(
        'unique(mailing_contact_id, stage_id)',
        'A subscriber can only have one delivery record for each newsletter stage.',
    )
    _recipient_required = models.Constraint(
        'CHECK(partner_id IS NOT NULL OR mailing_contact_id IS NOT NULL)',
        'A newsletter delivery must have a partner or mailing contact.',
    )

    @api.depends('partner_id.email', 'partner_id.name', 'mailing_contact_id.email', 'mailing_contact_id.name')
    def _compute_recipient(self):
        for delivery in self:
            partner = delivery.partner_id
            contact = delivery.mailing_contact_id
            delivery.email = (contact.email if contact else False) or (partner.email if partner else False)
            delivery.contact_name = (contact.name if contact else False) or (partner.name if partner else False)

    def _unsubscribe_token(self, contact):
        self.ensure_one()
        secret = config.get('database.secret') or config.get('admin_passwd') or ''
        payload = f'{self.env.cr.dbname}:{contact.id}:{contact.email}'.encode()
        return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

    def _get_unsubscribe_url(self):
        self.ensure_one()
        contact = self.mailing_contact_id
        if not contact or not contact.email:
            return False
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '').rstrip('/')
        if not base_url:
            return False
        return f'{base_url}/diligence/newsletter/unsubscribe/{contact.id}/{self._unsubscribe_token(contact)}'

    unsubscribe_url = fields.Char(compute='_compute_unsubscribe_url')

    @api.depends('mailing_contact_id.email')
    def _compute_unsubscribe_url(self):
        for delivery in self:
            delivery.unsubscribe_url = delivery._get_unsubscribe_url() if delivery.mailing_contact_id else False

    @api.model
    def _ensure_unsubscribe_footer(self):
        footer = (
            '<p style="margin-top:24px;font-size:12px;color:#666;">'
            '<a t-att-href="object.unsubscribe_url">Unsubscribe from this newsletter</a>'
            '</p>'
        )
        stages = self.env['diligence.newsletter.stage'].sudo().search([
            ('template_id', '!=', False),
        ])
        for stage in stages:
            template = stage.template_id
            body = template.body_html or ''
            if '&lt;p style=\"margin-top:24px;font-size:12px;color:#666;\"&gt;' in body:
                normalized = re.sub(
                    r'&lt;p style=\"margin-top:24px;font-size:12px;color:#666;\"&gt;.*?&lt;/p&gt;',
                    '', body,
                )
                template.write({'body_html': Markup(normalized + footer)})
            elif 'href=\"{{ object.unsubscribe_url }}\"' in body:
                normalized = body.replace('href=\"{{ object.unsubscribe_url }}\"', 't-att-href=\"object.unsubscribe_url\"')
                template.write({'body_html': Markup(normalized)})
            elif 'object.unsubscribe_url' not in body:
                template.write({'body_html': Markup(body + footer)})

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
    def _is_contact_subscribed(self, contact):
        mailing_list = self._newsletter_list()
        if not mailing_list or not contact or not contact.email:
            return False
        subscription = contact.subscription_ids.filtered(
            lambda record: record.list_id == mailing_list and not record.opt_out
        )
        return bool(subscription)

    @api.model
    def _partner_for_contact(self, contact):
        return self.env['res.partner'].sudo().search([
            ('email', '=ilike', contact.email),
            ('active', '=', True),
        ], limit=1)

    @api.model
    def _create_deliveries_for_contact(self, contact, anchor=None, partner=None):
        if not self._is_contact_subscribed(contact):
            return self.env[self._name]
        stages = self.env['diligence.newsletter.stage'].sudo().search([
            ('active', '=', True),
        ])
        anchor = anchor or fields.Datetime.now()
        partner = partner or self._partner_for_contact(contact)
        created = self.env[self._name]
        for stage in stages:
            domain = [
                ('stage_id', '=', stage.id),
                '|', ('mailing_contact_id', '=', contact.id),
                ('partner_id', '=', partner.id if partner else 0),
            ]
            existing = self.sudo().search(domain, limit=1)
            if existing:
                # Link legacy partner-based deliveries to the public contact
                # when both records represent the same email address.
                if partner and existing.partner_id == partner and not existing.mailing_contact_id:
                    existing.write({'mailing_contact_id': contact.id})
                # Keep an existing pending date intact. It may have been
                # deliberately rescheduled by an operator or a test; the
                # subscription anchor is applied when the delivery is first
                # created and must not overwrite that decision on every cron.
                continue
            created |= self.sudo().create({
                'partner_id': partner.id if partner else False,
                'mailing_contact_id': contact.id,
                'stage_id': stage.id,
                'scheduled_date': anchor + timedelta(days=stage.delay_days),
            })
        return created

    @api.model
    def _ensure_deliveries(self):
        mailing_list = self._newsletter_list()
        if not mailing_list:
            return
        subscriptions = self.env['mailing.subscription'].sudo().search([
            ('list_id', '=', mailing_list.id),
            ('opt_out', '=', False),
            ('contact_id.email', '!=', False),
        ])
        for subscription in subscriptions:
            contact = subscription.contact_id
            partner = self._partner_for_contact(contact)
            # The drip timeline belongs to this newsletter subscription, not to
            # the partner account. An existing Odoo account may subscribe much
            # later, and using partner.create_date would make all overdue
            # stages eligible in the same cron run.
            anchor = subscription.create_date or contact.create_date or fields.Datetime.now()
            self._create_deliveries_for_contact(contact, anchor=anchor, partner=partner)

    def _defer_following_deliveries(self, delivery, sent_at):
        """Keep overdue stages from being sent back-to-back for one recipient.

        A subscriber created before the drip was configured can have all stages
        overdue at once. The first due stage is sent, while later stages are
        spaced from the actual send time using their configured delay.
        """
        recipient_domain = (
            [('mailing_contact_id', '=', delivery.mailing_contact_id.id)]
            if delivery.mailing_contact_id else
            [('partner_id', '=', delivery.partner_id.id)]
        )
        later_stages = self.env['diligence.newsletter.stage'].sudo().search([
            ('active', '=', True),
            ('sequence', '>', delivery.stage_id.sequence),
        ], order='sequence, id')
        if not later_stages:
            return
        for stage in later_stages:
            next_delivery = self.sudo().search([
                *recipient_domain,
                ('stage_id', '=', stage.id),
                ('state', 'in', ('pending', 'failed')),
            ], limit=1)
            if not next_delivery:
                continue
            delay = max(0, stage.delay_days - delivery.stage_id.delay_days)
            next_date = sent_at + timedelta(days=delay)
            if next_delivery.scheduled_date < next_date:
                next_delivery.write({'scheduled_date': next_date})

    @api.model
    def _cron_process(self):
        self._ensure_unsubscribe_footer()
        self._ensure_deliveries()
        now = fields.Datetime.now()
        deliveries = self.sudo().search([
            ('state', 'in', ('pending', 'failed')),
            ('scheduled_date', '<=', now),
            ('attempt_count', '<', 3),
        ], order='scheduled_date, id', limit=100)
        processed_recipients = set()
        test_mode = self.env['ir.config_parameter'].sudo().get_param(
            'diligence.email_test_mode', 'True',
        ).lower() in ('1', 'true', 'yes', 'on')
        for delivery in deliveries:
            delivery.invalidate_recordset(['scheduled_date', 'state', 'attempt_count'])
            if delivery.scheduled_date > now:
                continue
            if not delivery.email:
                delivery.write({'state': 'skipped', 'last_error': _('Subscriber has no email address.')})
                continue
            if delivery.mailing_contact_id:
                subscribed = self._is_contact_subscribed(delivery.mailing_contact_id)
            else:
                subscribed = delivery.partner_id.diligence_newsletter_opt_in and self._is_subscribed(delivery.partner_id)
            if not subscribed:
                delivery.write({'state': 'skipped', 'last_error': _('Student is not subscribed.')})
                continue
            # Use the normalized address so duplicate legacy contacts cannot
            # cause multiple stages to be sent in the same cron cycle.
            recipient_key = ('email', delivery.email.strip().lower()) if delivery.email else (
                'contact', delivery.mailing_contact_id.id
            ) if delivery.mailing_contact_id else ('partner', delivery.partner_id.id)
            if recipient_key in processed_recipients:
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
                processed_recipients.add(recipient_key)
                self._defer_following_deliveries(delivery, now)
            except Exception as error:
                error_type = type(error).__name__
                _logger.error('Newsletter drip failed for delivery %s (%s)', delivery.id, error_type)
                delivery.write({
                    'state': 'failed',
                    'attempt_count': delivery.attempt_count + 1,
                    'last_error': _('Delivery failed (%s).') % error_type,
                })
        return True
