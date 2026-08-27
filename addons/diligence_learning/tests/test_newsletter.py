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
        delivery = delivery_model.search([('partner_id', '=', partner.id)], limit=1)
        self.assertEqual(delivery.state, 'pending')
        delivery_model._cron_process()
        delivery.invalidate_recordset()
        self.assertEqual(delivery.state, 'pending')
        self.assertEqual(delivery.attempt_count, 0)
        self.assertIn('test mode', delivery.last_error.lower())
