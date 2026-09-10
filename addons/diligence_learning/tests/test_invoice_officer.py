from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import AccessError
from odoo.tests import tagged


@tagged('-at_install', 'post_install')
class TestDiligenceInvoiceOfficer(AccountTestInvoicingCommon):
    """Verify the least-privilege invoice officer view."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.officer_group = cls.env.ref(
            'diligence_learning.group_diligence_invoice_officer'
        )
        cls.officer = cls.env['res.users'].create({
            'name': 'Diligence Invoice Officer E2E',
            'login': 'diligence-invoice-officer-e2e@example.com',
            'email': 'diligence-invoice-officer-e2e@example.com',
            'group_ids': [Command.set([
                cls.env.ref('base.group_user').id,
                cls.officer_group.id,
            ])],
        })

    def _create_test_invoice(self):
        return self._create_invoice_one_line(
            price_unit=100,
            product_id=self.product_a,
            tax_ids=[],
            post=True,
        )

    def _pay_invoice(self, invoice):
        journal = self.company_data['default_journal_bank']
        payment_line = journal.inbound_payment_method_line_ids.filtered(
            lambda line: line.payment_method_id.code == 'manual'
        )[:1]
        payment = self.env['account.payment'].create({
            'amount': invoice.amount_residual,
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': invoice.partner_id.id,
            'journal_id': journal.id,
            'payment_method_line_id': payment_line.id,
            'invoice_ids': [Command.set(invoice.ids)],
        })
        payment.action_post()
        receivable_lines = (invoice.line_ids | payment.move_id.line_ids).filtered(
            lambda line: line.account_id.account_type == 'asset_receivable'
            and not line.reconciled
        )
        receivable_lines.reconcile()
        self.assertEqual(invoice.payment_state, 'paid')

    def test_officer_sees_unpaid_but_not_paid_and_cannot_write(self):
        unpaid = self._create_test_invoice()
        paid = self._create_test_invoice()
        self._pay_invoice(paid)

        officer_moves = self.env['account.move'].with_user(self.officer).search([
            ('move_type', '=', 'out_invoice'),
        ])
        self.assertIn(unpaid, officer_moves)
        self.assertNotIn(paid, officer_moves)
        self.assertEqual(unpaid.payment_state, 'not_paid')
        self.assertEqual(paid.payment_state, 'paid')

        with self.assertRaises(AccessError):
            unpaid.with_user(self.officer).write({'ref': 'not allowed'})
