import re

from markupsafe import Markup, escape

from odoo import api, fields, models, _


class SlideSlide(models.Model):
    _inherit = 'slide.slide'

    diligence_external_quiz_url = fields.Char('External Quiz / Google Form Link')
    diligence_external_quiz_label = fields.Char(
        'External Quiz Button Label',
        default='Open External Quiz',
    )

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
