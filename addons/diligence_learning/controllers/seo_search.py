from odoo import http
from odoo.http import request


class DiligenceSeoSearchController(http.Controller):
    @http.route(
        '/diligence/seo/search-track',
        type='jsonrpc',
        auth='public',
        website=True,
        csrf=False,
        methods=['POST'],
        readonly=False,
    )
    def track_search(self, query=None, result_count=0, **kwargs):
        request.env['diligence.seo.search.term'].sudo().record_query(
            query, result_count=result_count
        )
        return {'ok': True}
