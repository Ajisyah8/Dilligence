import base64

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestDiligenceVideoPlayer(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Slide = cls.env['slide.slide']
        cls.channel = cls.env['slide.channel'].create({'name': 'Plyr test course'})

    def test_parse_supported_providers(self):
        parser = self.Slide
        cases = {
            'https://www.youtube.com/watch?v=dQw4w9WgXcQ': ('youtube', 'dQw4w9WgXcQ'),
            'https://youtu.be/dQw4w9WgXcQ': ('youtube', 'dQw4w9WgXcQ'),
            'https://vimeo.com/76979871': ('vimeo', '76979871'),
            'https://media.example.test/lesson.mp4': ('html5', None),
            'https://media.example.test/lesson.webm': ('html5', None),
            'https://media.example.test/lesson.m3u8': ('hls', None),
        }
        for url, expected in cases.items():
            result = parser._diligence_parse_video_url(url)
            self.assertEqual((result.get('provider'), result.get('embed_id')), expected)

    def test_unsupported_provider_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.Slide._diligence_parse_video_url('https://drive.google.com/file/d/example/view')

    def test_local_video_derives_html5_player_metadata(self):
        slide = self.Slide.create({
            'name': 'Test video',
            'channel_id': self.channel.id,
            'slide_category': 'video',
            'source_type': 'local_file',
            'binary_content': base64.b64encode(b'not-a-real-video'),
        })
        self.assertEqual(slide.diligence_video_provider, 'html5')
        self.assertEqual(slide.diligence_video_mime_type, 'video/mp4')
        self.assertIn('/web/content/slide.slide/%s/' % slide.id, slide.diligence_video_player_url)

    def test_audio_replacement_changes_media_cache_key(self):
        first_audio = base64.b64encode(b'first-audio-content')
        second_audio = base64.b64encode(b'second-audio-content')
        slide = self.Slide.create({
            'name': 'Test audio',
            'channel_id': self.channel.id,
            'slide_category': 'audio',
            'source_type': 'local_file',
            'binary_content': first_audio,
        })
        first_key = slide.diligence_audio_cache_key
        slide.write({'binary_content': second_audio})
        slide.invalidate_recordset()
        self.assertTrue(first_key)
        self.assertTrue(slide.diligence_audio_cache_key)
        self.assertNotEqual(first_key, slide.diligence_audio_cache_key)
        slide._compute_embed_code()
        self.assertIn(slide.diligence_audio_cache_key, str(slide.embed_code))

    def test_audio_form_field_persists_upload_as_local_file(self):
        audio = base64.b64encode(b'form-audio-content')
        slide = self.Slide.create({
            'name': 'Test form audio',
            'channel_id': self.channel.id,
            'slide_category': 'audio',
            'source_type': 'external',
            'url': 'https://media.example.test/old.mp3',
        })
        slide.write({
            'diligence_audio_binary_content': audio,
            'diligence_audio_filename': 'replacement.mp3',
        })
        slide.invalidate_recordset()
        self.assertEqual(slide.source_type, 'local_file')
        self.assertEqual(slide.binary_content, audio)
        self.assertEqual(slide.diligence_audio_filename, 'replacement.mp3')
