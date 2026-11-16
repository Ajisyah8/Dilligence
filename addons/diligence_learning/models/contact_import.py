import base64
import io
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class DiligenceContactImportWizard(models.TransientModel):
    _name = 'diligence.contact.import.wizard'
    _description = 'Import Contacts from Excel'

    file_data = fields.Binary(string='Excel file (.xlsx)')
    file_name = fields.Char(string='Filename')
    duplicate_policy = fields.Selection([
        ('update', 'Update matching contacts'),
        ('skip', 'Skip matching contacts'),
    ], default='update', required=True, string='When email or phone already exists')

    _HEADERS = {
        'name': ('name', 'contact name'),
        'email': ('email', 'email address'),
        'phone': ('phone / whatsapp', 'phone', 'whatsapp'),
        'function': ('job title', 'position'),
        'street': ('street', 'address'),
        'city': ('city',),
        'country_code': ('country code',),
        'lang_code': ('language code', 'language'),
        'segment': ('diligence segment', 'segment'),
        'newsletter_opt_in': ('newsletter opt-in', 'newsletter consent'),
    }
    _SEGMENTS = {
        'student': 'student',
        'customer': 'customer',
        'newsletter': 'newsletter',
        'newsletter subscriber': 'newsletter',
        'referral_non_student': 'referral_non_student',
        'referral - non student': 'referral_non_student',
        'affiliate': 'affiliate',
        'affiliate / referrer': 'affiliate',
        'other': 'other',
    }

    @staticmethod
    def _text(value):
        if value is None:
            return ''
        return str(value).strip()

    @staticmethod
    def _header(value):
        return re.sub(r'\s+', ' ', str(value or '').strip().casefold())

    def _parse_boolean(self, value, row_number):
        raw = self._text(value).casefold()
        if not raw:
            return None
        if raw in ('true', 'yes', 'y', '1', 'ya'):
            return True
        if raw in ('false', 'no', 'n', '0', 'tidak'):
            return False
        raise ValidationError(_('Row %(row)s: Newsletter Opt-In must be TRUE or FALSE.', row=row_number))

    def _read_rows(self, content):
        try:
            from openpyxl import load_workbook
        except ImportError as exc:
            raise UserError(_('The Python package openpyxl is required to import Excel files.')) from exc
        try:
            workbook = load_workbook(io.BytesIO(content), data_only=True, read_only=True)
            sheet = workbook['Contacts'] if 'Contacts' in workbook.sheetnames else workbook.active
            rows = sheet.iter_rows(values_only=True)
            headers = [self._header(value) for value in next(rows, ())]
        except Exception as exc:
            raise ValidationError(_('The uploaded file is not a readable .xlsx workbook.')) from exc

        columns = {}
        for key, aliases in self._HEADERS.items():
            for index, header in enumerate(headers):
                if header in aliases:
                    columns[key] = index
                    break
        if 'name' not in columns:
            raise ValidationError(_('The first worksheet must contain a Name column.'))

        country_by_code = {
            country.code.upper(): country.id
            for country in self.env['res.country'].sudo().search([('code', '!=', False)])
        }
        language_by_code = {
            lang.code.casefold(): lang.code
            for lang in self.env['res.lang'].sudo().search([('active', '=', True)])
        }
        service = self.env['diligence.whatsapp.service'].sudo()
        prepared = []
        seen_emails = set()
        seen_phones = set()
        for row_number, row in enumerate(rows, start=2):
            if not any(value not in (None, '') for value in row):
                continue

            def cell(key):
                index = columns.get(key)
                return row[index] if index is not None and index < len(row) else None

            name = self._text(cell('name'))
            if not name:
                raise ValidationError(_('Row %(row)s: Name is required.', row=row_number))
            email = self._text(cell('email')).casefold() or False
            if email and (not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email)):
                raise ValidationError(_('Row %(row)s: Email address is invalid.', row=row_number))
            phone = self._text(cell('phone')) or False
            normalized_phone = service.normalize_number(phone) if phone else False
            if phone and not normalized_phone:
                raise ValidationError(_('Row %(row)s: Phone / WhatsApp number is invalid.', row=row_number))
            if email and email in seen_emails:
                raise ValidationError(_('Row %(row)s duplicates an email already listed in this workbook.', row=row_number))
            if normalized_phone and normalized_phone in seen_phones:
                raise ValidationError(_('Row %(row)s duplicates a phone number already listed in this workbook.', row=row_number))
            if email:
                seen_emails.add(email)
            if normalized_phone:
                seen_phones.add(normalized_phone)

            raw_segment = self._text(cell('segment')).casefold()
            segment = self._SEGMENTS.get(raw_segment)
            if raw_segment and not segment:
                raise ValidationError(_(
                    'Row %(row)s: Segment must be student, customer, newsletter, referral_non_student, affiliate, or other.',
                    row=row_number,
                ))
            country_code = self._text(cell('country_code')).upper()
            if country_code and country_code not in country_by_code:
                raise ValidationError(_('Row %(row)s: Country Code %(code)s was not found.', row=row_number, code=country_code))
            lang_code = self._text(cell('lang_code')).casefold()
            if lang_code and lang_code not in language_by_code:
                raise ValidationError(_('Row %(row)s: Language Code %(code)s is not installed or active.', row=row_number, code=lang_code))

            values = {
                'name': name,
                'email': email,
                'phone': phone,
                'function': self._text(cell('function')) or False,
                'street': self._text(cell('street')) or False,
                'city': self._text(cell('city')) or False,
                'country_id': country_by_code.get(country_code) or False,
                'lang': language_by_code.get(lang_code) or False,
            }
            if segment:
                values['diligence_contact_segment'] = segment
            newsletter = self._parse_boolean(cell('newsletter_opt_in'), row_number)
            if newsletter is not None:
                values['diligence_newsletter_opt_in'] = newsletter
            # Empty optional cells do not erase existing values in update mode.
            clean_values = {key: value for key, value in values.items() if value not in (False, None, '')}
            if newsletter is not None:
                clean_values['diligence_newsletter_opt_in'] = newsletter
            prepared.append({
                'row': row_number,
                'values': clean_values,
                'email': email,
                'phone': phone,
                'normalized_phone': normalized_phone,
            })
        if not prepared:
            raise ValidationError(_('The Contacts worksheet contains no contact rows.'))
        return prepared

    def _find_existing(self, item):
        Partner = self.env['res.partner'].sudo()
        email_match = Partner.search([('email', '=ilike', item['email'])], limit=2) if item['email'] else Partner
        phone_matches = Partner
        if item['normalized_phone']:
            candidates = Partner.search([('phone', 'ilike', item['normalized_phone'][-8:])], limit=50)
            phone_matches = candidates.filtered(
                lambda partner: self.env['diligence.whatsapp.service'].sudo().normalize_number(partner.phone)
                == item['normalized_phone']
            )
        if len(email_match) > 1 or len(phone_matches) > 1:
            raise ValidationError(_('Row %(row)s matches multiple existing contacts. Resolve duplicates before importing.', row=item['row']))
        if email_match and phone_matches and email_match != phone_matches:
            raise ValidationError(_('Row %(row)s email and phone belong to different existing contacts.', row=item['row']))
        return email_match or phone_matches

    def action_download_template(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/diligence/contacts/import/template',
            'target': 'self',
        }

    def action_import(self):
        self.ensure_one()
        if not self.file_data:
            raise UserError(_('Select an Excel workbook first.'))
        if self.file_name and not self.file_name.lower().endswith('.xlsx'):
            raise UserError(_('Upload an .xlsx workbook.'))
        try:
            content = base64.b64decode(self.file_data)
        except (ValueError, TypeError) as exc:
            raise ValidationError(_('The uploaded file is not valid Base64 content.')) from exc

        prepared = self._read_rows(content)
        matches = [(item, self._find_existing(item)) for item in prepared]
        created = updated = skipped = 0
        Partner = self.env['res.partner'].sudo()
        for item, existing in matches:
            if existing:
                if self.duplicate_policy == 'skip':
                    skipped += 1
                    continue
                existing.write(item['values'])
                updated += 1
            else:
                Partner.create(item['values'])
                created += 1
        message = _('%(created)s created, %(updated)s updated, %(skipped)s skipped.',
                     created=created, updated=updated, skipped=skipped)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Contact import complete'),
                'message': message,
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    @api.model
    def _build_template(self):
        try:
            import xlsxwriter
        except ImportError as exc:
            raise UserError(_('The Python package xlsxwriter is required to create the Excel template.')) from exc
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Contacts')
        headers = [
            'Name', 'Email', 'Phone / WhatsApp', 'Job Title', 'Street', 'City',
            'Country Code', 'Language Code', 'Diligence Segment', 'Newsletter Opt-In',
        ]
        header_format = workbook.add_format({'bold': True, 'bg_color': '#D9EAF7', 'border': 1, 'text_wrap': True})
        for index, header in enumerate(headers):
            sheet.write(0, index, header, header_format)
            sheet.set_column(index, index, 22)
        sheet.set_column(0, 0, 28)
        sheet.set_column(1, 1, 32)
        sheet.set_column(2, 2, 22)
        sheet.freeze_panes(1, 0)
        sheet.autofilter(0, 0, 0, len(headers) - 1)
        guide = workbook.add_worksheet('Instructions')
        guide.write_column(0, 0, [
            'DILIGENCE ACADEMY — CONTACT IMPORT',
            'Isi satu kontak pada setiap baris di sheet Contacts. Jangan ubah nama kolom baris pertama.',
            'Name wajib. Email dan Phone / WhatsApp dipakai untuk mendeteksi duplikat.',
            'Jika email atau nomor cocok dengan kontak yang sudah ada, pilihan Update akan mengisi kolom yang tidak kosong; Skip akan melewatinya.',
            'Country Code memakai kode ISO, contoh ID. Language Code contoh id_ID, en_US, zh_CN; boleh dikosongkan.',
            'Diligence Segment: student, customer, newsletter, referral_non_student, affiliate, other.',
            'Newsletter Opt-In hanya isi TRUE jika kontak sudah memberi persetujuan menerima newsletter; selain itu isi FALSE atau kosong.',
            'Import memvalidasi seluruh baris terlebih dahulu. Jika ada kesalahan, tidak ada kontak yang diimpor.',
            'Simpan sebagai .xlsx dan unggah melalui Contacts > Import Contacts from Excel.',
        ])
        guide.set_column(0, 0, 115)
        guide.set_row(0, 28, workbook.add_format({'bold': True, 'font_size': 14, 'font_color': '#12546A'}))
        workbook.close()
        return output.getvalue()
