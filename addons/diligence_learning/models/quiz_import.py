import base64

from odoo import _, fields, models, Command
from odoo.exceptions import AccessError, UserError


class SlideSlide(models.Model):
    _inherit = 'slide.slide'

    def _check_quiz_spreadsheet_access(self):
        self.ensure_one()
        if self.is_category or not self.channel_id.can_upload:
            raise AccessError(_('You cannot manage quiz questions for this course content.'))

    def action_open_quiz_import_wizard(self):
        self.ensure_one()
        self._check_quiz_spreadsheet_access()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Import Quiz Questions'),
            'res_model': 'diligence.quiz.import.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_slide_id': self.id},
        }

    def action_open_quiz_import_guide(self):
        self.ensure_one()
        self._check_quiz_spreadsheet_access()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Excel Import Format Guide'),
            'res_model': 'diligence.quiz.import.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_slide_id': self.id, 'default_guide_only': True},
        }

    def action_download_quiz_import_template(self):
        self.ensure_one()
        self._check_quiz_spreadsheet_access()
        return {
            'type': 'ir.actions.act_url',
            'url': '/slides/slide/quiz/import_template',
            'target': 'self',
        }

    def action_export_quiz_questions(self):
        self.ensure_one()
        self._check_quiz_spreadsheet_access()
        return {
            'type': 'ir.actions.act_url',
            'url': '/slides/slide/%s/quiz/export' % self.id,
            'target': 'self',
        }

    def _build_quiz_questions_xlsx(self):
        self.ensure_one()
        self._check_quiz_spreadsheet_access()
        import io
        import xlsxwriter

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Quiz Questions')
        headers = [
            'Question', 'Question Type', 'Weight', 'Required', 'Allow Partial Score',
            'Listening Answer Type', 'Accepted Answers', 'Grading Rubric',
            'Answer 1', 'Correct 1', 'Comment 1', 'Answer 2', 'Correct 2', 'Comment 2',
            'Answer 3', 'Correct 3', 'Comment 3', 'Answer 4', 'Correct 4', 'Comment 4',
            'Feedback After Submit',
        ]
        header_format = workbook.add_format({'bold': True, 'bg_color': '#D9EAF7', 'border': 1, 'text_wrap': True})
        text_format = workbook.add_format({'text_wrap': True, 'valign': 'top'})
        for column, header in enumerate(headers):
            sheet.write(0, column, header, header_format)
            sheet.set_column(column, column, 20)
        sheet.set_column(0, 0, 42)
        sheet.set_column(6, 7, 42)

        for row_index, question in enumerate(self.question_ids.sorted('sequence'), start=1):
            answers = question.answer_ids.sorted('sequence')
            accepted_answers = [
                line for line in (question.short_answer_variants or '').splitlines() if line.strip()
            ]
            if not accepted_answers and (
                question.question_type == 'short_answer'
                or question.question_type == 'listening' and question.listening_answer_type == 'short_answer'
            ):
                accepted_answers = question.answer_ids.filtered('is_correct').sorted('sequence').mapped('text_value')
            accepted = '\n'.join(accepted_answers)
            row = [
                question.question,
                question.question_type or 'single_choice',
                question.weight or 1,
                'TRUE' if question.required else 'FALSE',
                'TRUE' if question.allow_partial_score else 'FALSE',
                question.listening_answer_type or '',
                accepted.replace('\n', '|'),
                question.grading_rubric or '',
            ]
            for slot in range(4):
                answer = answers[slot] if slot < len(answers) else False
                row.extend([
                    answer.text_value if answer else '',
                    ('TRUE' if answer.is_correct else 'FALSE') if answer else '',
                    answer.comment or '' if answer else '',
                ])
            row.append('TRUE' if question.feedback_after_submit else 'FALSE')
            for column, value in enumerate(row):
                sheet.write(row_index, column, value, text_format)

        sheet.freeze_panes(1, 0)
        if self.question_ids:
            sheet.autofilter(0, 0, len(self.question_ids), len(headers) - 1)
        workbook.close()
        return output.getvalue()


class DiligenceQuizImportWizard(models.TransientModel):
    _name = 'diligence.quiz.import.wizard'
    _description = 'Import Quiz Questions from Excel'

    slide_id = fields.Many2one('slide.slide', required=True, readonly=True)
    guide_only = fields.Boolean(default=False)
    file_data = fields.Binary(string='Excel file (.xlsx)')
    file_name = fields.Char(string='Filename')

    def action_download_template(self):
        self.ensure_one()
        self.slide_id._check_quiz_spreadsheet_access()
        return {
            'type': 'ir.actions.act_url',
            'url': '/slides/slide/quiz/import_template',
            'target': 'self',
        }

    def action_import(self):
        self.ensure_one()
        slide = self.slide_id
        slide._check_quiz_spreadsheet_access()
        if not self.file_data:
            raise UserError(_('Please select an Excel file to import.'))
        if self.file_name and not self.file_name.lower().endswith('.xlsx'):
            raise UserError(_('Please upload an .xlsx Excel file.'))

        try:
            content = base64.b64decode(self.file_data)
        except (ValueError, TypeError) as exc:
            raise UserError(_('The uploaded file is not valid Base64 content.')) from exc

        question_model = self.env['slide.question']
        prepared_questions = question_model._prepare_questions_from_xlsx(slide, content)
        next_sequence = max(slide.question_ids.mapped('sequence') or [0]) + 1
        for values in prepared_questions:
            values = dict(values)
            answers = values.pop('answer_ids', [])
            values.update({
                'sequence': next_sequence,
                'answer_ids': [Command.create(answer) for answer in answers],
            })
            question_model.create(values)
            next_sequence += 1

        self.env['slide.slide.partner'].search([
            ('slide_id', '=', slide.id),
            ('partner_id', '=', self.env.user.partner_id.id),
        ]).write({'completed': False})
        return {'type': 'ir.actions.act_window_close'}

