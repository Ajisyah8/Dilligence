import base64
import io
import re

from odoo import _, fields, models
from odoo.exceptions import UserError, ValidationError


class DiligenceEventRegistrationImport(models.TransientModel):
    _name = 'diligence.event.registration.import'
    _description = 'Bulk Import Event Participants'

    event_id = fields.Many2one('event.event', required=True, string='Event')
    file_data = fields.Binary(string='Excel file (.xlsx)')
    file_name = fields.Char()

    @staticmethod
    def _header(value):
        return re.sub(r'\s+', ' ', str(value or '').strip().casefold())

    @staticmethod
    def _text(value):
        return str(value).strip() if value is not None else ''

    @staticmethod
    def _question_key(value):
        value = re.sub(r'^question\s*:\s*', '', str(value or '').strip(), flags=re.IGNORECASE)
        value = re.sub(r'\b(?:dan|and)\b', ' ', value, flags=re.IGNORECASE)
        value = re.sub(r'[^a-z0-9]+', '', value.casefold())
        # Accept the older event title typo found in previously downloaded files.
        return value.replace('provinsis', 'provinsi')

    @staticmethod
    def _choice_key(value):
        return re.sub(r'[^a-z0-9]+', '', str(value or '').casefold())

    def action_download_template(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/diligence/events/%s/registrations/import/template' % self.event_id.id,
            'target': 'self',
        }

    def action_import(self):
        self.ensure_one()
        if not self.file_data:
            raise UserError(_('Select an .xlsx workbook first.'))
        try:
            from openpyxl import load_workbook
            workbook = load_workbook(io.BytesIO(base64.b64decode(self.file_data)), data_only=True, read_only=True)
            sheet = workbook['Registrations'] if 'Registrations' in workbook.sheetnames else workbook.active
            rows = sheet.iter_rows(values_only=True)
            headers = [self._header(value) for value in next(rows, ())]
        except Exception as exc:
            raise ValidationError(_('The uploaded workbook is not a readable .xlsx file.')) from exc

        standard = {
            'name': 'name', 'email': 'email', 'phone': 'phone', 'company': 'company',
            'participant_type': 'participant type',
        }
        columns = {key: headers.index(label) for key, label in standard.items() if label in headers}
        if 'name' not in columns or 'email' not in columns:
            raise ValidationError(_('The Registrations sheet must include Name and Email columns.'))
        question_columns = {}
        # Name, email, phone and company are already represented by the
        # standard columns above. They must not be treated as extra question
        # columns (which made every row fail with "Nama is required").
        custom_questions = self.event_id.question_ids.filtered(
            lambda question: question.question_type not in ('name', 'email', 'phone', 'company')
        )
        for question in self.event_id.question_ids:
            if question not in custom_questions:
                continue
            titles = {question.title}
            for language in ('en_US', 'id_ID', 'zh_CN'):
                titles.add(question.with_context(lang=language).title)
            title_keys = {self._question_key(title) for title in titles if title}
            matching_columns = [
                index for index, header in enumerate(headers)
                if self._question_key(header) in title_keys
            ]
            if len(matching_columns) > 1:
                raise ValidationError(_('Question column “%(question)s” is ambiguous.', question=question.title))
            if matching_columns:
                question_columns[question.id] = matching_columns[0]

        Registration = self.env['event.registration'].sudo().with_context(import_file=True)
        existing_emails = {
            email.casefold()
            for email in Registration.search([
                ('event_id', '=', self.event_id.id), ('active', '=', True),
            ]).mapped('email')
            if email
        }
        prepared, seen_emails, skipped = [], set(), 0
        for row_number, row in enumerate(rows, start=2):
            if not any(value not in (None, '') for value in row):
                continue
            def cell(index):
                return row[index] if index is not None and index < len(row) else None
            name = self._text(cell(columns['name']))
            email = self._text(cell(columns['email'])).casefold()
            phone = self._text(cell(columns.get('phone')))
            company = self._text(cell(columns.get('company')))
            participant_type_text = self._text(cell(columns.get('participant_type'))).casefold()
            participant_type_aliases = {
                'student': 'student', 'siswa': 'student',
                'general': 'general', 'general public': 'general', 'umum': 'general', 'public': 'general',
            }
            participant_type = participant_type_aliases.get(participant_type_text)
            if participant_type_text and not participant_type:
                raise ValidationError(_(
                    'Row %(row)s: Participant Type must be Student or General.', row=row_number,
                ))
            if not name or not email or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
                raise ValidationError(_('Row %(row)s: a name and valid email are required.', row=row_number))
            if email in seen_emails:
                raise ValidationError(_('Row %(row)s repeats an email in this workbook.', row=row_number))
            seen_emails.add(email)
            # A retry after a failed standard Odoo import must be idempotent.
            # Ignore already-registered rows before requiring their answers;
            # a duplicate row may have been imported before the old savepoint
            # bug surfaced and should not block genuinely new participants.
            if email in existing_emails:
                skipped += 1
                continue
            answers = []
            for question in custom_questions:
                index = question_columns.get(question.id)
                answer_text = self._text(cell(index))
                if question.is_mandatory_answer and not answer_text:
                    raise ValidationError(_('Row %(row)s: “%(question)s” is required.', row=row_number, question=question.title))
                if not answer_text:
                    continue
                answer_vals = {'question_id': question.id}
                if question.question_type == 'simple_choice':
                    matches = question.answer_ids.filtered(
                        lambda item: self._choice_key(item.name) == self._choice_key(answer_text)
                    )
                    if len(matches) != 1:
                        raise ValidationError(_('Row %(row)s: “%(answer)s” is not an option for “%(question)s”.', row=row_number, answer=answer_text, question=question.title))
                    answer = matches
                    answer_vals['value_answer_id'] = answer.id
                else:
                    answer_vals['value_text_box'] = answer_text
                answers.append((0, 0, answer_vals))
            prepared.append({
                'row': row_number, 'name': name, 'email': email, 'phone': phone,
                'company': company, 'participant_type': participant_type, 'answers': answers,
            })
        if not prepared and not skipped:
            raise ValidationError(_('No participant rows were found.'))

        # Keep Odoo's after-subscription mail scheduler from committing inside
        # this import transaction. Its cron trigger runs only after commit.
        Partner = self.env['res.partner'].sudo()
        created = 0
        for item in prepared:
            if Registration.search_count([('event_id', '=', self.event_id.id), ('email', '=ilike', item['email']), ('active', '=', True)]):
                skipped += 1
                continue
            partner = Partner.search([('email', '=ilike', item['email'])], limit=1)
            if not partner:
                partner = Partner.create({
                    'name': item['name'], 'email': item['email'],
                    'phone': item['phone'] or False,
                })
            Registration.create({
                'event_id': self.event_id.id,
                'partner_id': partner.id,
                'name': item['name'], 'email': item['email'],
                'phone': item['phone'] or False,
                'company_name': item['company'] or False,
                'diligence_participant_type': item['participant_type'] or False,
                'registration_answer_ids': item['answers'],
            })
            created += 1
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {
                'title': _('Event import complete'),
                'message': _('%(created)s participant(s) imported; %(skipped)s duplicate(s) skipped.', created=created, skipped=skipped),
                'type': 'success', 'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
