from odoo.tests.common import TransactionCase


class TestDiligenceContactSegments(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Partner = cls.env['res.partner']
        cls.Segment = cls.env['diligence.contact.segment']
        cls.student = cls.env.ref('diligence_learning.diligence_contact_segment_student')
        cls.customer = cls.env.ref('diligence_learning.diligence_contact_segment_customer')

    def test_partner_can_belong_to_multiple_segments(self):
        partner = self.Partner.create({
            'name': 'Multi Segment Test',
            'email': 'multi-segment@example.com',
            'diligence_contact_segment_ids': [(6, 0, [self.student.id, self.customer.id])],
        })
        self.assertEqual(partner.diligence_contact_segment_ids, self.student | self.customer)

    def test_course_creates_a_contact_segment(self):
        course = self.env['slide.channel'].create({'name': 'Mandarin Course Segment Test'})
        self.assertTrue(course.diligence_contact_segment_id)
        self.assertEqual(course.diligence_contact_segment_id.name, course.name)
        self.assertTrue(course.diligence_contact_segment_id.code.startswith('course_mandarin-course-segment-test_'))

    def test_package_access_adds_course_segment_to_student(self):
        course = self.env['slide.channel'].create({'name': 'Paid Mandarin Course'})
        partner = self.Partner.create({'name': 'Paid Course Student', 'email': 'paid-course@example.com'})
        package = self.env['product.template'].create({
            'name': 'Paid Mandarin Package',
            'type': 'service',
            'list_price': 129000,
            'diligence_package_type': 'starter',
            'diligence_course_ids': [(4, course.id)],
        })
        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_line': [(0, 0, {
                'product_id': package.product_variant_id.id,
                'product_uom_qty': 1,
            })],
        })
        order._diligence_grant_package_access()
        self.assertIn(course.diligence_contact_segment_id, partner.diligence_contact_segment_ids)
        self.assertTrue(self.env['slide.channel.partner'].search([
            ('channel_id', '=', course.id), ('partner_id', '=', partner.id),
        ]))

    def test_survey_segment_loader_uses_multiple_segments(self):
        first = self.Partner.create({'name': 'Mandarin Test', 'email': 'mandarin@example.com'})
        second = self.Partner.create({'name': 'English Test', 'email': 'english@example.com'})
        mandarin = self.Segment.create({'name': 'Mandarin Course', 'code': 'mandarin_course'})
        english = self.Segment.create({'name': 'English Course', 'code': 'english_course'})
        first.write({'diligence_contact_segment_ids': [(4, mandarin.id)]})
        second.write({'diligence_contact_segment_ids': [(4, english.id)]})
        survey = self.env['survey.survey'].create({'title': 'Segment Test Survey'})
        wizard = self.env['survey.invite'].create({
            'survey_id': survey.id,
            'diligence_segment_ids': [(6, 0, [mandarin.id, english.id])],
        })
        self.assertEqual(wizard._diligence_segment_partners(), first | second)
        wizard.action_load_diligence_segment()
        self.assertEqual(wizard.partner_ids, first | second)

    def test_survey_send_uses_only_loaded_segment_recipients(self):
        student = self.Partner.create({
            'name': 'Student Recipient',
            'email': 'student-recipient@example.com',
            'diligence_contact_segment_ids': [(4, self.student.id)],
        })
        other = self.Partner.create({
            'name': 'Other Recipient',
            'email': 'other-recipient@example.com',
            'diligence_contact_segment_ids': [(4, self.customer.id)],
        })
        survey = self.env['survey.survey'].create({
            'title': 'Segment Delivery E2E',
            'access_mode': 'token',
        })
        wizard = self.env['survey.invite'].create({
            'survey_id': survey.id,
            'diligence_segment_ids': [(6, 0, [self.student.id])],
        })
        expected_recipients = wizard._diligence_segment_partners()
        wizard.action_load_diligence_segment()
        self.assertEqual(wizard.partner_ids, expected_recipients)
        self.assertNotIn(other, wizard.partner_ids)
        wizard.partner_ids = [(4, other.id)]

        before_ids = set(survey.user_input_ids.ids)
        wizard.action_invite()
        new_answers = survey.user_input_ids.filtered(lambda answer: answer.id not in before_ids)
        self.assertEqual(new_answers.mapped('partner_id'), expected_recipients)
        self.assertNotIn(other, new_answers.mapped('partner_id'))
