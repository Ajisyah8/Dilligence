from odoo import http
from odoo.http import request, content_disposition
from werkzeug.exceptions import Forbidden


class DiligenceContactImportController(http.Controller):

    @http.route('/diligence/contacts/import/template', type='http', auth='user', website=True)
    def download_contact_import_template(self, **kwargs):
        if not request.env.user.has_group('base.group_user'):
            raise Forbidden()
        content = request.env['diligence.contact.import.wizard'].sudo()._build_template()
        return request.make_response(content, headers=[
            ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('Content-Disposition', content_disposition('diligence_contact_import_template.xlsx')),
            ('Content-Length', str(len(content))),
        ])
