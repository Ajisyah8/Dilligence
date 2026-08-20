import re

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
