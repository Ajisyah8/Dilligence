import calendar
from datetime import timedelta

from odoo import fields, http
from odoo.http import request


def _student_courses_values(partner):
    """Build the student dashboard values from native Odoo records."""
    memberships = request.env['slide.channel.partner'].sudo().search([
        ('partner_id', 'child_of', partner.id),
        ('active', '=', True),
        ('member_status', '!=', 'invited'),
    ])
    memberships = memberships.filtered(lambda membership: membership._diligence_access_is_valid())

    slide_partner_model = request.env['slide.slide.partner'].sudo()
    attempt_model = request.env['diligence.quiz.attempt'].sudo()
    dashboard_courses = []
    for membership in memberships:
        slides = membership.channel_id.slide_content_ids.filtered(lambda slide: not slide.is_category)
        slide_partners = slide_partner_model.search([
            ('slide_id', 'in', slides.ids),
            ('partner_id', '=', partner.id),
        ]) if slides else slide_partner_model.browse()
        completed_slides = slide_partners.filtered('completed')
        quiz_slides = slides.filtered(lambda slide: bool(slide.question_ids))
        attempts = attempt_model.search([
            ('slide_id', 'in', quiz_slides.ids),
            ('partner_id', '=', partner.id),
            ('state', '!=', 'in_progress'),
        ], order='submitted_at desc, id desc') if quiz_slides else attempt_model.browse()
        latest_scores = {}
        for attempt in attempts:
            latest_scores.setdefault(attempt.slide_id.id, attempt)
        score_boxes = []
        for index, quiz in enumerate(quiz_slides):
            attempt = latest_scores.get(quiz.id)
            score_boxes.append({
                'number': index + 1,
                'name': quiz.name,
                'score': round(attempt.final_score) if attempt else None,
                'state': attempt.state if attempt else 'not_started',
                'attempt_number': attempt.attempt_number if attempt else 0,
            })
        dashboard_courses.append({
            'membership': membership,
            'completed': len(completed_slides),
            'total': len(slides),
            'progress': membership.completion,
            'score_boxes': score_boxes,
        })

    today = fields.Date.context_today(request.env.user)
    month_start = today.replace(day=1)
    month_days = calendar.monthcalendar(today.year, today.month)
    activities = request.env['diligence.learning.activity'].sudo().search([
        ('partner_id', '=', partner.id),
        ('activity_date', '>=', today - timedelta(days=89)),
    ])
    month_activities = activities.filtered(
        lambda activity: month_start <= activity.activity_date <= today
    )
    active_days = {activity.activity_date.day for activity in month_activities}
    calendar_weeks = []
    for week in month_days:
        calendar_weeks.append([{
            'day': day,
            'active': day in active_days,
            'today': day == today.day,
        } for day in week])
    monthly_duration_minutes = sum(
        (activity.slide_id.completion_time or 0.0) * 60 for activity in month_activities
    )

    orders = request.env['sale.order'].sudo().search([
        ('partner_id', 'child_of', partner.id),
        ('state', 'in', ('sale', 'done')),
    ])
    invoices = request.env['account.move'].sudo().search([
        ('partner_id', 'child_of', partner.id),
        ('move_type', 'in', ('out_invoice', 'out_refund')),
        ('state', '=', 'posted'),
    ])
    cart_count = 0
    sale_order_id = request.session.get('sale_order_id')
    if sale_order_id:
        cart = request.env['sale.order'].sudo().browse(sale_order_id).exists()
        if cart and cart.partner_id.commercial_partner_id == partner:
            cart_count = int(sum(cart.order_line.mapped('product_uom_qty')))

    activity_model = request.env['diligence.learning.activity'].sudo()
    current_streak, best_streak = activity_model.calculate_streak(partner)
    sessions = request.env['diligence.session'].sudo().search([
        ('package_id', 'in', memberships.mapped('diligence_package_id').ids),
        ('start_datetime', '>=', fields.Datetime.now()),
        ('state', '=', 'scheduled'),
    ], order='start_datetime asc', limit=5)
    return {
        'partner': partner,
        'memberships': memberships,
        'dashboard_courses': dashboard_courses,
        'activities': activities,
        'current_streak': current_streak,
        'best_streak': best_streak,
        'upcoming_sessions': sessions,
        'calendar_weeks': calendar_weeks,
        'calendar_month_label': today.strftime('%B %Y'),
        'monthly_activity_days': len(active_days),
        'monthly_duration_minutes': round(monthly_duration_minutes),
        'orders_count': len(orders),
        'invoices_count': len(invoices),
        'cart_count': cart_count,
    }


class DiligenceStudentPortal(http.Controller):
    @http.route('/my/courses', type='http', auth='user', website=True)
    def my_courses(self, **kwargs):
        partner = request.env.user.partner_id.commercial_partner_id
        return request.render('diligence_learning.portal_my_courses', _student_courses_values(partner))

    @http.route('/my/consultations', type='http', auth='user', website=True)
    def my_consultations(self, **kwargs):
        partner = request.env.user.partner_id.commercial_partner_id
        orders = request.env['sale.order'].sudo().search([
            ('partner_id', 'child_of', partner.id),
            ('state', 'in', ('sale', 'done')),
            ('order_line.product_template_id.diligence_consultation', '=', True),
        ], order='date_order desc')
        return request.render('diligence_learning.portal_my_consultations', {
            'partner': partner,
            'orders': orders,
        })
