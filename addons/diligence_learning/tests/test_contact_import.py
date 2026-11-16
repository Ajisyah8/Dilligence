import base64
import io

import xlsxwriter

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestDiligenceContactImport(TransactionCase):

    def _workbook(self, rows):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Contacts')
        sheet.write_row(0, 0, [
            'Name', 'Email', 'Phone / WhatsApp', 'Job Title', 'Street', 'City',
            'Country Code', 'Language Code', 'Diligence Segment', 'Newsletter Opt-In',
        ])
        for row_index, row in enumerate(rows, start=1):
            sheet.write_row(row_index, 0, row)
        workbook.close()
        return base64.b64encode(output.getvalue())

    def _wizard(self, rows, **kwargs):
        return self.env['diligence.contact.import.wizard'].create({
            'file_name': 'contacts.xlsx',
            'file_data': self._workbook(rows),
            **kwargs,
        })

    def test_import_creates_contact_and_respects_explicit_newsletter_consent(self):
        wizard = self._wizard([[
            'Import Student', 'import-student@example.com', '081234567890',
            'Teacher', 'Main Street', 'Batam', 'ID', 'id_ID', 'student', 'TRUE',
        ]])

        wizard.action_import()

        partner = self.env['res.partner'].search([('email', '=', 'import-student@example.com')])
        self.assertEqual(len(partner), 1)
        self.assertEqual(partner.phone, '081234567890')
        self.assertEqual(partner.city, 'Batam')
        self.assertEqual(partner.diligence_contact_segment, 'student')
        self.assertTrue(partner.diligence_newsletter_opt_in)

    def test_update_duplicate_keeps_empty_cells_and_can_withdraw_newsletter_consent(self):
        partner = self.env['res.partner'].create({
            'name': 'Existing Contact',
            'email': 'existing-contact@example.com',
            'phone': '628123456789',
            'city': 'Batam',
            'diligence_newsletter_opt_in': True,
        })
        wizard = self._wizard([[
            'Updated Contact', 'existing-contact@example.com', '', '', '', '', '', '', '', 'FALSE',
        ]])

        wizard.action_import()

        self.assertEqual(partner.name, 'Updated Contact')
        self.assertEqual(partner.city, 'Batam')
        self.assertFalse(partner.diligence_newsletter_opt_in)

    def test_invalid_workbook_row_is_rejected_before_contact_creation(self):
        wizard = self._wizard([
            ['Valid Contact', 'valid-contact@example.com', '', '', '', '', '', '', '', ''],
            ['Invalid Contact', 'not-an-email', '', '', '', '', '', '', '', ''],
        ])

        with self.assertRaises(ValidationError):
            wizard.action_import()

        self.assertFalse(self.env['res.partner'].search([('email', '=', 'valid-contact@example.com')]))

    def test_download_template_builds_a_valid_xlsx_workbook(self):
        content = self.env['diligence.contact.import.wizard']._build_template()
        self.assertTrue(content.startswith(b'PK'))
