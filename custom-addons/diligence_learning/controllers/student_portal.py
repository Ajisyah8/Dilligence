from odoo import http
from odoo.http import request


class DiligenceStudentPortal(http.Controller):
    @http.route('/my/courses', type='http', auth='user', website=True)
    def my_courses(self, **kwargs):
        partner = request.env.user.partner_id.commercial_partner_id
        memberships = request.env['slide.channel.partner'].sudo().search([
            ('partner_id', 'child_of', partner.id),
            ('active', '=', True),
            ('member_status', '!=', 'invited'),
        ])
        memberships = memberships.filtered(lambda membership: membership._diligence_access_is_valid())
        return request.render('diligence_learning.portal_my_courses', {
            'partner': partner,
            'memberships': memberships,
        })

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
