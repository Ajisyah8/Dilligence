from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestDiligenceOutstandingPaymentAccount(AccountTestInvoicingCommon):
    """Regression tests for payment method line outstanding accounts.

    The test deliberately configures the account on the payment method line.
    It does not use ``account.journal.default_account_id`` as a fallback.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.payment_journal = cls.company_data['default_journal_bank'].copy({
            'name': 'Diligence QRIS test bank',
            'code': 'DQR1',
        })
        cls.payment_line = cls.payment_journal.inbound_payment_method_line_ids.filtered(
            lambda line: line.payment_method_id.code == 'manual'
        )[:1]
        if not cls.payment_line:
            cls.payment_line = cls.payment_journal.inbound_payment_method_line_ids[:1]
        cls.payment_line.payment_account_id = False
        cls.outstanding_account = cls.env['account.account'].create({
            'code': '119901',
            'name': 'Diligence Outstanding QRIS',
            'account_type': 'asset_current',
            'reconcile': True,
            'company_ids': [Command.set([cls.env.company.id])],
        })

    def _create_posted_invoice(self):
        return self._create_invoice_one_line(
            price_unit=100,
            product_id=self.product_a,
            tax_ids=[],
            post=True,
        )

    def _create_payment(self, invoice):
        return self.env['account.payment'].create({
            'amount': invoice.amount_residual,
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': invoice.partner_id.id,
            'journal_id': self.payment_journal.id,
            'payment_method_line_id': self.payment_line.id,
            'invoice_ids': [Command.set(invoice.ids)],
        })

    def test_payment_requires_payment_method_line_account(self):
        invoice = self._create_posted_invoice()
        payment = self._create_payment(invoice)
        self.assertEqual(payment.payment_method_line_id, self.payment_line)
        self.assertEqual(payment.payment_method_line_id.code, 'manual')
        self.assertFalse(payment.payment_method_line_id.payment_account_id)

        with self.assertRaisesRegex(UserError, 'Configure an outstanding account'):
            payment.action_post()

        self.assertFalse(payment.move_id)
        self.assertEqual(invoice.payment_state, 'not_paid')

    def test_payment_uses_configured_outstanding_account(self):
        self.payment_line.payment_account_id = self.outstanding_account
        invoice = self._create_posted_invoice()

        payments = self._create_payment(invoice)
        self.assertEqual(payments.outstanding_account_id, self.outstanding_account)
        payments.action_post()

        self.assertEqual(len(payments), 1)
        self.assertTrue(payments.move_id)
        self.assertEqual(payments.payment_method_line_id, self.payment_line)
        self.assertEqual(payments.move_id.line_ids.filtered(
            lambda line: line.account_id == self.outstanding_account
        ).balance, 100)
