from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests.common import TransactionCase


class TestDiligenceNewsletter(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.newsletter = cls.env['mailing.list'].search([
            ('name', '=', 'Diligence Academy Newsletter'),
        ], limit=1)
        cls.stages = cls.env['diligence.newsletter.stage'].search([])

    def test_opt_in_creates_subscription_and_idempotent_deliveries(self):
        partner = self.env['res.partner'].create({
            'name': 'Newsletter Test Student',
            'email': 'newsletter-test@example.com',
            'diligence_newsletter_opt_in': True,
        })
        contact = self.env['mailing.contact'].search([
            ('email', '=', partner.email),
        ], limit=1)
        self.assertTrue(contact)
        self.assertTrue(contact.subscription_ids.filtered(
            lambda subscription: subscription.list_id == self.newsletter and not subscription.opt_out
        ))

        delivery_model = self.env['diligence.newsletter.delivery']
        delivery_model._ensure_deliveries()
        deliveries = delivery_model.search([('partner_id', '=', partner.id)])
        self.assertEqual(len(deliveries), len(self.stages))

        delivery_model._ensure_deliveries()
        self.assertEqual(
            delivery_model.search_count([('partner_id', '=', partner.id)]),
            len(self.stages),
        )

    def test_unsubscribe_prevents_processing(self):
        partner = self.env['res.partner'].create({
            'name': 'Newsletter Optout Student',
            'email': 'newsletter-optout@example.com',
            'diligence_newsletter_opt_in': True,
        })
        partner.write({'diligence_newsletter_opt_in': False})
        contact = self.env['mailing.contact'].search([
            ('email', '=', partner.email),
        ], limit=1)
        self.assertTrue(contact.subscription_ids.filtered(
            lambda subscription: subscription.list_id == self.newsletter and subscription.opt_out
        ))
        self.env['diligence.newsletter.delivery']._ensure_deliveries()
        self.assertFalse(self.env['diligence.newsletter.delivery'].search([
            ('partner_id', '=', partner.id),
        ]))

    def test_test_mode_does_not_send_or_consume_delivery(self):
        partner = self.env['res.partner'].create({
            'name': 'Newsletter Test Mode Student',
            'email': 'newsletter-test-mode@example.com',
            'diligence_newsletter_opt_in': True,
        })
        delivery_model = self.env['diligence.newsletter.delivery']
        delivery_model._ensure_deliveries()
        self.env['ir.config_parameter'].sudo().set_param('diligence.email_test_mode', 'True')
        delivery = delivery_model.search([('partner_id', '=', partner.id)], limit=1)
        delivery.write({'scheduled_date': fields.Datetime.now()})
        self.assertEqual(delivery.state, 'pending')
        delivery_model._cron_process()
        delivery.invalidate_recordset()
        self.assertEqual(delivery.state, 'pending')
        self.assertEqual(delivery.attempt_count, 0)
        self.assertIn('test mode', delivery.last_error.lower())

    def test_delivery_schedule_uses_subscription_date(self):
        partner = self.env['res.partner'].create({
            'name': 'Newsletter Schedule Student',
            'email': 'newsletter-schedule@example.com',
            'diligence_newsletter_opt_in': True,
        })
        subscription = self.env['mailing.subscription'].search([
            ('contact_id.email', '=', partner.email),
            ('list_id', '=', self.newsletter.id),
        ], limit=1)
        self.assertTrue(subscription)

        delivery_model = self.env['diligence.newsletter.delivery']
        delivery_model._ensure_deliveries()
        anchor = fields.Datetime.to_datetime(
            subscription.create_date or subscription.contact_id.create_date
        )
        for stage in self.stages:
            delivery = delivery_model.search([
                ('partner_id', '=', partner.id),
                ('stage_id', '=', stage.id),
            ], limit=1)
            self.assertEqual(
                fields.Datetime.to_datetime(delivery.scheduled_date),
                anchor + timedelta(days=stage.delay_days),
            )

    def test_overdue_stages_are_not_sent_back_to_back(self):
        partner = self.env['res.partner'].create({
            'name': 'Newsletter Overdue Student',
            'email': 'newsletter-overdue@example.com',
            'diligence_newsletter_opt_in': True,
        })
        contact = self.env['mailing.contact'].search([
            ('email', '=', partner.email),
        ], limit=1)
        subscription = contact.subscription_ids.filtered(
            lambda record: record.list_id == self.newsletter
        )[:1]
        overdue_date = fields.Datetime.now() - timedelta(days=30)
        subscription.write({'create_date': overdue_date})
        contact.write({'create_date': overdue_date})
        delivery_model = self.env['diligence.newsletter.delivery']
        delivery_model._ensure_deliveries()
        self.env['ir.config_parameter'].sudo().set_param('diligence.email_test_mode', 'False')
        with patch.object(type(self.stages[0].template_id), 'send_mail') as send_mail:
            delivery_model._cron_process()
        deliveries = delivery_model.search([
            ('mailing_contact_id', '=', contact.id),
        ], order='stage_id')
        welcome = deliveries.filtered(lambda item: item.stage_id.delay_days == 0)
        first_material = deliveries.filtered(lambda item: item.stage_id.delay_days == 5)
        self.assertEqual(
            len(deliveries.filtered(lambda item: item.state == 'sent')), 1,
        )
        self.assertEqual(welcome.state, 'sent')
        self.assertGreaterEqual(
            fields.Datetime.to_datetime(first_material.scheduled_date),
            fields.Datetime.now() + timedelta(days=4, hours=23),
        )
