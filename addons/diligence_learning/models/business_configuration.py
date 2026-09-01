from odoo import api, fields, models
from odoo.exceptions import ValidationError


class DiligenceContactSegment(models.Model):
    _name = 'diligence.contact.segment'
    _description = 'Diligence Contact Segment'
    _order = 'sequence, name, id'
    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, copy=False, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    _code_unique = models.Constraint('unique(code)', 'Contact segment code must be unique.')

    @api.constrains('code')
    def _check_code(self):
        for record in self:
            if not record.code or not record.code.strip():
                raise ValidationError('Contact segment code cannot be empty.')


class DiligenceAffiliateType(models.Model):
    _name = 'diligence.affiliate.type'
    _description = 'Diligence Affiliate Type'
    _order = 'sequence, name, id'
    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, copy=False, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    _code_unique = models.Constraint('unique(code)', 'Affiliate type code must be unique.')


class DiligenceCashbackType(models.Model):
    _name = 'diligence.cashback.type'
    _description = 'Diligence Cashback Type'
    _order = 'sequence, name, id'
    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, copy=False, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    _code_unique = models.Constraint('unique(code)', 'Cashback type code must be unique.')


class DiligenceQuizType(models.Model):
    _name = 'diligence.quiz.type'
    _description = 'Diligence Quiz Type'
    _order = 'sequence, name, id'
    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, copy=False, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    supports_choices = fields.Boolean('Supports choices', default=True)
    supports_text_answer = fields.Boolean('Supports text answer')
    requires_manual_grading = fields.Boolean('Requires manual grading')
    _code_unique = models.Constraint('unique(code)', 'Quiz type code must be unique.')


class DiligenceActivityType(models.Model):
    _name = 'diligence.activity.type'
    _description = 'Diligence Activity Type'
    _order = 'sequence, name, id'
    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, copy=False, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    _code_unique = models.Constraint('unique(code)', 'Activity type code must be unique.')


class DiligenceSessionType(models.Model):
    _name = 'diligence.session.type'
    _description = 'Diligence Session Type'
    _order = 'sequence, name, id'
    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, copy=False, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    _code_unique = models.Constraint('unique(code)', 'Session type code must be unique.')
