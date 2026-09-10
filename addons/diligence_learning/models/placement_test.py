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


class SurveySurvey(models.Model):
    _inherit = 'survey.survey'

    diligence_is_placement_test = fields.Boolean('Placement Test', copy=False)
    diligence_placement_level_ids = fields.One2many(
        'diligence.placement.level', 'survey_id', string='Placement Levels', copy=True,
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

    @api.depends('survey_id', 'scoring_percentage', 'state')
    def _compute_diligence_placement_level(self):
        for result in self:
            if not result.survey_id.diligence_is_placement_test or result.state != 'done':
                result.diligence_placement_level_id = False
                continue
            result.diligence_placement_level_id = result.survey_id.diligence_placement_level_ids.filtered(
                lambda level: level.active and level.min_score <= result.scoring_percentage <= level.max_score
            )[:1]

