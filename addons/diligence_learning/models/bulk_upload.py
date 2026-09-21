import base64
import hashlib
import io
import os

from odoo import Command, _, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.pdf import PdfFileReader


class DiligenceBulkPdfUpload(models.TransientModel):
    _name = 'diligence.bulk.pdf.upload'
    _description = 'Bulk Upload PDF Materials'

    course_id = fields.Many2one(
        'slide.channel', string='Course', required=True, ondelete='cascade',
    )
    section_id = fields.Many2one(
        'slide.slide', string='Section',
        domain="[('channel_id', '=', course_id), ('is_category', '=', True)]",
        help='If empty, the new lessons are appended to the end of the course.',
    )
    attachment_ids = fields.Many2many(
        'ir.attachment', string='PDF / Audio files',
        help='Select or drag up to 50 PDF or audio files here, then click Upload.',
    )
    line_ids = fields.One2many(
        'diligence.bulk.pdf.upload.line', 'wizard_id', string='Upload results',
    )
    result_message = fields.Char(readonly=True)

    def _check_manager_access(self):
        if not (
            self.env.user.has_group('website_slides.group_website_slides_manager')
            or self.env.user._is_admin()
        ):
            raise AccessError(_('Only eLearning Managers can bulk upload course materials.'))
        self.course_id.check_access_rights('write')
        self.course_id.check_access_rule('write')

    def _validate_attachment(self, attachment):
        filename = attachment.name or ''
        extension = os.path.splitext(filename)[1].lower()
        allowed_mimetypes = {
            '.pdf': {'application/pdf'},
            '.mp3': {'audio/mpeg', 'audio/mp3', 'application/octet-stream'},
            '.wav': {'audio/wav', 'audio/x-wav', 'audio/wave', 'application/octet-stream'},
            '.ogg': {'audio/ogg', 'application/ogg', 'application/octet-stream'},
            '.webm': {'audio/webm', 'video/webm', 'application/octet-stream'},
        }
        if extension not in allowed_mimetypes:
            raise ValidationError(_('Only PDF, MP3, WAV, OGG, and WebM audio files are accepted.'))
        if attachment.mimetype not in allowed_mimetypes[extension]:
            raise ValidationError(_('The MIME type does not match the selected file extension.'))
        if not attachment.datas:
            raise ValidationError(_('The uploaded file is empty.'))
        content = base64.b64decode(attachment.datas)
        if not content:
            raise ValidationError(_('The uploaded file is empty.'))
        if extension == '.pdf':
            if not content.startswith(b'%PDF-'):
                raise ValidationError(_('The file is not a valid PDF.'))
            try:
                reader = PdfFileReader(io.BytesIO(content))
                if reader.getNumPages() < 1:
                    raise ValidationError(_('The PDF must contain at least one page.'))
            except ValidationError:
                raise
            except Exception as error:
                raise ValidationError(_('The PDF is corrupted or cannot be read.')) from error
            category = 'document'
        else:
            valid_audio_header = (
                content.startswith(b'ID3')
                or content[:2] in (b'\xff\xfb', b'\xff\xf3', b'\xff\xf2')
                or (content.startswith(b'RIFF') and content[8:12] == b'WAVE')
                or content.startswith(b'OggS')
                or content.startswith(b'\x1a\x45\xdf\xa3')
            )
            if not valid_audio_header:
                raise ValidationError(_('The audio file is corrupted or has an unsupported encoding.'))
            category = 'audio'

        max_size = int(self.env['ir.config_parameter'].sudo().get_param(
            'web.max_file_upload_size', 0,
        ) or 0)
        if max_size and len(content) > max_size:
            raise ValidationError(_(
                'The file exceeds the configured Odoo upload limit (%s bytes).', max_size,
            ))
        return content, category

    def _next_sequence(self, count):
        slides = self.course_id.slide_ids.sorted(key=lambda slide: (slide.sequence, slide.id))
        if not self.section_id:
            return (max(slides.mapped('sequence')) if slides else 0) + 1

        children = slides.filtered(lambda slide: slide.category_id == self.section_id)
        if children:
            sequence = max(children.mapped('sequence')) + 1
        else:
            sequence = self.section_id.sequence + 1
        following = slides.filtered(lambda slide: slide.sequence >= sequence)
        for slide in following.sorted(key=lambda item: (item.sequence, item.id), reverse=True):
            slide.sequence += count
        return sequence

    def _existing_checksum_slide(self, checksum):
        # Read only local PDF/audio lessons in this course. This is independent of
        # how Odoo stores an attachment for the binary field and also catches
        # retries after the temporary upload attachment has been removed.
        for slide in self.course_id.slide_ids.filtered(
            lambda item: item.slide_category in ('document', 'audio')
            and item.source_type == 'local_file'
            and item.binary_content
        ):
            content = base64.b64decode(slide.binary_content)
            if hashlib.sha1(content).hexdigest() == checksum:
                return slide
        return self.env['slide.slide']

    def action_upload(self):
        self.ensure_one()
        self._check_manager_access()
        attachments = self.attachment_ids
        if not attachments:
            raise UserError(_('Select at least one PDF or audio file.'))
        if len(attachments) > 50:
            raise UserError(_('You can upload a maximum of 50 PDF files at once.'))

        sequence = self._next_sequence(len(attachments))
        uploaded = 0
        failed = 0
        for attachment in attachments.sorted(key=lambda item: (item.name or '').lower()):
            line = self.env['diligence.bulk.pdf.upload.line'].create({
                'wizard_id': self.id,
                'attachment_id': attachment.id,
                'filename': attachment.name,
                'file_size': attachment.file_size,
                'content_type': 'document' if (attachment.name or '').lower().endswith('.pdf') else 'audio',
                'state': 'pending',
            })
            try:
                content, category = self._validate_attachment(attachment)
                # Match the SHA1 checksum used by ir.attachment so retries are
                # idempotent after the slide attachment is created.
                checksum = hashlib.sha1(content).hexdigest()
                duplicate = self._existing_checksum_slide(checksum)
                if duplicate:
                    line.write({
                        'state': 'duplicate',
                        'error_message': _('This PDF already exists in the selected course.'),
                        'slide_id': duplicate.id,
                    })
                    failed += 1
                    continue
                slide = self.env['slide.slide'].create({
                    'name': os.path.splitext(attachment.name)[0],
                    'channel_id': self.course_id.id,
                    'slide_category': category,
                    'source_type': 'local_file',
                    'binary_content': base64.b64encode(content),
                    'is_published': False,
                    'website_published': False,
                    'sequence': sequence,
                    'user_id': self.env.uid,
                })
                if category == 'audio' and 'diligence_audio_filename' in slide._fields:
                    slide.write({'diligence_audio_filename': attachment.name})
                sequence += 1
                line.write({
                    'state': 'uploaded',
                    'slide_id': slide.id,
                    'error_message': False,
                })
                uploaded += 1
            except (ValidationError, UserError) as error:
                line.write({'state': 'failed', 'error_message': str(error)})
                failed += 1
            finally:
                if line.state in ('uploaded', 'duplicate', 'failed'):
                    attachment.unlink()

        self.attachment_ids = [Command.clear()]
        self.result_message = _('%s uploaded, %s failed or skipped.', uploaded, failed)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bulk Upload Materials'),
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }


