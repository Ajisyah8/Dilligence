import re
from urllib.parse import parse_qs, urlparse

from markupsafe import Markup, escape

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SlideSlide(models.Model):
    _inherit = 'slide.slide'

    def _action_mark_completed(self):
        """Complete media lessons without triggering Odoo quiz validation.

        Odoo's generic implementation always calls ``_action_set_quiz_done``.
        That helper is correct for quiz attempts, but it rejects an admin
        previewing a normal PDF/audio/video lesson when the admin is not a
        student member of the channel.  Keep the native behaviour for quizzes
        and use the same slide-partner completion record for other lessons.
        """
        media_slides = self.filtered(
            lambda slide: slide.slide_category != 'quiz' and not slide.question_ids
        )
        quiz_slides = self - media_slides

        if media_slides:
            uncompleted = media_slides.filtered(lambda slide: not slide.user_has_completed)
            partner = self.env.user.partner_id
            membership_model = self.env['slide.slide.partner'].sudo()
            existing = membership_model.search([
                ('slide_id', 'in', uncompleted.ids),
                ('partner_id', '=', partner.id),
            ])
            existing.write({'completed': True})
            new_slides = uncompleted.sudo() - existing.mapped('slide_id')
            membership_model.create([{
                'slide_id': slide.id,
                'channel_id': slide.channel_id.id,
                'partner_id': partner.id,
                'vote': 0,
                'completed': True,
            } for slide in new_slides])

        if quiz_slides:
            return super(SlideSlide, quiz_slides)._action_mark_completed()
        return True

    quiz_passing_score = fields.Float('Quiz passing score (%)', default=70.0)
    quiz_max_attempts = fields.Integer('Maximum quiz attempts', default=0)
    quiz_randomize_questions = fields.Boolean('Randomize questions')
    quiz_randomize_answers = fields.Boolean('Randomize answers')

    diligence_external_quiz_url = fields.Char('External Quiz / Google Form Link')
    diligence_external_quiz_label = fields.Char(
        'External Quiz Button Label',
        default='Open External Quiz',
    )

    @api.constrains('quiz_passing_score', 'quiz_max_attempts')
    def _check_diligence_quiz_settings(self):
        for slide in self:
            if not 0 <= slide.quiz_passing_score <= 100:
                raise ValidationError(_('Quiz passing score must be between 0 and 100.'))
            if slide.quiz_max_attempts < 0:
                raise ValidationError(_('Maximum quiz attempts cannot be negative.'))

    @api.model_create_multi
    def create(self, vals_list):
        slides = super().create(vals_list)
        slides.filtered(
            lambda slide: slide.slide_category == 'quiz' and slide.diligence_external_quiz_url
        ).write({'is_published': True})
        return slides

    def write(self, values):
        result = super().write(values)
        if 'diligence_external_quiz_url' in values:
            self.filtered(
                lambda slide: slide.slide_category == 'quiz' and slide.diligence_external_quiz_url
            ).write({'is_published': True})
        return result

    video_source_type = fields.Selection(
        selection_add=[('external', 'External Video')],
        ondelete={'external': 'set null'},
    )

    diligence_video_provider = fields.Selection(
        [
            ('youtube', 'YouTube'),
            ('vimeo', 'Vimeo'),
            ('html5', 'HTML5 video'),
            ('hls', 'HLS stream'),
            ('private_hls', 'Private HLS stream'),
        ],
        string='Diligence Video Provider',
        compute='_compute_diligence_video_fields',
        store=True,
        readonly=True,
    )
    diligence_video_embed_id = fields.Char(
        string='Diligence Embed ID',
        compute='_compute_diligence_video_fields',
        store=True,
        readonly=True,
    )
    diligence_video_is_private = fields.Boolean(
        string='Private HLS Video',
        help='Private HLS playback is only enabled for authenticated course members.',
    )
    diligence_video_poster = fields.Image(string='Video Poster', max_width=1920, max_height=1080)
    diligence_video_mime_type = fields.Char(
        string='Video MIME Type', compute='_compute_diligence_video_fields', store=True, readonly=True,
    )
    diligence_video_player_url = fields.Char(
        string='Player Source URL', compute='_compute_diligence_video_fields', store=True, readonly=True,
    )
    diligence_video_embed_url = fields.Char(
        string='Provider Embed URL', compute='_compute_diligence_video_fields', store=True, readonly=True,
    )

    @api.model
    def _diligence_parse_video_url(self, value):
        """Return safe player metadata for an allowlisted URL.

        The original URL remains in Odoo's native ``url``/``video_url`` field;
        this method only derives the provider and embed id used by the player.
        """
        if not value:
            return {}
        parsed = urlparse(value.strip())
        if parsed.scheme not in ('http', 'https') or not parsed.netloc:
            raise ValidationError(_('Video URL must be an absolute HTTP(S) URL.'))
        host = parsed.netloc.lower().split(':', 1)[0]
        path = parsed.path or ''
        if host in ('youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtube-nocookie.com', 'www.youtube-nocookie.com'):
            video_id = parse_qs(parsed.query).get('v', [None])[0]
            if not video_id and path.startswith('/embed/'):
                video_id = path.split('/embed/', 1)[1].split('/', 1)[0]
            if video_id and re.fullmatch(r'[A-Za-z0-9_-]{11}', video_id):
                return {'provider': 'youtube', 'embed_id': video_id, 'mime': 'video/youtube'}
            raise ValidationError(_('This YouTube URL does not contain a valid video ID.'))
        if host in ('youtu.be',):
            video_id = path.strip('/').split('/', 1)[0]
            if re.fullmatch(r'[A-Za-z0-9_-]{11}', video_id):
                return {'provider': 'youtube', 'embed_id': video_id, 'mime': 'video/youtube'}
            raise ValidationError(_('This YouTube short URL does not contain a valid video ID.'))
        if host in ('vimeo.com', 'www.vimeo.com', 'player.vimeo.com'):
            match = re.search(r'(?<!\d)(\d{6,})(?:/([A-Za-z0-9]+))?', path)
            if match:
                embed_id = match.group(1) + (('/' + match.group(2)) if match.group(2) else '')
                return {'provider': 'vimeo', 'embed_id': embed_id, 'mime': 'video/vimeo'}
            raise ValidationError(_('This Vimeo URL does not contain a valid video ID.'))
        if re.search(r'\.m3u8(?:$|[?#])', path, re.I):
            return {
                'provider': 'private_hls' if self.diligence_video_is_private else 'hls',
                'mime': 'application/vnd.apple.mpegurl',
            }
        if re.search(r'\.(?:mp4|webm)(?:$|[?#])', path, re.I):
            return {
                'provider': 'html5',
                'mime': 'video/webm' if path.lower().split('?', 1)[0].endswith('.webm') else 'video/mp4',
            }
        raise ValidationError(_(
            'Unsupported video URL. Use YouTube, Vimeo, MP4, WebM, or an HLS (.m3u8) URL.'
        ))

    @api.depends('slide_category', 'source_type', 'binary_content', 'video_url', 'diligence_video_is_private')
    def _compute_diligence_video_fields(self):
        for slide in self:
            provider = embed_id = mime = player_url = embed_url = False
            if slide.slide_category == 'video' and slide.source_type == 'local_file' and slide.binary_content:
                provider, mime = 'html5', 'video/mp4'
                player_url = '/web/content/slide.slide/%s/binary_content?download=false' % slide.id
            elif slide.slide_category == 'video' and slide.video_url:
                try:
                    metadata = slide._diligence_parse_video_url(slide.video_url)
                except ValidationError:
                    metadata = {}
                provider = metadata.get('provider')
                embed_id = metadata.get('embed_id')
                mime = metadata.get('mime')
                player_url = False if provider == 'private_hls' else slide.video_url
                if provider == 'youtube':
                    embed_url = 'https://www.youtube-nocookie.com/embed/%s?rel=0&playsinline=1' % embed_id
                elif provider == 'vimeo':
                    embed_url = 'https://player.vimeo.com/video/%s?dnt=1' % embed_id.split('/', 1)[0]
            slide.diligence_video_provider = provider
            slide.diligence_video_embed_id = embed_id
            slide.diligence_video_mime_type = mime
            slide.diligence_video_player_url = player_url
            slide.diligence_video_embed_url = embed_url

    @api.constrains('video_url', 'slide_category', 'source_type', 'diligence_video_is_private')
    def _check_diligence_video_url(self):
        for slide in self:
            if slide.slide_category == 'video' and slide.source_type != 'local_file' and slide.video_url:
                slide._diligence_parse_video_url(slide.video_url)

    def _diligence_get_signed_video_url(self):
        """Extension hook for a future private-HLS signer.

        Never return the stored private URL by default: doing so would expose
        an origin URL without an access-controlled signature.
        """
        self.ensure_one()
        return False

    @api.depends('slide_category', 'source_type', 'video_source_type')
    def _compute_slide_type(self):
        super()._compute_slide_type()
        for slide in self:
            if slide.slide_category == 'audio' and slide.source_type == 'external' and slide.url:
                # Reuse Odoo's native audio type so every LMS template renders
                # the built-in audio-file icon consistently.
                slide.slide_type = 'local_audio'

    @api.depends('slide_type', 'slide_category', 'source_type', 'video_source_type')
    def _compute_slide_icon_class(self):
        super()._compute_slide_icon_class()
        for slide in self:
            # Odoo normally derives the icon from ``slide_type``. Draft/local
            # audio and video lessons do not have a slide type until a media
            # file is uploaded, which made their course-list icon fall back to
            # the generic (and visually empty) file icon. The content category
            # is already known, so it is the stable source for these icons.
            if slide.slide_category == 'audio':
                slide.slide_icon_class = 'fa-file-audio-o'
            elif slide.slide_category == 'video':
                slide.slide_icon_class = 'fa-file-video-o'

    @api.depends('slide_category', 'source_type', 'binary_content', 'url', 'google_drive_id',
                 'video_url', 'video_source_type', 'youtube_id', 'vimeo_id')
    def _compute_embed_code(self):
        """Allow course audio to stream from a trusted HTTPS source.

        Standard Odoo eLearning only renders uploaded audio.  Diligence uses
        attributed, externally hosted practice audio, so it needs the same
        player behaviour without copying third-party media into this database.
        """
        super()._compute_embed_code()
        for slide in self.filtered(
            lambda record: record.slide_category == 'audio'
            and record.source_type == 'external'
            and record.url
            and re.match(r'^https://', record.url)
        ):
            slide.embed_code = Markup(
                '<audio controls="controls" preload="metadata" class="w-100" aria-label="%s">'
                '<source src="%s"></source>'
                '</audio>'
            ) % (_('External Audio'), escape(slide.url))
