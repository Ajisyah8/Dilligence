import logging

from odoo import _, fields, tools
from odoo.http import request, route
from odoo.addons.website_mass_mailing.controllers.main import MassMailController


_logger = logging.getLogger(__name__)


class DiligenceNewsletterController(MassMailController):
    """Use the Diligence list and create drip deliveries for public contacts."""

    @route('/website_mass_mailing/subscribe', type='jsonrpc', website=True, auth='public')
    def subscribe(self, list_id, value, subscription_type, **post):
        if subscription_type != 'email':
            return {
                'toast_type': 'danger',
                'toast_content': _('Please provide a valid email address.'),
            }

        email = (value or '').strip().lower()
        if not tools.single_email_re.fullmatch(email):
            return {
                'toast_type': 'danger',
                'toast_content': _('Masukkan alamat email yang valid.'),
            }

        try:
            mailing_list = request.env['mailing.list'].sudo().search([
                ('name', '=', 'Diligence Academy Newsletter'),
                ('active', '=', True),
            ], limit=1)
            if not mailing_list:
                _logger.error('Diligence newsletter list is missing.')
                return {
                    'toast_type': 'danger',
                    'toast_content': _('Pendaftaran newsletter gagal. Silakan coba lagi.'),
                }

            Contacts = request.env['mailing.contact'].sudo()
            Subscriptions = request.env['mailing.subscription'].sudo()
            contact = Contacts.search([('email', '=ilike', email)], limit=1)
            if not contact:
                name, email_domain = tools.parse_contact_from_email(email)
                contact = Contacts.create({'name': name or email.split('@')[0], 'email': email})

            subscription = Subscriptions.search([
                ('contact_id', '=', contact.id),
                ('list_id', '=', mailing_list.id),
            ], limit=1)
            already_subscribed = bool(subscription and not subscription.opt_out)
            if already_subscribed:
                request.session['mass_mailing_email'] = email
                return {
                    'toast_type': 'warning',
                    'toast_content': _('Email ini sudah terdaftar pada newsletter kami.'),
                }

            if subscription:
                subscription.write({'opt_out': False, 'opt_out_datetime': False, 'opt_out_reason_id': False})
            else:
                subscription = Subscriptions.create({
                    'contact_id': contact.id,
                    'list_id': mailing_list.id,
                })

            request.env['diligence.newsletter.delivery'].sudo()._create_deliveries_for_contact(
                contact, anchor=fields.Datetime.now(),
            )
            request.session['mass_mailing_email'] = email
            return {
                'toast_type': 'success',
                'toast_content': _(
                    'Terima kasih, Anda berhasil berlangganan newsletter Diligence Academy.'
                ),
            }
        except Exception as error:
            _logger.error('Public newsletter subscription failed (%s).', type(error).__name__)
            return {
                'toast_type': 'danger',
                'toast_content': _('Pendaftaran newsletter gagal. Silakan coba lagi.'),
            }
