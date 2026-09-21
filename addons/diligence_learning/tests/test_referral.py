from odoo.tests.common import TransactionCase


class TestDiligenceReferralTracking(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.affiliate = cls.env['res.partner'].create({'name': 'Referral Affiliate Test'})
        cls.student = cls.env['res.partner'].create({'name': 'Referral Student Test'})
        cls.order = cls.env['sale.order'].create({'partner_id': cls.student.id})
        cls.referral_model = cls.env['diligence.referral']

    def test_cashback_remaining_until_paid(self):
        referral = self.referral_model.create({
            'affiliate_id': self.affiliate.id,
            'student_id': self.student.id,
            'sale_order_id': self.order.id,
            'referral_code': 'TEST-TRACKING',
            'cashback_amount': 125000,
            'status': 'pending_payment',
        })
        self.assertEqual(referral.cashback_paid_amount, 0)
        self.assertEqual(referral.cashback_remaining_amount, 125000)
        self.assertEqual(referral.cashback_tracking_status, 'pending_payment')

        referral.write({'status': 'ready_to_pay'})
        self.assertEqual(referral.cashback_remaining_amount, 125000)
        self.assertEqual(referral.cashback_tracking_status, 'pending_payout')

        referral.write({'status': 'paid'})
        self.assertEqual(referral.cashback_paid_amount, 125000)
        self.assertEqual(referral.cashback_remaining_amount, 0)
        self.assertEqual(referral.cashback_tracking_status, 'paid')

    def test_cancelled_or_reversed_cashback_is_not_outstanding(self):
        referral = self.referral_model.create({
            'affiliate_id': self.affiliate.id,
            'student_id': self.student.id,
            'sale_order_id': self.order.id,
            'referral_code': 'TEST-CANCELLED',
            'cashback_amount': 50000,
            'status': 'cancelled',
        })
        self.assertEqual(referral.cashback_paid_amount, 0)
        self.assertEqual(referral.cashback_remaining_amount, 0)
        self.assertEqual(referral.cashback_tracking_status, 'cancelled')

    def test_settlement_totals_show_paid_and_remaining_cashback(self):
        first = self.referral_model.create({
            'affiliate_id': self.affiliate.id,
            'student_id': self.student.id,
            'sale_order_id': self.order.id,
            'referral_code': 'TEST-SETTLEMENT-1',
            'cashback_amount': 100000,
            'status': 'ready_to_pay',
        })
        second_order = self.env['sale.order'].create({'partner_id': self.student.id})
        second = self.referral_model.create({
            'affiliate_id': self.affiliate.id,
            'student_id': self.student.id,
            'sale_order_id': second_order.id,
            'referral_code': 'TEST-SETTLEMENT-2',
            'cashback_amount': 50000,
            'status': 'paid',
        })
        settlement = self.env['diligence.referral.settlement'].create({
            'affiliate_id': self.affiliate.id,
            'period_start': '2026-09-01',
            'period_end': '2026-09-30',
            'referral_ids': [(6, 0, (first | second).ids)],
        })
        self.assertEqual(settlement.total_cashback_paid, 50000)
        self.assertEqual(settlement.total_cashback_remaining, 100000)
        self.assertEqual(settlement.pending_referral_count, 1)
