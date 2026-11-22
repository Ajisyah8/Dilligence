from datetime import timedelta

from odoo import SUPERUSER_ID, api, fields


def migrate(cr, version):
    """Grant missing course memberships for valid existing package purchases.

    Older versions skipped package courses marked Coming Soon. This adds only
    missing memberships; existing enrollment and lesson progress are untouched.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    teacher_segment = env['diligence.contact.segment'].search([
        ('code', '=', 'teacher'),
        ('active', '=', True),
    ], limit=1)
    if teacher_segment:
        legacy_coach_sessions = env['diligence.session'].search([
            ('coach_id', '!=', False),
            ('coach_partner_id', '=', False),
        ])
        for session in legacy_coach_sessions:
            teacher_contact = session.coach_id.partner_id
            if teacher_segment in teacher_contact.diligence_contact_segment_ids or teacher_contact.diligence_contact_segment_id == teacher_segment:
                session.coach_partner_id = teacher_contact.id

    orders = env['sale.order'].search([
        ('state', 'in', ('sale', 'done')),
        ('diligence_renewal_status', 'not in', ('not_continue', 'expired')),
    ])
    now = fields.Datetime.now()
    for order in orders:
        if not order._diligence_has_valid_package_payment():
            continue
        if order.diligence_access_expires_at and order.diligence_access_expires_at < now:
            continue

        products = order._diligence_course_access_products()
        if not products:
            continue
        courses = env['slide.channel'].browse()
        for product in products:
            courses |= product._diligence_course_access_course_ids()

        Membership = env['slide.channel.partner'].sudo()
        missing_courses = courses.filtered(lambda course: not Membership.search_count([
            ('channel_id', '=', course.id),
            ('partner_id', '=', order.partner_id.id),
            ('active', '=', True),
            ('member_status', 'in', ('joined', 'ongoing', 'completed')),
        ]))
        if not missing_courses:
            continue

        missing_courses.sudo()._action_add_members(order.partner_id)
        new_memberships = Membership.search([
            ('channel_id', 'in', missing_courses.ids),
            ('partner_id', '=', order.partner_id.id),
            ('active', '=', True),
        ])
        for product in products:
            product_memberships = new_memberships.filtered(
                lambda membership: membership.channel_id in product._diligence_course_access_course_ids()
            )
            if not product_memberships:
                continue
            expires_at = order.diligence_access_expires_at
            if not expires_at and product.diligence_access_duration_days:
                expires_at = (order.date_order or fields.Datetime.now()) + timedelta(
                    days=product.diligence_access_duration_days,
                )
            product_memberships.write({
                'diligence_package_id': product.id,
                'diligence_access_expires_at': expires_at,
            })
