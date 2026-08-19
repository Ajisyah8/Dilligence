from datetime import timedelta

from odoo import api, fields, models


class DiligenceLearningActivity(models.Model):
    _name = 'diligence.learning.activity'
    _description = 'Diligence Learning Activity'
    _order = 'activity_date desc, id desc'

    partner_id = fields.Many2one('res.partner', required=True, index=True, ondelete='cascade')
    slide_id = fields.Many2one('slide.slide', required=True, index=True, ondelete='cascade')
    channel_id = fields.Many2one(related='slide_id.channel_id', store=True, index=True)
    activity_date = fields.Date(required=True, default=fields.Date.context_today, index=True)
    activity_type = fields.Selection([
        ('lesson', 'Lesson completed'),
        ('quiz', 'Quiz completed'),
    ], required=True, default='lesson')

    _activity_uniq = models.Constraint(
        'unique(partner_id, slide_id, activity_date, activity_type)',
        'The same learning activity cannot be recorded twice on one day.',
    )

    @api.model
    def record_completion(self, partner, slide, activity_type='lesson'):
        partner = partner.commercial_partner_id
        today = fields.Date.context_today(self)
        domain = [
            ('partner_id', '=', partner.id), ('slide_id', '=', slide.id),
            ('activity_date', '=', today), ('activity_type', '=', activity_type),
        ]
        return self.search(domain, limit=1) or self.create({
            'partner_id': partner.id,
            'slide_id': slide.id,
            'activity_date': today,
            'activity_type': activity_type,
        })

    @api.model
    def calculate_streak(self, partner, until=None):
        until = until or fields.Date.context_today(self)
        days = set(self.search([
            ('partner_id', '=', partner.commercial_partner_id.id),
            ('activity_date', '<=', until),
        ]).mapped('activity_date'))
        current = 0
        cursor = until
        while cursor in days:
            current += 1
            cursor -= timedelta(days=1)
        best = 0
        for day in sorted(days):
            length = 1
            while day + timedelta(days=length) in days:
                length += 1
            best = max(best, length)
        return current, best


class SlideSlidePartnerActivity(models.Model):
    _inherit = 'slide.slide.partner'

    def write(self, vals):
        completed_before = {record.id: record.completed for record in self}
        result = super().write(vals)
        if vals.get('completed'):
            activity_model = self.env['diligence.learning.activity'].sudo()
            for membership in self.filtered(lambda record: not completed_before.get(record.id)):
                activity_model.record_completion(
                    membership.partner_id,
                    membership.slide_id,
                    'quiz' if membership.slide_id.question_ids else 'lesson',
                )
        return result
