from datetime import timedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestCoachingCapacityAndEventType(TransactionCase):

    def test_slot_capacity_counts_each_booked_participant(self):
        package = self.env['product.template'].create({
            'name': 'Capacity Test Coaching Package',
            'diligence_consultation': True,
        })
        start = fields.Datetime.now() + timedelta(days=3)
        slot = self.env['diligence.session'].create({
            'name': 'Two Person Coaching Slot',
            'package_id': package.id,
            'session_type': 'one_on_one',
            'start_datetime': start,
            'end_datetime': start + timedelta(hours=1),
            'capacity': 2,
            'state': 'scheduled',
            'student_booking_open': True,
        })
        booker = self.env['res.partner'].create({'name': 'Booking Student'})
        self.env['diligence.session.attendee'].create([
            {
                'session_id': slot.id,
                'partner_id': booker.id,
                'booking_partner_id': booker.id,
                'participant_name': 'Booking Student',
            },
            {
                'session_id': slot.id,
                'booking_partner_id': booker.id,
                'participant_name': 'Friend Student',
                'student_code': 'TEST-002',
            },
        ])
        self.assertEqual(slot.attendee_count, 2)
        self.assertEqual(slot.seats_available, 0)
        with self.assertRaises(ValidationError):
            with self.env.cr.savepoint():
                self.env['diligence.session.attendee'].create({
                    'session_id': slot.id,
                    'participant_name': 'Extra Student',
                })

    def test_duplicate_slot_resets_booking_and_zoom_data(self):
        package = self.env['product.template'].create({
            'name': 'Duplicate Test Coaching Package',
            'diligence_consultation': True,
        })
        start = fields.Datetime.now() + timedelta(days=3)
        student = self.env['res.partner'].create({'name': 'Duplicate Test Student'})
        slot = self.env['diligence.session'].create({
            'name': 'Coaching 16:30',
            'package_id': package.id,
            'session_type': 'one_on_one',
            'start_datetime': start,
            'end_datetime': start + timedelta(minutes=15),
            'coach_id': self.env.user.id,
            'capacity': 3,
            'state': 'scheduled',
            'student_booking_open': True,
            'meeting_url': 'https://zoom.us/j/old-meeting',
            'zoom_meeting_id': 'old-meeting',
            'zoom_password': 'secret',
            'zoom_start_url': 'https://zoom.us/s/host-old-meeting',
            'zoom_created': True,
        })
        self.env['diligence.session.attendee'].create({
            'session_id': slot.id,
            'partner_id': student.id,
            'participant_name': student.name,
        })

        action = slot.action_duplicate_slot()
        duplicate = self.env['diligence.session'].browse(action['res_id'])

        self.assertEqual(action['res_model'], 'diligence.session')
        self.assertEqual(duplicate.name, 'Coaching 16:30 (copy)')
        self.assertEqual(duplicate.start_datetime, slot.start_datetime)
        self.assertEqual(duplicate.end_datetime, slot.end_datetime)
        self.assertEqual(duplicate.capacity, 3)
        self.assertEqual(duplicate.state, 'draft')
        self.assertFalse(duplicate.student_booking_open)
        self.assertFalse(duplicate.attendee_ids)
        self.assertFalse(duplicate.meeting_url)
        self.assertFalse(duplicate.zoom_meeting_id)
        self.assertFalse(duplicate.zoom_password)
        self.assertFalse(duplicate.zoom_start_url)
        self.assertFalse(duplicate.zoom_created)

    def test_booking_one_slot_keeps_other_open_slots_available(self):
        package = self.env['product.template'].create({
            'name': 'Multiple Slot Coaching Package',
            'diligence_consultation': True,
        })
        start = fields.Datetime.now() + timedelta(days=3)
        student = self.env['res.partner'].create({'name': 'Booked Student'})
        another_student = self.env['res.partner'].create({'name': 'Another Student'})
        Slot = self.env['diligence.session']
        first_slot = Slot.create({
            'name': 'Coaching 16:30', 'package_id': package.id,
            'session_type': 'one_on_one', 'start_datetime': start,
            'end_datetime': start + timedelta(minutes=15), 'capacity': 3,
            'state': 'scheduled', 'student_booking_open': True,
        })
        second_slot = Slot.create({
            'name': 'Coaching 16:45', 'package_id': package.id,
            'session_type': 'one_on_one', 'start_datetime': start + timedelta(minutes=15),
            'end_datetime': start + timedelta(minutes=30), 'capacity': 3,
            'state': 'scheduled', 'student_booking_open': True,
        })
        self.env['diligence.session.attendee'].create({
            'session_id': first_slot.id,
            'partner_id': student.id,
            'booking_partner_id': student.id,
            'participant_name': student.name,
        })

        student_slots = Slot.get_student_bookable_slots(student, package)
        other_student_slots = Slot.get_student_bookable_slots(another_student, package)

        self.assertNotIn(first_slot, student_slots)
        self.assertIn(second_slot, student_slots)
        self.assertIn(first_slot, other_student_slots)
        self.assertIn(second_slot, other_student_slots)

    def test_event_registrations_can_be_classified(self):
        event = self.env['event.event'].create({
            'name': 'Participant Type Test Event',
            'date_begin': fields.Datetime.now() + timedelta(days=2),
            'date_end': fields.Datetime.now() + timedelta(days=2, hours=1),
        })
        general_partner = self.env['res.partner'].create({
            'name': 'General Participant',
            'email': 'general-participant@example.com',
            'diligence_contact_segment': 'other',
        })
        student_partner = self.env['res.partner'].create({
            'name': 'Student Participant',
            'email': 'student-participant@example.com',
            'diligence_contact_segment': 'student',
        })
        general = self.env['event.registration'].create({
            'event_id': event.id,
            'name': 'General Participant',
            'email': 'general-participant@example.com',
            'partner_id': general_partner.id,
        })
        student = self.env['event.registration'].create({
            'event_id': event.id,
            'name': 'Student Participant',
            'email': 'student-participant@example.com',
            'partner_id': student_partner.id,
        })
        self.assertEqual(general.diligence_participant_type, 'general')
        self.assertEqual(student.diligence_participant_type, 'student')

    def test_import_defers_after_subscription_email_until_commit(self):
        start = fields.Datetime.now() + timedelta(days=2)
        template = self.env.ref('event.event_registration_mail_template_badge')
        event = self.env['event.event'].create({
            'name': 'Import Scheduler Test Event',
            'date_begin': start,
            'date_end': start + timedelta(hours=1),
            'event_mail_ids': [(0, 0, {
                'interval_unit': 'now',
                'interval_type': 'after_sub',
                'template_ref': 'mail.template,%s' % template.id,
            })],
        })
        partner = self.env['res.partner'].create({
            'name': 'Import Scheduler Test Participant',
            'email': 'import-scheduler-test@example.com',
        })

        with self.capture_triggers('event.event_mail_scheduler') as captured:
            registration = self.env['event.registration'].with_context(import_file=True).create({
                'event_id': event.id,
                'partner_id': partner.id,
                'name': partner.name,
                'email': partner.email,
            })

        self.assertTrue(registration)
        self.assertEqual(len(captured.records), 1)
        self.assertFalse(registration.mail_registration_ids)
        self.assertFalse(self.env['mail.mail'].search([
            ('model', '=', 'event.registration'),
            ('res_id', '=', registration.id),
        ]))

    def test_teacher_contact_can_be_selected_as_learning_session_coach(self):
        teacher_segment = self.env['diligence.contact.segment'].search([
            ('code', '=', 'teacher'),
        ], limit=1)
        if not teacher_segment:
            teacher_segment = self.env['diligence.contact.segment'].create({
                'name': 'Teacher Test Segment',
                'code': 'teacher',
            })
        teacher = self.env['res.partner'].create({
            'name': 'Teacher Contact',
            'diligence_contact_segment_ids': [(4, teacher_segment.id)],
        })
        package = self.env['product.template'].create({
            'name': 'Teacher Contact Coaching Package',
            'diligence_package_type': 'consultation',
        })
        start = fields.Datetime.now() + timedelta(days=3)
        session = self.env['diligence.session'].create({
            'name': 'Teacher Contact Coaching Session',
            'package_id': package.id,
            'session_type': 'one_on_one',
            'start_datetime': start,
            'end_datetime': start + timedelta(minutes=15),
            'coach_partner_id': teacher.id,
        })
        self.assertEqual(session.coach_partner_id, teacher)

        non_teacher = self.env['res.partner'].create({'name': 'Non Teacher Contact'})
        with self.assertRaises(ValidationError):
            with self.env.cr.savepoint():
                session.write({'coach_partner_id': non_teacher.id})

    def test_package_grants_membership_for_coming_soon_course(self):
        course = self.env['slide.channel'].create({
            'name': 'Coming Soon Package Course',
            'channel_type': 'training',
            'enroll': 'public',
            'diligence_availability': 'coming_soon',
        })
        package = self.env['product.template'].create({
            'name': 'Three Course Coaching Package',
            'diligence_package_type': 'consultation',
            'diligence_course_ids': [(6, 0, [course.id])],
        })
        student = self.env['res.partner'].create({'name': 'Package Access Student'})
        order = self.env['sale.order'].create({
            'partner_id': student.id,
            'order_line': [(0, 0, {
                'product_id': package.product_variant_id.id,
                'product_uom_qty': 1,
                'price_unit': 100,
            })],
        })

        order._diligence_grant_package_access()

        membership = self.env['slide.channel.partner'].search([
            ('partner_id', '=', student.id),
            ('channel_id', '=', course.id),
        ])
        self.assertTrue(membership)
        self.assertEqual(membership.member_status, 'joined')
