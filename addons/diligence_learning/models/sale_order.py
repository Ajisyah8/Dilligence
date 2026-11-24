from datetime import timedelta
import logging
import secrets
from urllib.parse import urlsplit

from odoo import Command, _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import html_escape

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    diligence_referral_code = fields.Char('Referral Code', copy=False)
    diligence_referrer_id = fields.Many2one('res.partner', 'Referrer', copy=False, readonly=True)
    diligence_referral_id = fields.Many2one('diligence.referral', 'Referral Attribution', copy=False, readonly=True)
    diligence_commission_amount = fields.Monetary('Manual Affiliate Cashback', copy=False)
    diligence_commission_status = fields.Selection([
        ('none', 'Not Applicable'),
        ('eligible', 'Eligible'),
        ('paid', 'Paid Manually'),
    ], default='none', copy=False)
    diligence_consultation_status = fields.Selection([
        ('not_applicable', 'Not Applicable'),
        ('new', 'New - Contact Learner'),
        ('scheduled', 'Coaching Scheduled'),
        ('ongoing', 'Coaching Ongoing'),
        ('completed', 'Completed'),
    ], default='not_applicable', copy=False)
    diligence_coach_id = fields.Many2one('res.users', 'Coach', copy=False)
    diligence_next_coaching_date = fields.Datetime('Next Coaching / Q&A', copy=False)
    diligence_coaching_link = fields.Char('Coaching / Q&A Link', copy=False)
    diligence_coaching_note = fields.Text('Coach Progress Note', copy=False)
    diligence_renewal_package_id = fields.Many2one('product.template', string='Renewal Package', copy=False, readonly=True, index=True)
    diligence_access_expires_at = fields.Datetime(string='Package Access Expires At', copy=False, readonly=True, index=True)
    diligence_renewal_status = fields.Selection([
        ('not_due', 'Not Due'),
        ('waiting', 'Waiting for Student'),
        ('continue', 'Wants to Continue'),
        ('not_continue', 'Will Not Continue'),
        ('renewed', 'Renewed'),
        ('expired', 'Expired - No Renewal'),
    ], string='Renewal Decision', default='not_due', copy=False, readonly=True, index=True)
    diligence_renewal_reason = fields.Selection([
        ('completed_material', 'Completed the learning materials'),
        ('no_time', 'No time to continue'),
        ('not_interested', 'Not interested in continuing'),
        ('other', 'Other'),
    ], string='Reason for Not Continuing', copy=False, readonly=True)
    diligence_renewal_reason_note = fields.Text(string='Other Renewal Reason', copy=False, readonly=True)
    diligence_renewal_whatsapp_phone = fields.Char(
        string='WhatsApp Number Confirmed for Opt-Out', copy=False, readonly=True,
        help='Number supplied by the learner when confirming they will not renew; used for group removal and retries.',
    )
    diligence_renewal_token = fields.Char(copy=False, readonly=True, index=True)
    diligence_renewal_reminder_sent_at = fields.Datetime(string='Renewal Reminder Sent At', copy=False, readonly=True)
    diligence_renewal_email_sent_at = fields.Datetime(string='Renewal Email Sent At', copy=False, readonly=True)
    diligence_renewal_whatsapp_sent_at = fields.Datetime(string='Renewal WhatsApp Sent At', copy=False, readonly=True)
    diligence_renewal_response_at = fields.Datetime(string='Renewal Response At', copy=False, readonly=True)
    diligence_renewed_by_order_id = fields.Many2one('sale.order', string='Renewed By Order', copy=False, readonly=True)
    diligence_package_switch_from_order_id = fields.Many2one(
        'sale.order', string='Package Switched From', copy=False, readonly=True, index=True,
        help='Previous paid package whose WhatsApp group access is reconciled after this package is activated.',
    )
    diligence_whatsapp_group_removal_state = fields.Selection([
        ('not_required', 'Not Required'),
        ('pending', 'Pending Group Removal'),
        ('removed', 'Removed from WhatsApp Group'),
        ('error', 'Group Removal Failed'),
    ], string='WhatsApp Group Removal', default='not_required', copy=False, readonly=True, index=True)
    diligence_whatsapp_group_removed_at = fields.Datetime(string='Removed from WhatsApp Group At', copy=False, readonly=True)

    def _verify_updated_quantity(self, order_line, product_id, new_qty, uom_id, **kwargs):
        quantity, warning = super()._verify_updated_quantity(
            order_line, product_id, new_qty, uom_id, **kwargs,
        )
        product = self.env['product.product'].browse(product_id).exists()
        if (
            new_qty > 0
            and product
            and (
                product.product_tmpl_id.diligence_package_type_id
                or product.product_tmpl_id.diligence_package_type
            )
            and product.product_tmpl_id.diligence_sales_status in ('full', 'coming_soon')
        ):
            current_quantity = order_line.product_uom_qty if order_line else 0
            return current_quantity, _(
                'The learning package “%(package)s” is currently full and cannot be purchased.',
                package=product.display_name,
            )
        if (
            new_qty > 0
            and product
            and product.product_tmpl_id._diligence_is_package()
            and not product.product_tmpl_id.diligence_has_available_course
        ):
            current_quantity = order_line.product_uom_qty if order_line else 0
            return current_quantity, _(
                'The learning package “%(package)s” is coming soon and cannot be purchased yet.',
                package=product.display_name,
            )
        if (
            new_qty > 0
            and product
            and product.product_tmpl_id._diligence_is_standalone_course_product()
            and (
                product.product_tmpl_id.diligence_sales_status in ('full', 'coming_soon')
                or not product.product_tmpl_id.diligence_has_available_course
            )
        ):
            current_quantity = order_line.product_uom_qty if order_line else 0
            return current_quantity, _(
                'The course “%(course)s” is not available for purchase yet.',
                course=product.display_name,
            )
        return quantity, warning

    def _diligence_package_lines(self):
        return self.order_line.filtered(lambda line: line.product_template_id._diligence_is_package())

    def _diligence_course_access_products(self):
        return self.order_line.mapped('product_template_id').filtered(
            lambda product: product._diligence_is_course_access_product()
        )

    def _diligence_referrer_for_code(self, code):
        """Return the active referrer for *code*, or an empty recordset.

        This is shared by the checkout form and the post-payment attribution
        flow so that a code preview cannot use rules different from the final
        referral attribution.
        """
        self.ensure_one()
        code = (code or '').strip().upper()
        if not code:
            return self.env['res.partner'].browse()
        referrer = self.env['res.partner'].sudo().search([
            ('diligence_referral_code', '=', code),
            ('diligence_is_affiliate', '=', True),
        ], limit=1)
        today = fields.Date.today()
        active_dates = referrer and (
            (not referrer.diligence_affiliate_start_date or referrer.diligence_affiliate_start_date <= today)
            and (not referrer.diligence_affiliate_end_date or referrer.diligence_affiliate_end_date >= today)
        )
        package = self._diligence_package_lines()[:1].product_template_id
        allowed_program = not referrer.diligence_affiliate_program_ids or package in referrer.diligence_affiliate_program_ids
        if not (referrer and active_dates and allowed_program):
            return self.env['res.partner'].browse()
        if referrer.commercial_partner_id == self.partner_id.commercial_partner_id:
            return self.env['res.partner'].browse()
        return referrer

    def _diligence_apply_referral(self):
        for order in self:
            code = (order.diligence_referral_code or '').strip().upper()
            if not code or order.diligence_referrer_id:
                continue
            referrer = order._diligence_referrer_for_code(code)
            package = order._diligence_package_lines()[:1].product_template_id
            # Referral attribution is per sale order.  The same student may
            # legitimately use the same referrer on a later transaction; do
            # not block that transaction because an earlier referral exists.
            if referrer:
                values = {
                    'diligence_referrer_id': referrer.id,
                    'diligence_commission_status': 'eligible',
                }
                order.write(values)
                referral = self.env['diligence.referral'].create({
                    'affiliate_id': referrer.id,
                    'student_id': order.partner_id.id,
                    'sale_order_id': order.id,
                    'program_id': package.id if package else False,
                    'referral_code': code,
                    'cashback_type': referrer._diligence_cashback_type_code(),
                    'cashback_type_id': referrer.diligence_cashback_type_id.id or False,
                    'cashback_rate': referrer.diligence_cashback_rate,
                    'cashback_fixed': referrer.diligence_cashback_fixed,
                    'status': 'pending_payment',
                })
                order.diligence_referral_id = referral.id

    def _diligence_grant_package_access(self):
        community_group = self.env.ref('diligence_learning.group_diligence_community_member')
        for order in self:
            access_products = order._diligence_course_access_products()
            if not access_products:
                continue
            order.partner_id.commercial_partner_id._diligence_set_primary_contact_segment('active_student')
            package_products = access_products.filtered(lambda product: product._diligence_is_package())
            renewal_package = package_products[:1]
            if renewal_package and renewal_package.diligence_access_duration_days and not order.diligence_access_expires_at:
                base_date = order.date_order or fields.Datetime.now()
                expires_at = base_date + timedelta(days=renewal_package.diligence_access_duration_days)
                order.write({
                    'diligence_renewal_package_id': renewal_package.id,
                    'diligence_access_expires_at': expires_at,
                    'diligence_renewal_status': 'not_due',
                    'diligence_renewal_token': secrets.token_urlsafe(32),
                })
            courses = self.env['slide.channel'].browse()
            for product in access_products:
                courses |= product._diligence_course_access_course_ids()
            # Grant membership for every course bundled with the paid product,
            # including courses marked Coming Soon. Their lessons remain hidden
            # until release, but the learner should not need to buy them again.
            courses.sudo()._action_add_members(order.partner_id)
            for course in courses:
                course._diligence_ensure_contact_segment()
                if course.diligence_contact_segment_id:
                    order.partner_id._diligence_assign_segment_codes([
                        course.diligence_contact_segment_id.code,
                    ])
            for access_product in access_products:
                membership = self.env['slide.channel.partner'].search([
                    ('channel_id', 'in', access_product._diligence_course_access_course_ids().ids),
                    ('partner_id', '=', order.partner_id.id),
                ])
                expiration = False
                if access_product.diligence_access_duration_days:
                    base_date = order.date_order or fields.Datetime.now()
                    expiration = base_date + timedelta(days=access_product.diligence_access_duration_days)
                membership.write({
                    'diligence_package_id': access_product.id,
                    'diligence_access_expires_at': expiration,
                })

            if package_products.filtered('diligence_forum_access'):
                portal_users = order.partner_id.user_ids.filtered(lambda user: user.active and user.share)
                portal_users.write({'group_ids': [Command.link(community_group.id)]})

            if package_products.filtered('diligence_consultation'):
                order.diligence_consultation_status = 'new'
                order.activity_schedule(
                    'mail.mail_activity_data_todo',
                    summary=_('Contact Consultation learner'),
                    note=_('Arrange coaching, learning-progress review, and live Q&A via WhatsApp or Zoom.'),
                )

            session_packages = package_products.filtered(
                lambda package: package._diligence_delivery_mode_code() != 'self'
            )
            for package in session_packages:
                session = self.env['diligence.session'].search([
                    ('package_id', '=', package.id),
                    ('state', '=', 'scheduled'),
                    ('start_datetime', '>=', fields.Datetime.now()),
                ], order='start_datetime asc', limit=1)
                if session and (not session.capacity or session.attendee_count < session.capacity):
                    self.env['diligence.session.attendee'].create({
                        'session_id': session.id,
                        'partner_id': order.partner_id.id,
                        'sale_order_id': order.id,
                    })

            if self.env['ir.config_parameter'].sudo().get_param(
                'diligence.whatsapp.send_on_payment', 'False'
            ) == 'True':
                self.env['diligence.whatsapp.service'].queue_payment_confirmation(order)

            order._diligence_reconcile_package_switch_groups(package_products)

            if renewal_package:
                order._diligence_mark_previous_package_orders_renewed(renewal_package)

    def _diligence_reconcile_package_switch_groups(self, new_packages):
        """Move WhatsApp group access only after the replacement package is activated."""
        service = self.env['diligence.whatsapp.service'].sudo()
        now = fields.Datetime.now()
        for order in self:
            previous = order.diligence_package_switch_from_order_id
            if (
                not previous or not new_packages
                or previous.partner_id != order.partner_id
            ):
                continue
            phone = service.normalize_number(order.partner_id.phone)
            if not phone:
                _logger.warning('Cannot reconcile package WhatsApp groups for order %s: account phone is missing/invalid', order.name)
                continue

            previous_package = previous.diligence_renewal_package_id
            old_group = previous_package.diligence_whatsapp_group_jid if previous_package else False
            new_groups = set(new_packages.mapped('diligence_whatsapp_group_jid')) - {False, ''}

            # A transition between group-bearing packages joins the new tier's
            # group but deliberately retains the old group. The learner leaves
            # package groups only when switching to a package with no group.
            for group_jid in new_groups:
                if group_jid != old_group:
                    service.add_group_participant(group_jid, phone)

            previous.write({
                'diligence_renewal_status': 'renewed',
                'diligence_renewed_by_order_id': order.id,
            })
            if not new_groups:
                # Starter Pack has no group entitlement. Remove every group
                # retained through earlier Community/Coaching switches, unless
                # another currently active package still grants that same group.
                package_orders = self.search([
                    ('partner_id', '=', order.partner_id.id),
                    ('state', 'in', ('sale', 'done')),
                    ('diligence_access_expires_at', '>', now),
                    ('diligence_renewal_package_id.diligence_whatsapp_group_jid', '!=', False),
                ])
                entitled_orders = package_orders.filtered(
                    lambda candidate: candidate.diligence_renewal_status
                    not in ('not_continue', 'renewed', 'expired')
                )
                entitled_groups = set(
                    entitled_orders.mapped('diligence_renewal_package_id.diligence_whatsapp_group_jid')
                )
                groups_to_remove = set(
                    package_orders.mapped('diligence_renewal_package_id.diligence_whatsapp_group_jid')
                ) - {False, ''} - entitled_groups
                for group_jid in groups_to_remove:
                    result = service.remove_group_participant(group_jid, phone)
                    related_orders = package_orders.filtered(
                        lambda candidate: candidate.diligence_renewal_package_id.diligence_whatsapp_group_jid == group_jid
                    )
                    related_orders.write({
                        'diligence_whatsapp_group_removal_state': 'removed' if result.get('removed') else 'error',
                        'diligence_whatsapp_group_removed_at': now if result.get('removed') else False,
                    })

    def _diligence_mark_previous_package_orders_renewed(self, package):
        self.ensure_one()
        previous_orders = self.search([
            ('id', '!=', self.id),
            ('partner_id', '=', self.partner_id.id),
            ('state', 'in', ('sale', 'done')),
            ('diligence_renewal_package_id', '=', package.id),
            ('diligence_renewal_status', '!=', 'renewed'),
        ])
        previous_orders.write({
            'diligence_renewal_status': 'renewed',
            'diligence_renewed_by_order_id': self.id,
        })

    @api.model
    def _cron_send_package_renewal_reminders(self):
        now = fields.Datetime.now()
        reminder_days = 3
        expires_before = now + timedelta(days=reminder_days)
        legacy_orders = self.sudo().search([
            ('state', 'in', ('sale', 'done')),
            ('diligence_access_expires_at', '=', False),
            ('order_line.product_template_id.diligence_access_duration_days', '>', 0),
        ])
        for order in legacy_orders.filtered(lambda item: item._diligence_has_valid_package_payment()):
            package = order._diligence_package_lines()[:1].product_template_id
            if not package:
                continue
            memberships = self.env['slide.channel.partner'].sudo().search([
                ('partner_id', 'child_of', order.partner_id.commercial_partner_id.id),
                ('channel_id', 'in', package._diligence_course_access_course_ids().ids),
                ('diligence_package_id', '=', package.id),
                ('diligence_access_expires_at', '!=', False),
            ])
            expires_at = max(memberships.mapped('diligence_access_expires_at'), default=False)
            if expires_at:
                order.write({
                    'diligence_renewal_package_id': package.id,
                    'diligence_access_expires_at': expires_at,
                    'diligence_renewal_status': 'not_due',
                    'diligence_renewal_token': secrets.token_urlsafe(32),
                })
        expired_orders = self.sudo().search([
            ('state', 'in', ('sale', 'done')),
            ('diligence_access_expires_at', '<', now),
            ('diligence_renewal_status', 'in', ('not_due', 'waiting', 'continue')),
        ])
        expired_orders.write({'diligence_renewal_status': 'expired'})
        orders = self.sudo().search([
            ('state', 'in', ('sale', 'done')),
            ('diligence_renewal_package_id', '!=', False),
            ('diligence_access_expires_at', '>', now),
            ('diligence_access_expires_at', '<=', expires_before),
            '|',
            ('diligence_renewal_reminder_sent_at', '=', False),
            '|',
            ('diligence_renewal_email_sent_at', '=', False),
            ('diligence_renewal_whatsapp_sent_at', '=', False),
            ('diligence_renewal_status', 'in', ('not_due', 'waiting')),
        ])
        for order in orders:
            if not order._diligence_has_valid_package_payment():
                continue
            # Old reminders had one combined timestamp only. Do not resend those
            # when the per-channel tracking fields are first introduced.
            if (
                order.diligence_renewal_reminder_sent_at
                and not order.diligence_renewal_email_sent_at
                and not order.diligence_renewal_whatsapp_sent_at
            ):
                continue
            website = order.website_id or self.env['website'].get_current_website()
            base_url = website.get_base_url() if website else self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            renewal_url = '%s/diligence/package-renewal/%s' % (
                base_url.rstrip('/'), order.diligence_renewal_token,
            )
            continue_url = '%s?intent=continue' % renewal_url
            not_continue_url = '%s?intent=not_continue' % renewal_url
            change_package_url = '%s?intent=change_package' % renewal_url
            expiry_label = fields.Datetime.context_timestamp(order, order.diligence_access_expires_at).strftime('%d %B %Y')
            message = (
                'Halo %(name)s, masa akses paket %(package)s akan berakhir pada %(expiry)s.\n\n'
                'Silakan pilih salah satu:\n'
                '1. LANJUT — buka checkout untuk membeli paket yang sama: %(continue_url)s\n'
                '2. GANTI PAKET — pilih paket lain dan bayar harga penuh paket tersebut: %(change_package_url)s\n'
                '3. TIDAK LANJUT — pilih alasan berhenti: %(not_continue_url)s\n\n'
                'Akses belajar yang sudah dibayar tetap aktif sampai tanggal berakhir.'
            ) % {
                'name': order.partner_id.name or 'Siswa',
                'package': order.diligence_renewal_package_id.name,
                'expiry': expiry_label,
                'continue_url': continue_url,
                'change_package_url': change_package_url,
                'not_continue_url': not_continue_url,
            }
            service = self.env['diligence.whatsapp.service'].sudo()
            delivery = self.env['diligence.whatsapp.delivery'].sudo().search([
                ('sale_order_id', '=', order.id),
                ('kind', '=', 'renewal_reminder'),
            ], limit=1)
            if not delivery:
                delivery = self.env['diligence.whatsapp.delivery'].sudo().create({
                    'sale_order_id': order.id,
                    'partner_id': order.partner_id.commercial_partner_id.id,
                    'kind': 'renewal_reminder',
                    'message': message,
                })
            elif delivery.state != 'sent':
                delivery.write({'message': message})
            if not order.diligence_renewal_whatsapp_sent_at:
                delivery.action_send()
            whatsapp_sent = delivery.state == 'sent'
            email_sent = False
            if order.partner_id.email and not order.diligence_renewal_email_sent_at:
                try:
                    sender_domain = urlsplit(website.domain).hostname if website and website.domain else False
                    sender = (
                        'Diligence Academy <admin@%s>' % sender_domain
                        if sender_domain else
                        self.env['ir.config_parameter'].sudo().get_param('mail.default.from') or False
                    )
                    mail = self.env['mail.mail'].sudo().create({
                        'subject': _('Your learning package is nearing its end'),
                        'email_to': order.partner_id.email,
                        'email_from': sender,
                        'body_html': (
                            '<div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;color:#173642">'
                            '<p>%s</p><p style="margin:24px 0">'
                            '<a href="%s" style="display:inline-block;background:#0d6678;color:#fff;'
                            'padding:12px 20px;border-radius:6px;text-decoration:none;margin-right:8px">'
                            'Continue and go to checkout</a>'
                            '<a href="%s" style="display:inline-block;background:#f2f4f5;color:#173642;'
                            'padding:12px 20px;border-radius:6px;text-decoration:none;margin-right:8px">Change package</a>'
                            '<a href="%s" style="display:inline-block;background:#f2f4f5;color:#173642;'
                            'padding:12px 20px;border-radius:6px;text-decoration:none">I will not continue</a>'
                            '</p><p style="color:#667">If you choose not to continue, you can tell us why on the next page. '
                            'Your current access remains available until its expiry date.</p></div>'
                            % (
                                html_escape(message.replace(renewal_url, '').strip()),
                                html_escape(continue_url),
                                html_escape(change_package_url),
                                html_escape(not_continue_url),
                            )
                        ),
                    })
                    mail.send(raise_exception=False)
                    email_sent = mail.state == 'sent'
                except Exception:
                    _logger.exception('Failed to send package renewal email for order %s', order.name)
            update = {}
            if email_sent:
                update['diligence_renewal_email_sent_at'] = now
            if whatsapp_sent:
                update['diligence_renewal_whatsapp_sent_at'] = now
            if update:
                update.update({
                    'diligence_renewal_status': 'waiting',
                    'diligence_renewal_reminder_sent_at': now,
                })
                order.write(update)

        self._cron_remove_expired_nonrenewing_students_from_whatsapp()
        return True

    @api.model
    def _cron_remove_expired_nonrenewing_students_from_whatsapp(self):
        """Retry group removals that failed after a learner opted out."""
        orders = self.sudo().search([
            ('state', 'in', ('sale', 'done')),
            ('diligence_renewal_status', '=', 'not_continue'),
            ('diligence_whatsapp_group_removal_state', 'in', ('pending', 'error')),
        ])
        for order in orders:
            order._diligence_remove_from_whatsapp_group()
        switched_orders = self.sudo().search([
            ('state', 'in', ('sale', 'done')),
            ('diligence_package_switch_from_order_id.diligence_whatsapp_group_removal_state', 'in', ('pending', 'error')),
        ])
        for order in switched_orders:
            packages = order._diligence_course_access_products().filtered(
                lambda product: product._diligence_is_package()
            )
            order._diligence_reconcile_package_switch_groups(packages)
        return True

    def _diligence_remove_from_whatsapp_group(self):
        """Remove a paid learner as soon as they confirm they will not renew."""
        now = fields.Datetime.now()
        service = self.env['diligence.whatsapp.service'].sudo()
        for order in self:
            if (
                order.state not in ('sale', 'done')
                or not order.diligence_renewal_package_id
                or not order.diligence_access_expires_at
                or not order._diligence_has_valid_package_payment()
            ):
                order.write({'diligence_whatsapp_group_removal_state': 'not_required'})
                continue
            # Never trust a phone number posted from the public renewal form.
            # Group actions must target the number on the learner's account.
            phone = order.partner_id.phone
            if not phone:
                order.write({'diligence_whatsapp_group_removal_state': 'not_required'})
                continue
            package_orders = self.search([
                ('partner_id', '=', order.partner_id.id),
                ('state', 'in', ('sale', 'done')),
                ('diligence_access_expires_at', '>', now),
                ('diligence_renewal_package_id.diligence_whatsapp_group_jid', '!=', False),
            ])
            active_orders = package_orders.filtered(
                lambda candidate: candidate.diligence_renewal_status
                not in ('not_continue', 'renewed', 'expired')
            )
            active_groups = set(
                active_orders.mapped('diligence_renewal_package_id.diligence_whatsapp_group_jid')
            )
            all_groups = set(
                package_orders.mapped('diligence_renewal_package_id.diligence_whatsapp_group_jid')
            ) - {False, ''}
            groups_to_remove = all_groups - active_groups
            if not groups_to_remove:
                order.write({'diligence_whatsapp_group_removal_state': 'not_required'})
                continue
            results = [
                (group_jid, service.remove_group_participant(group_jid, phone))
                for group_jid in groups_to_remove
            ]
            failed = False
            for group_jid, result in results:
                related_orders = package_orders.filtered(
                    lambda candidate: candidate.diligence_renewal_package_id.diligence_whatsapp_group_jid == group_jid
                )
                if result.get('removed'):
                    related_orders.write({
                        'diligence_whatsapp_group_removal_state': 'removed',
                        'diligence_whatsapp_group_removed_at': now,
                    })
                else:
                    related_orders.write({'diligence_whatsapp_group_removal_state': 'error'})
                    failed = True
            order.write({
                'diligence_whatsapp_group_removal_state': 'error' if failed else 'removed',
                'diligence_whatsapp_group_removed_at': False if failed else now,
            })
        return True

    def _diligence_has_valid_package_payment(self):
        self.ensure_one()
        if not self._diligence_course_access_products():
            return True
        return any(
            transaction.state == 'done'
            and transaction.currency_id == self.currency_id
            and transaction.amount == self.amount_total
            for transaction in self.transaction_ids
        )

    def _send_payment_succeeded_for_order_mail(self):
        """Send pending-payment mail only after a QRIS proof was uploaded."""
        if self.env.context.get('diligence_allow_pending_payment_email'):
            return super()._send_payment_succeeded_for_order_mail()
        qris_without_proof = self.filtered(lambda order: any(
            transaction.provider_id.custom_mode == 'qris_static'
            and transaction.state == 'pending'
            and not transaction.qris_proof_attachment_id
            for transaction in order.transaction_ids
        ))
        return super(SaleOrder, self - qris_without_proof)._send_payment_succeeded_for_order_mail()

    def _action_confirm(self):
        result = super()._action_confirm()
        paid_or_non_package = self.filtered(lambda order: order._diligence_has_valid_package_payment())
        paid_or_non_package._diligence_apply_referral()
        paid_or_non_package._diligence_grant_package_access()
        return result

    def action_mark_diligence_cashback_paid(self):
        self.ensure_one()
        if not self.diligence_referrer_id:
            raise ValidationError(_('This order has no valid referral.'))
        if self.diligence_referral_id:
            self.diligence_referral_id.action_mark_paid()
        self.diligence_commission_status = 'paid'

    def action_refresh_diligence_referral_payment(self):
        self.ensure_one()
        if not self.diligence_referral_id:
            raise ValidationError(_('This order has no referral attribution.'))
        self.diligence_referral_id.action_refresh_payment()
        self.diligence_commission_amount = self.diligence_referral_id.cashback_amount


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _get_display_price_ignore_combo(self):
        price = super()._get_display_price_ignore_combo()
        self.ensure_one()
        product = self.product_id.product_tmpl_id
        early_bird_price = product._diligence_early_bird_price_for_date(self._get_order_date())
        if early_bird_price:
            return product.currency_id._convert(
                early_bird_price,
                self.currency_id,
                self.company_id,
                self._get_order_date(),
            )
        return price