class DiligenceBulkPdfUploadLine(models.TransientModel):
    _name = 'diligence.bulk.pdf.upload.line'
    _description = 'Bulk PDF Upload Result'
    _order = 'id'

    wizard_id = fields.Many2one('diligence.bulk.pdf.upload', required=True, ondelete='cascade')
    attachment_id = fields.Many2one('ir.attachment', ondelete='set null', readonly=True)
    filename = fields.Char(readonly=True)
    file_size = fields.Integer(readonly=True)
    content_type = fields.Selection([
        ('document', 'PDF'),
        ('audio', 'Audio'),
    ], string='Type', readonly=True)
    state = fields.Selection([
        ('pending', 'Pending'),
        ('uploaded', 'Uploaded'),
        ('failed', 'Failed'),
        ('duplicate', 'Skipped: Duplicate'),
    ], required=True, default='pending', readonly=True)
    error_message = fields.Text(readonly=True)
    slide_id = fields.Many2one('slide.slide', string='Lesson', readonly=True)


class SlideChannelBulkPdfUpload(models.Model):
    _inherit = 'slide.channel'

    def action_open_bulk_pdf_upload(self):
        self.ensure_one()
        if not (
            self.env.user.has_group('website_slides.group_website_slides_manager')
            or self.env.user._is_admin()
        ):
            raise AccessError(_('Only eLearning Managers can bulk upload course materials.'))
        self.check_access_rights('write')
        self.check_access_rule('write')
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bulk Upload Materials'),
            'res_model': 'diligence.bulk.pdf.upload',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_course_id': self.id},
        }
