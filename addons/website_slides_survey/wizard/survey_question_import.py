# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64

from odoo import fields, models, _
from odoo.exceptions import ValidationError


class SurveyQuestionImportWizard(models.TransientModel):
    _name = 'survey.question.import.wizard'
    _description = 'Import Certification Questions'

    survey_id = fields.Many2one('survey.survey', required=True, readonly=True)
    import_file = fields.Binary(string='Excel File', required=True)
    import_filename = fields.Char(string='Filename')
    replace_existing = fields.Boolean(string='Replace Existing Questions', default=True)

    def action_import(self):
        self.ensure_one()
        if not self.import_file:
            raise ValidationError(_("Please upload an Excel file."))
        if self.import_filename and not self.import_filename.lower().endswith('.xlsx'):
            raise ValidationError(_("Please upload a .xlsx file."))

        file_content = base64.b64decode(self.import_file)
        created_questions = self.survey_id.import_certification_questions_from_xlsx(
            file_content,
            replace_existing=self.replace_existing,
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Import Complete'),
                'message': (
                    _('Certification questions replaced and imported successfully.')
                    if self.replace_existing else
                    _('%s question(s) imported successfully.') % len(created_questions.filtered(lambda q: not q.is_page))
                ),
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.client',
                    'tag': 'reload',
                },
            },
        }

    def action_download_template(self):
        self.ensure_one()
        return self.survey_id.action_download_question_import_template()
