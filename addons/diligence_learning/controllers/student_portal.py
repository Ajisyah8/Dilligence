import calendar
import base64
from datetime import timedelta

from odoo import fields, http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal


def _student_courses_values(partner):
    """Build the student dashboard values from native Odoo records."""
    paid_orders = request.env['sale.order'].sudo().search([
        ('partner_id', 'child_of', partner.id),
        ('state', 'in', ('sale', 'done')),
    ]).filtered(lambda order: order._diligence_has_valid_package_payment())
    paid_package_ids = paid_orders.mapped('order_line.product_template_id').filtered(
        lambda product: product._diligence_is_package()
    ).ids
    memberships = request.env['slide.channel.partner'].sudo().search([
        ('partner_id', 'child_of', partner.id),
        ('active', '=', True),
        ('member_status', '!=', 'invited'),
        ('diligence_package_id', 'in', paid_package_ids or [0]),
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
    pending_qris_orders = request.env['sale.order'].sudo().search([
        ('partner_id', 'child_of', partner.id),
        ('transaction_ids.state', '=', 'pending'),
        ('transaction_ids.provider_id.custom_mode', '=', 'qris_static'),
    ])
    qris_orders_with_proof = request.env['sale.order'].sudo().search([
        ('partner_id', 'child_of', partner.id),
        ('transaction_ids.provider_id.custom_mode', '=', 'qris_static'),
        ('transaction_ids.qris_proof_attachment_id', '!=', False),
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
        ('attendee_ids.partner_id', '=', partner.id),
        ('attendee_ids.state', '!=', 'cancelled'),
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
        'pending_qris_orders': pending_qris_orders,
        'qris_orders_with_proof': qris_orders_with_proof,
    }


class DiligenceStudentPortal(CustomerPortal):
    @http.route(['/my'], type='http', auth='user', website=True,
                list_as_website_content=False)
    def home(self, **kwargs):
        """Keep Student Corner on /my; leave the native My Account route at /my/home."""
        partner = request.env.user.partner_id.commercial_partner_id
        values = _student_courses_values(partner)
        values.update(self._prepare_portal_layout_values())
        values['my_details'] = True
        return request.render('diligence_learning.portal_my_courses', values)

    @http.route('/my/courses', type='http', auth='user', website=True)
    def my_courses(self, **kwargs):
        return request.redirect('/my')

    @http.route('/my/orders/<int:order_id>/qris', type='http', auth='user', website=True,
                sitemap=False)
    def resume_qris_payment(self, order_id, **kwargs):
        """Resume the existing pending QRIS transaction without creating a new order."""
        partner = request.env.user.partner_id.commercial_partner_id
        order = request.env['sale.order'].sudo().browse(order_id).exists()
        if not order or order.partner_id.commercial_partner_id != partner:
            raise request.not_found()
        transaction = order.transaction_ids.filtered(
            lambda tx: tx.state == 'pending'
            and tx.provider_id.custom_mode == 'qris_static'
        )[:1]
        if not transaction:
            return request.redirect('/my/orders')
        request.session['__payment_monitored_tx_id__'] = transaction.id
        return request.redirect('/payment/status')

    @http.route('/my/orders/<int:order_id>/qris/proof', type='http', auth='user', website=True,
                sitemap=False)
    def view_qris_proof(self, order_id, **kwargs):
        """Serve only the logged-in student's own QRIS proof inline."""
        partner = request.env.user.partner_id.commercial_partner_id
        order = request.env['sale.order'].sudo().browse(order_id).exists()
        if not order or order.partner_id.commercial_partner_id != partner:
            raise request.not_found()
        transaction = order.transaction_ids.filtered(
            lambda tx: tx.provider_id.custom_mode == 'qris_static'
            and tx.qris_proof_attachment_id
        )[:1]
        if not transaction:
            raise request.not_found()
        attachment = transaction.qris_proof_attachment_id.sudo()
        content = base64.b64decode(attachment.datas or b'')
        return request.make_response(content, headers=[
            ('Content-Type', attachment.mimetype or 'application/octet-stream'),
            ('Content-Length', str(len(content))),
            ('Content-Disposition', 'inline; filename="%s"' % attachment.name.replace('"', '')),
            ('X-Content-Type-Options', 'nosniff'),
        ])

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
