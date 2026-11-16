from odoo.tests.common import TransactionCase


class TestDiligenceCoursePublish(TransactionCase):

    def setUp(self):
        super().setUp()
        self.course = self.env['slide.channel'].create({'name': 'Auto publish test course'})
        self.lesson = self.env['slide.slide'].create({
            'name': 'Draft lesson',
            'channel_id': self.course.id,
            'slide_category': 'video',
            'source_type': 'external',
            'url': 'https://example.com/lesson.mp4',
        })
        self.section = self.env['slide.slide'].create({
            'name': 'Lesson section',
            'channel_id': self.course.id,
            'is_category': True,
        })

    def test_publishing_course_publishes_active_lessons_not_sections(self):
        self.course.write({'website_published': True})

        self.assertTrue(self.lesson.is_published)
        self.assertTrue(self.lesson.website_published)
        self.assertTrue(self.section.is_category)

    def test_unrelated_edit_does_not_publish_later_draft_lesson(self):
        self.course.write({'website_published': True})
        later_lesson = self.env['slide.slide'].create({
            'name': 'Later draft lesson',
            'channel_id': self.course.id,
            'slide_category': 'video',
            'source_type': 'external',
            'url': 'https://example.com/later.mp4',
        })

        self.course.write({'description': '<p>Updated description</p>'})

        self.assertFalse(later_lesson.is_published)
        self.assertFalse(later_lesson.website_published)

    def test_releasing_coming_soon_course_publishes_its_lessons(self):
        self.course.write({'diligence_availability': 'coming_soon', 'website_published': True})
        self.assertFalse(self.lesson.is_published)

        self.course.write({'diligence_availability': 'available'})

        self.assertTrue(self.lesson.is_published)
        self.assertTrue(self.lesson.website_published)

    def test_go_to_website_opens_course_overview(self):
        action = self.course.open_website_url()

        self.assertEqual(
            action['params']['path'],
            f'{self.course.website_url}?overview=1',
        )
