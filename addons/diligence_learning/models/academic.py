from datetime import datetime, timedelta

from odoo import api, fields, models


class SlideChannel(models.Model):
    _inherit = 'slide.channel'

    diligence_availability = fields.Selection([
        ('available', 'Available'),
        ('coming_soon', 'Coming Soon'),
    ], string='Learning Availability', default='available', required=True, index=True,
       help='Coming Soon keeps the course visible, but prevents learners from opening its lessons until it is released.')
    diligence_contact_segment_id = fields.Many2one(
        'diligence.contact.segment',
        string='Course Contact Segment',
        copy=False,
        readonly=True,
        help='Automatically created segment used to find learners enrolled in this course.',
    )
    diligence_active_student_count = fields.Integer('Active Students', compute='_compute_diligence_kpis')
    diligence_new_student_count = fields.Integer('New Students (30 Days)', compute='_compute_diligence_kpis')
    diligence_completed_student_count = fields.Integer('Completed Students', compute='_compute_diligence_kpis')
    diligence_expiring_student_count = fields.Integer('Expiring Access (30 Days)', compute='_compute_diligence_kpis')

    @api.model_create_multi
    def create(self, vals_list):
        courses = super().create(vals_list)
        courses._diligence_ensure_contact_segment()
        return courses

    def write(self, vals):
        result = super().write(vals)
        if 'name' in vals:
            self._diligence_ensure_contact_segment()
        return result

    def _diligence_ensure_contact_segment(self):
        Segment = self.env['diligence.contact.segment'].sudo()
        IrHttp = self.env['ir.http']
        for course in self:
            if not course.name:
                continue
            slug = IrHttp._slugify(course.name, max_length=100, path=False) or f'course-{course.id}'
            code = f'course_{slug}_{course.id}'
            segment = course.diligence_contact_segment_id
            if not segment:
                segment = Segment.search([('code', '=', code)], limit=1)
            if not segment:
                segment = Segment.create({
                    'name': course.name,
                    'code': code,
                    'sequence': 100,
                })
            elif segment.name != course.name:
                segment.write({'name': course.name})
            if course.diligence_contact_segment_id != segment:
                course.sudo().with_context(diligence_syncing_course_segment=True).write({
                    'diligence_contact_segment_id': segment.id,
                })
        return self

    def _diligence_sync_active_member_segments(self):
        for course in self:
            course._diligence_ensure_contact_segment()
            if not course.diligence_contact_segment_id:
                continue
            active_members = course.channel_partner_ids.filtered(
                lambda member: member.member_status in ('joined', 'ongoing')
                and member._diligence_access_is_valid()
            )
            active_members.mapped('partner_id')._diligence_assign_segment_codes([
                course.diligence_contact_segment_id.code,
            ])
        return self

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
