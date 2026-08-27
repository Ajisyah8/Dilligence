from unittest.mock import patch

from odoo import Command
from odoo.addons.payment_custom.tests.common import PaymentCustomCommon
from odoo.exceptions import AccessError
from odoo.tests import tagged


@tagged('-at_install', 'post_install')
class TestDiligenceAutomaticInvoice(PaymentCustomCommon):
    """Regression coverage for the standard sale/payment invoice flow.

    The test intentionally exercises Odoo's standard ``_post_process`` instead
    of duplicating invoice creation in the Diligence module.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.provider = cls._prepare_provider(code='custom', custom_mode='wire_transfer')
        cls.product = cls.env['product.product'].create({
            'name': 'Diligence invoice test package',
            'type': 'service',
            'invoice_policy': 'order',
            'list_price': 129000,
            'diligence_package_type': 'starter',
        })

    def _create_order(self):
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [Command.create({
                'product_id': self.product.id,
                'product_uom_qty': 1,
            })],
        })
        return order

    def _create_done_transaction(self, order, amount=None, state='done'):
        return self._create_transaction(
            flow='direct',
            amount=order.amount_total if amount is None else amount,
            sale_order_ids=[order.id],
            state=state,
            reference=f'Diligence invoice test {order.id}',
        )

    def test_pending_and_failed_payment_do_not_invoice(self):
        pending_order = self._create_order()
        pending_tx = self._create_done_transaction(pending_order, state='pending')
        pending_tx._post_process()
        self.assertFalse(pending_order.invoice_ids)
        self.assertEqual(pending_order.state, 'sent')

        failed_order = self._create_order()
        failed_tx = self._create_done_transaction(failed_order, state='pending')
        failed_tx._set_error('Test failure')
        failed_tx._post_process()
        self.assertFalse(failed_order.invoice_ids)
        self.assertEqual(failed_order.state, 'draft')

    def test_custom_payment_callback_stays_pending_until_verification(self):
        tx = self._create_transaction(flow='direct')
        tx._apply_updates({})
        self.assertEqual(tx.state, 'pending')
        self.assertTrue(tx.last_state_change)

    def test_only_finance_can_verify_bank_transfer(self):
        tx = self._create_transaction(flow='direct', state='pending')
        portal_user = self.env['res.users'].sudo().create({
            'name': 'Diligence Portal Payment Tester',
            'login': 'diligence-payment-portal@example.com',
            'email': 'diligence-payment-portal@example.com',
            'group_ids': [Command.set([self.env.ref('base.group_portal').id])],
        })
        with self.assertRaises(AccessError):
            tx.with_user(portal_user).action_diligence_verify_payment()

        with patch('odoo.addons.diligence_learning.models.payment_transaction.PaymentTransaction._post_process'):
            tx.action_diligence_verify_payment()
        self.assertEqual(tx.state, 'done')

    def test_mismatched_payment_does_not_confirm_or_invoice(self):
        order = self._create_order()
        self.assertGreater(order.amount_total, 0, 'The test order must have a non-zero total.')
        tx = self._create_done_transaction(order, amount=order.amount_total - 1)
        tx._post_process()
        self.assertEqual(order.state, 'draft',
                         'amount_total=%s, tx_amount=%s, amount_paid=%s' %
                         (order.amount_total, tx.amount, order.amount_paid))
        self.assertFalse(order.invoice_ids,
                         'amount_total=%s, tx_amount=%s, amount_paid=%s' %
                         (order.amount_total, tx.amount, order.amount_paid))

    def test_done_payment_creates_one_exact_invoice_and_is_idempotent(self):
        self.env['ir.config_parameter'].sudo().set_param('sale.automatic_invoice', 'True')
        order = self._create_order()
        self.assertGreater(order.amount_total, 0, 'The test order must have a non-zero total.')
        tx = self._create_done_transaction(order)

        # Invoice mail generation is outside this test and can require the
        # optional wkhtmltopdf binary on a developer workstation.
        with patch('odoo.addons.sale.models.payment_transaction.PaymentTransaction._send_invoice'):
            tx._post_process()
            tx._post_process()

        self.assertEqual(order.state, 'sale')
        self.assertEqual(len(tx.invoice_ids), 1,
                         'amount_total=%s, tx_amount=%s, amount_paid=%s, '
                         'order_invoices=%s, invoice_status=%s' %
                         (order.amount_total, tx.amount, order.amount_paid,
                          order.invoice_ids.ids, order.invoice_status))
        self.assertAlmostEqual(tx.invoice_ids.amount_total, order.amount_total)
        self.assertEqual(tx.invoice_ids.partner_id, order.partner_id)
