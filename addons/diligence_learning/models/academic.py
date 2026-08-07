from datetime import datetime, timedelta

from odoo import api, fields, models


class SlideChannel(models.Model):
    _inherit = 'slide.channel'

    diligence_active_student_count = fields.Integer('Active Students', compute='_compute_diligence_kpis')
    diligence_new_student_count = fields.Integer('New Students (30 Days)', compute='_compute_diligence_kpis')
    diligence_completed_student_count = fields.Integer('Completed Students', compute='_compute_diligence_kpis')
    diligence_expiring_student_count = fields.Integer('Expiring Access (30 Days)', compute='_compute_diligence_kpis')

    @api.depends('channel_partner_ids', 'channel_partner_ids.member_status', 'channel_partner_ids.create_date', 'channel_partner_ids.diligence_access_expires_at')
    def _compute_diligence_kpis(self):
        now = fields.Datetime.now()
        new_since = now - timedelta(days=30)
        expiring_until = now + timedelta(days=30)
        for channel in self:
            members = channel.channel_partner_ids
            active = members.filtered(lambda member: member.member_status in ('joined', 'ongoing'))
            channel.diligence_active_student_count = len(active)
            channel.diligence_new_student_count = len(active.filtered(lambda member: member.create_date and member.create_date >= new_since))
            channel.diligence_completed_student_count = len(members.filtered(lambda member: member.member_status == 'completed'))
            channel.diligence_expiring_student_count = len(active.filtered(
                lambda member: member.diligence_access_expires_at and now <= member.diligence_access_expires_at <= expiring_until
            ))
