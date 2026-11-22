import io

from odoo import http, _
from odoo.http import content_disposition, request
from werkzeug.exceptions import NotFound


class DiligenceEventRegistrationImportController(http.Controller):

    @http.route('/diligence/events/<int:event_id>/registrations/import/template',
                type='http', auth='user', website=False, sitemap=False)
    def download_event_registration_template(self, event_id, **kwargs):
        event = request.env['event.event'].browse(event_id).exists()
        if not event:
            raise NotFound()
        try:
            import xlsxwriter
        except ImportError as exc:
            from odoo.exceptions import UserError
            raise UserError(_('The Python package xlsxwriter is required to create this template.')) from exc
        headers = ['Name', 'Email', 'Phone', 'Company', 'Participant Type']
        custom_questions = event.question_ids.filtered(
            lambda question: question.question_type not in ('name', 'email', 'phone', 'company')
        )
        headers.extend('Question: %s' % question.title for question in custom_questions)
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Registrations')
        header_format = workbook.add_format({'bold': True, 'bg_color': '#D9EAF7', 'border': 1, 'text_wrap': True})
        for index, header in enumerate(headers):
            sheet.write(0, index, header, header_format)
            sheet.set_column(index, index, 26)
        sheet.freeze_panes(1, 0)
        sheet.autofilter(0, 0, 0, len(headers) - 1)
        guide = workbook.add_worksheet('Instructions')
        guide.write_column(0, 0, [
            'DILIGENCE ACADEMY — EVENT PARTICIPANT IMPORT',
            'Event: %s' % event.name,
            'Isi satu peserta per baris di sheet Registrations. Name dan Email wajib.',
            'Participant Type dapat diisi Student atau General. Jika kosong, sistem mengikuti Contact Segment pada kontak: Student menjadi Student, segment lain menjadi General.',
            'Jangan mengubah nama header. Pertanyaan event ditambahkan sebagai kolom Question: <judul pertanyaan>.',
            'Untuk pertanyaan pilihan, isi jawaban persis seperti salah satu opsi yang tersedia.',
            'Email yang sudah terdaftar di event ini akan dilewati, tidak dibuat ganda.',
            'Simpan workbook sebagai .xlsx lalu unggah lewat Events > Import Participants from Excel.',
        ])
        guide.set_column(0, 0, 110)
        workbook.close()
        content = output.getvalue()
        return request.make_response(content, headers=[
            ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('Content-Length', str(len(content))),
            ('Content-Disposition', content_disposition('event_%s_participants.xlsx' % event_id)),
        ])
