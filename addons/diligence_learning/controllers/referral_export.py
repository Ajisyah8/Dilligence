import csv
import io

from odoo import http
from odoo.exceptions import AccessError
from odoo.http import request


class DiligenceReferralExport(http.Controller):
    @http.route('/diligence/referrals/export', type='http', auth='user')
    def export_referrals(self, ids='', **kwargs):
        if not (
            request.env.user.has_group('sales_team.group_sale_manager')
            or request.env.user.has_group('account.group_account_invoice')
            or request.env.user.has_group('base.group_system')
        ):
            raise AccessError('You are not allowed to export referral data.')
        referral_ids = [int(value) for value in ids.split(',') if value.isdigit()]
        referrals = request.env['diligence.referral'].search(
            [('id', 'in', referral_ids)], order='payment_date desc, id desc'
        )
        output = io.StringIO(newline='')
        writer = csv.writer(output)
        writer.writerow([
            'Reference', 'Affiliate', 'Student', 'Referral Code', 'Sale Order',
            'Program', 'Payment Date', 'Payment Amount', 'Net Payment',
            'Cashback Amount', 'Status', 'Settlement', 'Paid Date',
        ])
        for referral in referrals:
            writer.writerow([
                referral.name,
                referral.affiliate_id.display_name,
                referral.student_id.display_name,
                referral.referral_code,
                referral.sale_order_id.name,
                referral.program_id.display_name,
                referral.payment_date or '',
                referral.payment_amount,
                referral.net_payment,
                referral.cashback_amount,
                referral.status,
                referral.settlement_id.name or '',
                referral.paid_date or '',
            ])
        return request.make_response(
            output.getvalue().encode('utf-8-sig'),
            headers=[
                ('Content-Type', 'text/csv; charset=utf-8'),
                ('Content-Disposition', 'attachment; filename="diligence_referrals.csv"'),
            ],
        )
