from odoo import api, fields, models
from odoo.exceptions import ValidationError


class DiligencePackageType(models.Model):
    _name = 'diligence.package.type'
    _description = 'Diligence Package Type'
    _order = 'sequence, name, id'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, copy=False, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    description = fields.Text(translate=True)
    website_label = fields.Char('Website Label', translate=True)
    website_badge = fields.Char('Website Badge', translate=True)

    _code_unique = models.Constraint(
        'unique(code)',
        'The package type code must be unique.',
    )

    @api.constrains('code')
    def _check_code(self):
        for record in self:
            if not record.code or not record.code.strip():
                raise ValidationError('Package type code cannot be empty.')


class DiligenceDeliveryMode(models.Model):
    _name = 'diligence.delivery.mode'
    _description = 'Diligence Delivery Mode'
    _order = 'sequence, name, id'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, copy=False, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    description = fields.Text(translate=True)

    _code_unique = models.Constraint(
        'unique(code)',
        'The delivery mode code must be unique.',
    )

    @api.constrains('code')
    def _check_code(self):
        for record in self:
            if not record.code or not record.code.strip():
                raise ValidationError('Delivery mode code cannot be empty.')
