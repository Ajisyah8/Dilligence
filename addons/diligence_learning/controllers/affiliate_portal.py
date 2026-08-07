from odoo import http
from odoo.http import request


class DiligenceAffiliatePortal(http.Controller):
    @http.route('/my/affiliate', type='http', auth='user', website=True)
    def my_affiliate(self, **kwargs):
        partner = request.env.user.partner_id.commercial_partner_id
        if not partner.diligence_is_affiliate:
            return request.not_found()
        referrals = request.env['diligence.referral'].search([
            ('affiliate_id', 'child_of', partner.id),
        ])
        settlements = request.env['diligence.referral.settlement'].search([
            ('affiliate_id', 'child_of', partner.id),
        ])
        masked_referrals = [{
            'name': referral.name,
            'student': (referral.student_id.name[:1] + '***') if referral.student_id.name else 'Student',
            'program': referral.program_id.name,
            'payment': referral.net_payment,
            'cashback': referral.cashback_amount,
            'status': dict(referral._fields['status'].selection).get(referral.status),
            'date': referral.registration_date,
        } for referral in referrals]
        return request.render('diligence_learning.portal_my_affiliate', {
            'partner': partner,
            'referral_link': request.httprequest.host_url.rstrip('/') + '/diligence/referral/' + partner.diligence_referral_code,
            'referrals': masked_referrals,
            'settlements': settlements,
        })

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

    @http.route(['/my/consultation', '/my/consultations'], type='http', auth='user', website=True)
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
