import base64
import io

from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase
from odoo.tools import file_open
from odoo.tools.pdf import PdfFileReader


class TestDiligenceBulkPdfUpload(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager_group = cls.env.ref('website_slides.group_website_slides_manager')
        cls.user_group = cls.env.ref('base.group_user')
        cls.manager = cls.env['res.users'].create({
            'name': 'Bulk PDF Manager',
            'login': 'bulk-pdf-manager@example.com',
            'email': 'bulk-pdf-manager@example.com',
            'group_ids': [Command.set([cls.user_group.id, cls.manager_group.id])],
        })
        cls.student = cls.env['res.users'].create({
            'name': 'Bulk PDF Student',
            'login': 'bulk-pdf-student@example.com',
            'email': 'bulk-pdf-student@example.com',
            'group_ids': [Command.set([cls.user_group.id])],
        })
        cls.course = cls.env['slide.channel'].create({'name': 'Bulk PDF Test Course'})
        cls.section = cls.env['slide.slide'].create({
            'name': 'Bulk PDF Test Section',
            'channel_id': cls.course.id,
            'is_category': True,
            'sequence': 1,
        })
        cls.pdf = file_open('base/tests/minimal.pdf', 'rb').read()
        if not cls.pdf or PdfFileReader(io.BytesIO(cls.pdf)).getNumPages() < 1:
            raise AssertionError('The Odoo minimal PDF fixture is not readable.')
        cls.audio = b'ID3\x04\x00\x00\x00\x00\x00\x00' + (b'fake-audio-frame' * 8)

    def _wizard(self, names_and_contents=None, section=False):
        wizard = self.env['diligence.bulk.pdf.upload'].with_user(self.manager).create({
            'course_id': self.course.id,
            'section_id': self.section.id if section else False,
        })
        names_and_contents = names_and_contents or [('Lesson 01.pdf', self.pdf)]
        attachments = self.env['ir.attachment'].with_user(self.manager).create([
            {
                'name': name,
                'datas': base64.b64encode(content),
                'mimetype': mimetype,
                'res_model': wizard._name,
                'res_id': wizard.id,
            }
            for name, content, mimetype in [
                (name, content, 'application/pdf' if name.lower().endswith('.pdf') else 'audio/mpeg')
                for name, content in names_and_contents
            ]
        ])
        wizard.attachment_ids = [Command.set(attachments.ids)]
        return wizard

    def test_upload_creates_unpublished_pdf_lessons(self):
        wizard = self._wizard([
            ('Lesson %02d.pdf' % index, self.pdf + (b'\n' * index))
            for index in range(1, 11)
        ])
        wizard.action_upload()
        slides = self.course.slide_ids.filtered(
            lambda slide: slide.name.startswith('Lesson ')
        )
        self.assertEqual(len(slides), 10)
        self.assertTrue(all(slide.slide_category == 'document' for slide in slides))
        self.assertTrue(all(slide.source_type == 'local_file' for slide in slides))
        self.assertTrue(all(not slide.is_published for slide in slides))
        self.assertTrue(all(slide.binary_content for slide in slides))
        self.assertEqual(wizard.line_ids.mapped('state'), ['uploaded'] * 10)

    def test_duplicate_checksum_is_skipped_without_new_slide(self):
        first = self._wizard([('Duplicate.pdf', self.pdf)])
        first.action_upload()
        before = len(self.course.slide_ids)
        second = self._wizard([('Same-content-different-name.pdf', self.pdf)])
        second.action_upload()
        self.assertEqual(len(self.course.slide_ids), before)
        self.assertEqual(second.line_ids.state, 'duplicate')

    def test_upload_creates_unpublished_audio_lesson(self):
        wizard = self._wizard([('Listening 01.mp3', self.audio)])
        wizard.action_upload()
        slide = self.course.slide_ids.filtered(lambda item: item.name == 'Listening 01')
        self.assertEqual(len(slide), 1)
        self.assertEqual(slide.slide_category, 'audio')
        self.assertEqual(slide.source_type, 'local_file')
        self.assertFalse(slide.is_published)
        self.assertEqual(slide.diligence_audio_filename, 'Listening 01.mp3')
        self.assertTrue(slide.binary_content)
        self.assertEqual(wizard.line_ids.content_type, 'audio')

    def test_invalid_files_are_reported_and_not_created(self):
        wizard = self._wizard([
            ('not-a-pdf.jpg', b'not a pdf'),
            ('empty.pdf', b''),
            ('broken.pdf', b'%PDF-1.7 but incomplete'),
        ])
        wizard.action_upload()
        self.assertEqual(len(self.course.slide_ids), 1)  # the category only
        self.assertEqual(set(wizard.line_ids.mapped('state')), {'failed'})
        self.assertFalse(wizard.attachment_ids)

    def test_maximum_batch_size_is_enforced(self):
        wizard = self._wizard([
            ('lesson-%02d.pdf' % index, self.pdf)
            for index in range(51)
        ])
        with self.assertRaises(UserError):
            wizard.action_upload()

    def test_only_elearning_manager_can_upload(self):
        wizard = self._wizard()
        with self.assertRaises(AccessError):
            wizard.with_user(self.student).action_upload()
