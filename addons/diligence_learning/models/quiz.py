import re
import unicodedata
import io

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
    question_type_id = fields.Many2one('diligence.quiz.type', string='Question Type (Configurable)', ondelete='restrict')
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

    def _diligence_display_question(self, slide, sequence=None):
        """Avoid rendering a bare imported item number as if it were a prompt."""
        self.ensure_one()
        title = (self.question or '').strip()
        title = re.sub(r'\s*=\s*$', '', title).strip()
        if title and not re.fullmatch(r'(?:question\s*)?\d+[.)]?', title, flags=re.IGNORECASE):
            return title
        item_number = sequence or self.sequence or 1
        if slide.slide_category == 'audio':
            return _('Listen to the audio and enter your answer for item %(number)s.', number=item_number)
        return _('Enter your answer for item %(number)s.', number=item_number)

    @api.model
    def _prepare_questions_from_xlsx(self, slide, file_content):
        """Parse the standard Slides spreadsheet plus Diligence question types.

        Older spreadsheets without a Question Type column keep the native
        single-choice behavior. Short-answer and essay rows do not need
        distractor columns; listening questions can be imported as either
        choice or short-answer and have their audio attached after import.
        """
        try:
            from openpyxl import load_workbook
        except ImportError as exc:
            raise ValidationError(_("The Python package 'openpyxl' is required to import quiz questions from Excel.")) from exc

        try:
            workbook = load_workbook(io.BytesIO(file_content), data_only=True, read_only=True)
        except Exception as exc:
            raise ValidationError(_('The uploaded file could not be read. Please upload a valid .xlsx file.')) from exc

        rows = list(workbook.active.iter_rows(values_only=True))
        if not rows:
            raise ValidationError(_('The uploaded Excel file is empty.'))
        headers = [self._normalize_import_header(cell) for cell in rows[0]]
        if 'question' not in headers:
            raise ValidationError(_('The Excel file must contain a Question column.'))

        def column(*names):
            for name in names:
                normalized = self._normalize_import_header(name)
                if normalized in headers:
                    return headers.index(normalized)
            return None

        def cell(row, index):
            return row[index] if index is not None and index < len(row) else None

        question_index = column('question')
        type_index = column('question type', 'type')
        weight_index = column('weight', 'points')
        required_index = column('required')
        partial_index = column('allow partial score', 'partial credit')
        listening_index = column('listening answer type', 'response format')
        accepted_index = column('accepted answers', 'accepted answer', 'answer key')
        correct_answer_index = column('correct answer')
        rubric_index = column('grading rubric', 'rubric')
        feedback_index = column('feedback after submit', 'show feedback')

        answer_columns = {}
        for index, header in enumerate(headers):
            match = self._IMPORT_HEADER_REGEX.match(header or '')
            if match:
                answer_type, number = match.groups()
                answer_columns.setdefault(int(number), {})[answer_type] = index

        aliases = {
            'single_choice': 'single_choice', 'single choice': 'single_choice', 'multiple_choice': 'multiple_choice',
            'multiple choice': 'multiple_choice', 'true_false': 'true_false', 'true/false': 'true_false',
            'true false': 'true_false', 'short_answer': 'short_answer', 'short answer': 'short_answer',
            'essay': 'essay', 'listening': 'listening',
        }
        supported_types = {'single_choice', 'multiple_choice', 'true_false', 'short_answer', 'essay', 'listening'}
        prepared = []

        for row_index, row in enumerate(rows[1:], start=2):
            if not any(value not in (None, '') for value in row):
                continue
            title = self._format_import_cell(cell(row, question_index))
            if not title:
                raise ValidationError(_('Row %(row)s is missing the question title.', row=row_index))

            raw_type = self._format_import_cell(cell(row, type_index)).casefold() if type_index is not None else ''
            question_type = aliases.get(raw_type.replace('-', '_'), aliases.get(raw_type, 'single_choice'))
            if raw_type and question_type == 'single_choice' and raw_type not in aliases:
                raise ValidationError(_(
                    "Unsupported question type '%(type)s' in row %(row)s. Supported types: single_choice, multiple_choice, true_false, short_answer, essay, listening.",
                    type=raw_type, row=row_index,
                ))
            if question_type not in supported_types:
                raise ValidationError(_('Question type %(type)s is not supported for bulk import.', type=raw_type))

            try:
                weight = float(cell(row, weight_index) if cell(row, weight_index) not in (None, '') else 1.0)
            except (TypeError, ValueError) as exc:
                raise ValidationError(_('Row %(row)s has an invalid Weight.', row=row_index)) from exc
            if weight <= 0:
                raise ValidationError(_('Row %(row)s Weight must be greater than zero.', row=row_index))

            required_raw = cell(row, required_index)
            required = True if required_raw in (None, '') else self._parse_import_boolean(required_raw, row_index, 'Required')
            partial = self._parse_import_boolean(cell(row, partial_index), row_index, 'Allow Partial Score')
            feedback_raw = cell(row, feedback_index)
            feedback = True if feedback_raw in (None, '') else self._parse_import_boolean(feedback_raw, row_index, 'Feedback After Submit')

            answer_values = []
            marked_correct_texts = []
            for number in sorted(answer_columns):
                mapping = answer_columns[number]
                answer_text = self._format_import_cell(cell(row, mapping.get('answer')))
                if not answer_text:
                    continue
                is_correct = self._parse_import_boolean(cell(row, mapping.get('correct')), row_index, f'Correct {number}')
                answer_values.append({
                    'sequence': len(answer_values) + 1,
                    'text_value': answer_text,
                    'is_correct': is_correct,
                    'comment': self._format_import_cell(cell(row, mapping.get('comment'))),
                })
                if is_correct:
                    marked_correct_texts.append(answer_text)

            accepted_raw = self._format_import_cell(cell(row, accepted_index))
            accepted_answers = [value.strip() for value in re.split(r'[|\n]+', accepted_raw) if value.strip()]
            accepted_answers = accepted_answers or marked_correct_texts
            values = {
                'slide_id': slide.id,
                'question': title,
                'question_type': question_type,
                'weight': weight,
                'required': required,
                'allow_partial_score': partial,
                'feedback_after_submit': feedback,
                'grading_rubric': self._format_import_cell(cell(row, rubric_index)),
                'answer_ids': [],
            }
            configured_type = self.env['diligence.quiz.type'].search([('code', '=', question_type)], limit=1)
            if configured_type:
                values['question_type_id'] = configured_type.id

            if question_type in ('single_choice', 'multiple_choice'):
                if len(answer_values) < 2 or not any(a['is_correct'] for a in answer_values) or all(a['is_correct'] for a in answer_values):
                    raise ValidationError(_(
                        'Row %(row)s (%(type)s) needs at least two options, including one correct and one incorrect option.',
                        row=row_index, type=question_type,
                    ))
                if question_type == 'single_choice' and len(marked_correct_texts) != 1:
                    raise ValidationError(_('Row %(row)s single-choice question must have exactly one correct option.', row=row_index))
                values['answer_ids'] = answer_values
            elif question_type == 'true_false':
                if not answer_values:
                    raw_correct = self._format_import_cell(cell(row, correct_answer_index)).casefold()
                    if raw_correct not in ('true', 'false', 'benar', 'salah'):
                        raise ValidationError(_('Row %(row)s true/false needs Answer 1/2 options or Correct Answer set to True/False.', row=row_index))
                    correct_text = 'True' if raw_correct in ('true', 'benar') else 'False'
                    answer_values = [
                        {'sequence': 1, 'text_value': 'True', 'is_correct': correct_text == 'True'},
                        {'sequence': 2, 'text_value': 'False', 'is_correct': correct_text == 'False'},
                    ]
                if len(answer_values) != 2 or sum(a['is_correct'] for a in answer_values) != 1:
                    raise ValidationError(_('Row %(row)s true/false question must have two options and exactly one correct answer.', row=row_index))
                values['answer_ids'] = answer_values
            elif question_type == 'short_answer':
                if not accepted_answers:
                    raise ValidationError(_('Row %(row)s short-answer question needs Accepted Answers (separate alternatives with |).', row=row_index))
                values['short_answer_variants'] = '\n'.join(accepted_answers)
            elif question_type == 'essay':
                if not values['grading_rubric']:
                    raise ValidationError(_('Row %(row)s essay question needs a Grading Rubric.', row=row_index))
            else:  # listening
                listening_raw = self._format_import_cell(cell(row, listening_index)).casefold() if listening_index is not None else ''
                listening_type = {'choice': 'choice', 'short_answer': 'short_answer', 'short answer': 'short_answer'}.get(listening_raw, 'choice')
                values['listening_answer_type'] = listening_type
                if listening_type == 'choice':
                    if len(answer_values) < 2 or not any(a['is_correct'] for a in answer_values) or all(a['is_correct'] for a in answer_values):
                        raise ValidationError(_('Row %(row)s listening-choice needs at least one correct and one incorrect option.', row=row_index))
                    values['answer_ids'] = answer_values
                else:
                    if not accepted_answers:
                        raise ValidationError(_('Row %(row)s listening short-answer needs Accepted Answers.', row=row_index))
                    values['short_answer_variants'] = '\n'.join(accepted_answers)

            prepared.append(values)

        if not prepared:
            raise ValidationError(_('The Excel file does not contain any question rows to import.'))
        return prepared

    @api.onchange('question_type_id')
    def _onchange_question_type_id(self):
        for question in self:
            if question.question_type_id and question.question_type_id.code in dict(
                self._fields['question_type'].selection
            ):
                question.question_type = question.question_type_id.code

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            type_id = vals.get('question_type_id')
            if type_id and not vals.get('question_type'):
                configured = self.env['diligence.quiz.type'].browse(type_id)
                if configured.code in dict(self._fields['question_type'].selection):
                    vals['question_type'] = configured.code
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('question_type_id'):
            configured = self.env['diligence.quiz.type'].browse(vals['question_type_id'])
            if configured.code in dict(self._fields['question_type'].selection):
                vals = dict(vals, question_type=configured.code)
        return super().write(vals)

    @api.constrains('weight', 'max_audio_plays')
    def _check_diligence_quiz_configuration(self):
        for question in self:
            if question.weight <= 0:
                raise ValidationError(_('Question weight must be greater than zero.'))
            if question.max_audio_plays < 0:
                raise ValidationError(_('Maximum audio plays cannot be negative.'))

    @api.constrains('answer_ids', 'question_type', 'listening_answer_type')
    def _check_answers_integrity(self):
        choice_questions = self.filtered(lambda question: (
            question.question_type in ('single_choice', 'multiple_choice', 'true_false')
            or question.question_type == 'listening'
            and question.listening_answer_type == 'choice'
        ))
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
        if not accepted:
            accepted = self.answer_ids.filtered('is_correct').mapped('text_value')
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
            # Show the automatically calculated result immediately.  A mixed
            # quiz may still wait for its essay/speaking grade, but displaying
            # zero until then is misleading for the learner.
            attempt.final_score = (
                attempt.manual_score
                if manually_scored and attempt.state in ('passed', 'failed')
                else attempt.auto_score
            )

    def action_grade(self):
        if not self.env.user.has_group('website_slides.group_website_slides_officer') and not self.env.user._is_admin():
            raise AccessError(_('Only authorised teachers or administrators can grade quiz attempts.'))
        for attempt in self:
            if any(response.question_type in ('essay', 'speaking') and not response.manual_graded
                   for response in attempt.response_ids):
                raise ValidationError(_('All manual answers must be graded first.'))
            total_weight = sum(attempt.response_ids.mapped('question_id.weight')) or 1.0
            points = sum(
                response.manual_score if response.question_type in ('essay', 'speaking') else response.auto_score
                for response in attempt.response_ids
            )
            final_score = points / total_weight * 100
            attempt.write({
                'manual_score': final_score,
                'manual_graded': True,
                'state': 'passed' if final_score >= attempt.passing_score else 'failed',
            })


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
