from odoo import fields, models


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    diligence_referral_code = fields.Char('Referral Code', copy=False, index=True)
    diligence_referrer_id = fields.Many2one('res.partner', 'Affiliate Referrer', copy=False)
    diligence_program_id = fields.Many2one('product.template', 'Interested Package', copy=False)
    diligence_student_id = fields.Many2one('res.partner', 'Student', copy=False)
