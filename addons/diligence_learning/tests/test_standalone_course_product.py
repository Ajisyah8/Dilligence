from odoo.tests.common import TransactionCase


class TestDiligenceStandaloneCourseProduct(TransactionCase):

    def setUp(self):
        super().setUp()
        self.course = self.env['slide.channel'].create({'name': 'Advanced Mandarin Standalone Test'})
        self.partner = self.env['res.partner'].create({
            'name': 'Standalone Course Student',
            'email': 'standalone-course-student@example.com',
        })

    def _product(self, **values):
        return self.env['product.template'].create({
            'name': 'Advanced Mandarin Course',
            'type': 'service',
            'sale_ok': True,
            'list_price': 250000,
            'diligence_course_ids': [(4, self.course.id)],
            **values,
        })

    def test_course_product_without_package_type_is_standalone(self):
        product = self._product()

        self.assertTrue(product._diligence_is_standalone_course_product())
        self.assertTrue(product._diligence_is_course_access_product())
        self.assertFalse(product._diligence_is_package())

    def test_native_odoo_course_product_is_detected_for_buy_now(self):
        product = self._product(
            name='Standalone Native Course',
            service_tracking='course',
            is_published=True,
        )
        self.course.write({'product_id': product.product_variant_id.id})

        self.assertTrue(product._diligence_is_standalone_course_product())
        self.assertEqual(self.course._diligence_standalone_product(), product.product_variant_id)

    def test_course_access_product_maps_to_the_linked_course(self):
        product = self._product()
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': product.product_variant_id.id,
                'product_uom_qty': 1,
            })],
        })

        order._diligence_grant_package_access()

        membership = self.env['slide.channel.partner'].search([
            ('channel_id', '=', self.course.id),
            ('partner_id', '=', self.partner.id),
        ], limit=1)
        self.assertTrue(membership)
        self.assertEqual(membership.diligence_package_id, product)

    def test_package_with_course_mapping_is_not_standalone(self):
        product = self._product(
            name='Starter package',
            diligence_package_type='starter',
        )

        self.assertTrue(product._diligence_is_package())
        self.assertFalse(product._diligence_is_standalone_course_product())
        self.assertTrue(self.course._diligence_has_package_product())

    def test_price_period_label_uses_access_duration(self):
        product = self._product(diligence_access_duration_days=30)
        self.assertEqual(product._diligence_price_period_label(), '/ 30 days')

        product.diligence_access_duration_days = 365
        self.assertEqual(product._diligence_price_period_label(), '/ 1 year')

        product.diligence_access_duration_days = 75
        self.assertEqual(product._diligence_price_period_label(), '/ 75 days')

        product.diligence_access_duration_days = 400
        self.assertEqual(product._diligence_price_period_label(), '/ 1 year 1 month 5 days')

        product.diligence_access_duration_days = 730
        self.assertEqual(product._diligence_price_period_label(), '/ 2 years')

        product.diligence_access_duration_days = 0
        self.assertFalse(product._diligence_price_period_label())
