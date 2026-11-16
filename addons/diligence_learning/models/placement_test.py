from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class DiligencePlacementLevel(models.Model):
    _name = 'diligence.placement.level'
    _description = 'Diligence Placement Test Level'
    _order = 'sequence, min_score, id'

    name = fields.Char(required=True, translate=True)
    survey_id = fields.Many2one('survey.survey', required=True, ondelete='cascade', index=True)
    min_score = fields.Float('Minimum Score (%)', required=True)
    max_score = fields.Float('Maximum Score (%)', required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    recommendation = fields.Text('Recommendation', translate=True)

    @api.constrains('min_score', 'max_score')
    def _check_score_range(self):
        for level in self:
            if not 0 <= level.min_score <= level.max_score <= 100:
                raise ValidationError(_('Placement level scores must be between 0 and 100.'))


class DiligencePlacementCourse(models.Model):
    _name = 'diligence.placement.course'
    _description = 'Course in a Diligence Placement Test'
    _order = 'sequence, id'

    name = fields.Char(related='course_id.name', string='Course', store=True, readonly=True)
    survey_id = fields.Many2one('survey.survey', required=True, ondelete='cascade', index=True)
    course_id = fields.Many2one('slide.channel', string='Course', required=True, ondelete='restrict')
    question_ids = fields.One2many('survey.question', 'diligence_placement_course_id', string='Questions')
    min_score = fields.Float('Passing Score (%)', default=70.0, required=True)
    sequence = fields.Integer(default=10)

    _course_per_survey = models.Constraint(
        'unique(survey_id, course_id)',
        'A course can only be added once to a placement test.',
    )

    @api.constrains('min_score')
    def _check_min_score(self):
        for record in self:
            if not 0 <= record.min_score <= 100:
                raise ValidationError(_('The passing score must be between 0 and 100.'))


class DiligencePlacementCourseResult(models.Model):
    _name = 'diligence.placement.course.result'
    _description = 'Placement Test Result by Course'
    _order = 'sequence, id'

    user_input_id = fields.Many2one('survey.user_input', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    course_id = fields.Many2one('slide.channel', string='Course', required=True, ondelete='restrict')
    score = fields.Float('Score (%)', digits=(5, 2), readonly=True)
    passing_score = fields.Float('Passing Score (%)', digits=(5, 2), readonly=True)
    manually_graded_count = fields.Integer('Questions for Instructor Review', readonly=True)
    outcome = fields.Selection([
        ('pass', 'Skip Recommended'),
        ('review', 'Course Review Recommended'),
        ('manual', 'Instructor Review Required'),
        ('not_tested', 'No Questions Selected'),
    ], required=True, readonly=True)
    manual_decision = fields.Selection([
        ('pass', 'Skip Course'),
        ('review', 'Review Course'),
    ], string='Instructor Decision')
    final_recommendation = fields.Selection([
        ('pass', 'Skip Course'),
        ('review', 'Review Course'),
        ('manual', 'Instructor Review Required'),
        ('not_tested', 'No Questions Selected'),
    ], compute='_compute_final_recommendation', string='Final Recommendation')

    _result_per_course = models.Constraint(
        'unique(user_input_id, course_id)',
        'A placement result can only contain one row per course.',
    )

    @api.constrains('user_input_id', 'course_id')
    def _check_result_course(self):
        for result in self:
            configs = result.user_input_id.survey_id.diligence_placement_course_ids
            if result.course_id not in configs.mapped('course_id'):
                raise ValidationError(_('The result course must be configured on this placement test.'))

    @api.depends('outcome', 'manual_decision')
    def _compute_final_recommendation(self):
        for result in self:
            result.final_recommendation = result.manual_decision or result.outcome


class SurveySurvey(models.Model):
    _inherit = 'survey.survey'

    diligence_is_placement_test = fields.Boolean('Placement Test', copy=False)
    diligence_placement_level_ids = fields.One2many(
        'diligence.placement.level', 'survey_id', string='Placement Levels', copy=True,
    )
    diligence_placement_course_ids = fields.One2many(
        'diligence.placement.course', 'survey_id', string='Courses and Pass Scores', copy=True,
    )

class SurveyUserInput(models.Model):
    _inherit = 'survey.user_input'

    diligence_placement_level_id = fields.Many2one(
        'diligence.placement.level', string='Recommended Level', compute='_compute_diligence_placement_level',
        store=True, readonly=True,
    )
    diligence_placement_review_state = fields.Selection([
        ('pending', 'Pending Admin Review'),
        ('reviewed', 'Reviewed'),
    ], string='Placement Review', default='pending', required=True, copy=False)
    diligence_placement_course_result_ids = fields.One2many(
        'diligence.placement.course.result', 'user_input_id', string='Course Recommendations', readonly=True,
    )

    def write(self, vals):
        result = super().write(vals)
        if 'state' in vals:
            self.filtered(lambda item: item.state == 'done' and item.survey_id.diligence_is_placement_test)._diligence_update_placement_course_results()
        return result

    def _diligence_update_placement_course_results(self):
        for user_input in self:
            lines_by_question = {}
            for line in user_input.user_input_line_ids:
                lines_by_question.setdefault(line.question_id.id, self.env['survey.user_input.line'])
                lines_by_question[line.question_id.id] |= line
            result_values = []
            for config in user_input.survey_id.diligence_placement_course_ids:
                questions = config.question_ids.filtered(
                    lambda question: not question.is_page and question in user_input.predefined_question_ids
                )
                possible_score = 0.0
                earned_score = 0.0
                manual_count = 0
                for question in questions:
                    if question.question_type == 'simple_choice':
                        possible_score += max(
                            question.suggested_answer_ids.filtered(lambda answer: answer.answer_score > 0).mapped('answer_score'),
                            default=0.0,
                        )
                    elif question.question_type == 'multiple_choice':
                        possible_score += sum(
                            question.suggested_answer_ids.filtered(lambda answer: answer.answer_score > 0).mapped('answer_score')
                        )
                    elif question.is_scored_question:
                        possible_score += question.answer_score
                    else:
                        manual_count += 1

                    earned_score += sum(lines_by_question.get(question.id, self.env['survey.user_input.line']).mapped('answer_score'))

                score = max(0.0, round(100.0 * earned_score / possible_score, 2)) if possible_score else 0.0
                if not questions:
                    outcome = 'not_tested'
                elif manual_count or not possible_score:
                    outcome = 'manual'
                elif score >= config.min_score:
                    outcome = 'pass'
                else:
                    outcome = 'review'
                result_values.append({
                    'sequence': config.sequence,
                    'course_id': config.course_id.id,
                    'score': score,
                    'passing_score': config.min_score,
                    'manually_graded_count': manual_count,
                    'outcome': outcome,
                })
            result_model = self.env['diligence.placement.course.result'].sudo()
            existing = result_model.search([('user_input_id', '=', user_input.id)])
            existing.unlink()
            if result_values:
                result_model.create([
                    dict(values, user_input_id=user_input.id) for values in result_values
                ])

    @api.depends('survey_id', 'scoring_percentage', 'state')
    def _compute_diligence_placement_level(self):
        for result in self:
            if not result.survey_id.diligence_is_placement_test or result.state != 'done':
                result.diligence_placement_level_id = False
                continue
            result.diligence_placement_level_id = result.survey_id.diligence_placement_level_ids.filtered(
                lambda level: level.active and level.min_score <= result.scoring_percentage <= level.max_score
            )[:1]


class SurveyQuestion(models.Model):
    _inherit = 'survey.question'

    diligence_placement_course_id = fields.Many2one(
        'diligence.placement.course', string='Placement Course', ondelete='set null',
        domain="[('survey_id', '=', survey_id)]",
        help='Assign this question to the course it assesses in a placement test.',
    )

    @api.constrains('survey_id', 'diligence_placement_course_id')
    def _check_placement_course_survey(self):
        for question in self.filtered('diligence_placement_course_id'):
            if question.survey_id != question.diligence_placement_course_id.survey_id:
                raise ValidationError(_('The placement course must belong to the same survey as the question.'))

