import re
import unicodedata

from odoo import api, fields, models, _, Command
from odoo.exceptions import AccessError, ValidationError


class SlideQuestion(models.Model):
    _inherit = 'slide.question'

    question_type = fields.Selection([
        ('single_choice', 'Single choice'),
        ('multiple_choice', 'Multiple choice'),
        ('true_false', 'True / False'),
        ('short_answer', 'Short answer'),
        ('essay', 'Essay'),
        ('listening', 'Listening'),
        ('matching', 'Matching (Phase 2)'),
        ('ordering', 'Ordering (Phase 2)'),
        ('speaking', 'Speaking / audio (Phase 2)'),
    ], default='single_choice', required=True, string='Question type')
    weight = fields.Float('Weight', default=1.0)
    required = fields.Boolean('Required', default=True)
    allow_partial_score = fields.Boolean('Allow partial score')
    short_answer_variants = fields.Text(
        'Accepted short answers',
        help='One accepted answer per line. Matching is case-insensitive and whitespace is normalized.',
    )
    short_answer_ignore_punctuation = fields.Boolean('Ignore punctuation', default=True)
    short_answer_ignore_accents = fields.Boolean('Ignore accents', default=True)
    listening_answer_type = fields.Selection([
        ('choice', 'Choice'),
        ('short_answer', 'Short answer'),
    ], default='choice', string='Listening answer type')
    audio_file = fields.Binary('Question audio', attachment=True)
    audio_filename = fields.Char('Audio filename')
    max_audio_plays = fields.Integer('Maximum audio plays', default=0)
    feedback_after_submit = fields.Boolean('Show feedback after submit', default=True)
    grading_rubric = fields.Text('Teacher grading rubric')

    @api.constrains('weight', 'max_audio_plays')
    def _check_diligence_quiz_configuration(self):
        for question in self:
            if question.weight <= 0:
                raise ValidationError(_('Question weight must be greater than zero.'))
            if question.max_audio_plays < 0:
                raise ValidationError(_('Maximum audio plays cannot be negative.'))

    @api.constrains('answer_ids', 'question_type')
    def _check_answers_integrity(self):
        choice_questions = self.filtered(lambda question: question.question_type in (
            'single_choice', 'multiple_choice', 'true_false', 'listening'))
        if choice_questions:
            super(SlideQuestion, choice_questions)._check_answers_integrity()

    @api.onchange('question_type')
    def _onchange_question_type(self):
        for question in self:
            if question.question_type == 'true_false' and not question.answer_ids:
                question.answer_ids = [
                    Command.create({'text_value': _('True'), 'sequence': 1}),
                    Command.create({'text_value': _('False'), 'sequence': 2}),
                ]

    def _diligence_is_multitype(self):
        self.ensure_one()
        return self.question_type != 'single_choice'

    def _diligence_normalize_answer(self, value):
        value = re.sub(r'\s+', ' ', (value or '').strip()).casefold()
        if self.short_answer_ignore_accents:
            value = ''.join(
                char for char in unicodedata.normalize('NFKD', value)
                if not unicodedata.combining(char)
            )
        if self.short_answer_ignore_punctuation:
            value = ''.join(char for char in value if not unicodedata.category(char).startswith('P'))
        return value

    def _diligence_short_answer_is_correct(self, value):
        accepted = [line for line in (self.short_answer_variants or '').splitlines() if line.strip()]
        return self._diligence_normalize_answer(value) in {
            self._diligence_normalize_answer(answer) for answer in accepted
        }


class SlideAnswer(models.Model):
    _inherit = 'slide.answer'

    answer_weight = fields.Float('Answer weight', default=1.0)


class DiligenceQuizAttempt(models.Model):
    _name = 'diligence.quiz.attempt'
    _description = 'Diligence Quiz Attempt'
    _order = 'started_at desc, id desc'

    slide_id = fields.Many2one('slide.slide', required=True, index=True, ondelete='cascade')
    channel_id = fields.Many2one(related='slide_id.channel_id', store=True, index=True)
    partner_id = fields.Many2one('res.partner', required=True, index=True, ondelete='cascade')
    attempt_number = fields.Integer(required=True)
    started_at = fields.Datetime(required=True, default=fields.Datetime.now)
    submitted_at = fields.Datetime()
    auto_score = fields.Float()
    manual_score = fields.Float()
    manual_graded = fields.Boolean('Manual grade completed')
    final_score = fields.Float(compute='_compute_final_score', store=True)
    passing_score = fields.Float(default=70.0)
    state = fields.Selection([
        ('in_progress', 'In progress'),
        ('pending_review', 'Waiting for grading'),
        ('passed', 'Passed'),
        ('failed', 'Failed'),
    ], default='in_progress', required=True, index=True)
    response_ids = fields.One2many('diligence.quiz.response', 'attempt_id', string='Answers')

    _attempt_uniq = models.Constraint(
        'unique(slide_id, partner_id, attempt_number)',
        'Quiz attempt number must be unique per student and quiz.',
    )

    @api.depends('auto_score', 'manual_score', 'state')
    def _compute_final_score(self):
        for attempt in self:
            manually_scored = attempt.response_ids.filtered(lambda response: response.question_type in ('essay', 'speaking'))
            attempt.final_score = attempt.manual_score if manually_scored else attempt.auto_score

    def action_grade(self):
        for attempt in self:
            if any(response.question_type in ('essay', 'speaking') and not response.manual_graded
                   for response in attempt.response_ids):
                raise ValidationError(_('All manual answers must be graded first.'))
            total_weight = sum(attempt.response_ids.mapped('question_id.weight')) or 1.0
            points = sum(
                response.manual_score if response.question_type in ('essay', 'speaking') else response.auto_score
                for response in attempt.response_ids
            )
            attempt.manual_score = points / total_weight * 100
            attempt.state = 'passed' if attempt.final_score >= attempt.passing_score else 'failed'


class DiligenceQuizResponse(models.Model):
    _name = 'diligence.quiz.response'
    _description = 'Diligence Quiz Answer'

    attempt_id = fields.Many2one('diligence.quiz.attempt', required=True, index=True, ondelete='cascade')
    question_id = fields.Many2one('slide.question', required=True, index=True, ondelete='cascade')
    question_type = fields.Selection(related='question_id.question_type', store=True)
    selected_answer_ids = fields.Many2many('slide.answer', string='Selected choices')
    text_answer = fields.Text('Text answer')
    audio_file = fields.Binary('Audio answer', attachment=True)
    audio_filename = fields.Char('Audio filename')
    is_correct = fields.Boolean()
    auto_score = fields.Float()
    manual_score = fields.Float()
    manual_graded = fields.Boolean('Manually graded')
    feedback = fields.Text()
    graded_by = fields.Many2one('res.users')
    graded_at = fields.Datetime()

    _response_uniq = models.Constraint(
        'unique(attempt_id, question_id)',
        'A quiz attempt can contain only one answer per question.',
    )

    def _check_student_access(self):
        self.ensure_one()
        user = self.env.user
        if user.has_group('website_slides.group_website_slides_officer') or user.has_group('base.group_system'):
            return
        if self.attempt_id.partner_id != user.partner_id:
            raise AccessError(_('You can only access your own quiz answers.'))
