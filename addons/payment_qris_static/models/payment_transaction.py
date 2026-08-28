import base64

from odoo import _, fields, models
from odoo.exceptions import AccessError, ValidationError


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    qris_proof_attachment_id = fields.Many2one(
        'ir.attachment',
        string='QRIS Payment Proof',
        readonly=True,
        copy=False,
        help='Payment proof uploaded by the customer for this QRIS transaction.',
    )
    qris_payment_proof = fields.Binary(
        string='QRIS Proof Download', related='qris_proof_attachment_id.datas', readonly=True,
    )
    qris_payment_proof_filename = fields.Char(
        string='Proof Filename', related='qris_proof_attachment_id.name', readonly=True,
    )
    qris_payment_amount = fields.Monetary(
        string='Amount Paid by Student', currency_field='currency_id', copy=False,
    )
    qris_order_amount = fields.Monetary(
        string='Sales Order Amount', currency_field='currency_id',
        compute='_compute_qris_order_amount',
    )
    qris_proof_uploaded_at = fields.Datetime(string='Proof Uploaded At', readonly=True, copy=False)
    qris_proof_uploaded_by = fields.Many2one('res.users', string='Proof Uploaded By', readonly=True, copy=False)
    qris_finance_note = fields.Text(string='Finance Note', copy=False)
    qris_rejection_reason = fields.Text(string='Rejection Reason', copy=False)

    def _compute_qris_order_amount(self):
        for transaction in self:
            transaction.qris_order_amount = (
                transaction.sale_order_ids[:1].amount_total
                if transaction.sale_order_ids else 0
            )

    def _set_done(self, state_message=None):
        """Never complete static QRIS before a proof is attached.

        A custom payment callback can be replayed or incorrectly report a
        successful payment.  Static QRIS has no gateway confirmation, so the
        uploaded receipt is the required confirmation signal.  Keeping this
        invariant at transaction level also protects callers other than the
        public upload controller.
        """
        unverified = self.filtered(
            lambda tx: tx.provider_code == 'custom'
            and tx.provider_id.custom_mode == 'qris_static'
            and not tx.qris_proof_attachment_id
        )
        if unverified:
            raise ValidationError(
                _('A QRIS payment proof is required before the payment can be confirmed.')
            )
        return super()._set_done(state_message=state_message)

    def _get_specific_rendering_values(self, processing_values):
        values = super()._get_specific_rendering_values(processing_values)
        if self.provider_code == 'custom' and self.provider_id.custom_mode == 'qris_static':
            values.update({
                'amount': self.amount,
                'qris_image': self.provider_id.qris_image,
                'qris_instructions': self.provider_id.qris_instructions,
            })
        return values

    def _apply_updates(self, payment_data):
        if self.provider_code != 'custom' or self.provider_id.custom_mode != 'qris_static':
            return super()._apply_updates(payment_data)

        # The first custom-payment redirect only creates a pending transaction. The proof is
        # uploaded on the payment status page and remains pending until Finance verifies it.
        return super()._apply_updates(payment_data)

    def _save_qris_proof(self, proof, paid_amount=None):
        self.ensure_one()
        if self.provider_code != 'custom' or self.provider_id.custom_mode != 'qris_static':
            raise ValidationError(_('This transaction is not a static QRIS transaction.'))
        if self.state not in ('draft', 'pending'):
            raise ValidationError(_('This payment is no longer awaiting a QRIS proof.'))
        if self.qris_proof_attachment_id:
            raise ValidationError(_('A QRIS payment proof has already been submitted.'))
        if not proof or not hasattr(proof, 'read'):
            raise ValidationError(_('Please upload your QRIS payment proof.'))

        content = proof.read()
        if not content:
            raise ValidationError(_('The uploaded payment proof is empty.'))
        if len(content) > 8 * 1024 * 1024:
            raise ValidationError(_('The payment proof must be smaller than 8 MB.'))

        allowed_mimetypes = {'image/jpeg', 'image/png', 'image/webp', 'application/pdf'}
        if proof.mimetype not in allowed_mimetypes:
            raise ValidationError(_('Please upload a JPG, PNG, WEBP, or PDF payment proof.'))

        if paid_amount in (None, ''):
            raise ValidationError(_('Enter the amount paid before submitting the proof.'))
        try:
            paid_amount = float(paid_amount)
        except (TypeError, ValueError) as error:
            raise ValidationError(_('Enter a valid payment amount.')) from error
        if self.currency_id.compare_amounts(paid_amount, self.amount) != 0:
            raise ValidationError(_('The payment amount does not match the order total.'))

        attachment = self.env['ir.attachment'].sudo().create({
            'name': proof.filename or f'{self.reference}-qris-proof',
            'type': 'binary',
            'datas': base64.b64encode(content),
            'mimetype': proof.mimetype or 'application/octet-stream',
            'res_model': self._name,
            'res_id': self.id,
        })
        self.write({
            'qris_proof_attachment_id': attachment.id,
            'qris_payment_amount': paid_amount,
            'qris_proof_uploaded_at': fields.Datetime.now(),
            'qris_proof_uploaded_by': self.env.uid if not self.env.user._is_public() else False,
            'state_message': _('QRIS payment proof uploaded. Waiting for Finance verification.'),
        })
        if self.state == 'draft':
            self._set_pending(state_message=_('QRIS payment proof uploaded.'))
        for order in self.sale_order_ids:
            order.message_post(body=_('QRIS payment proof uploaded and is waiting for Finance verification.'))

    def action_diligence_verify_qris(self):
        """Verify a static QRIS receipt and run normal post-processing."""
        if not (
            self.env.user.has_group('account.group_account_invoice')
            or self.env.user.has_group('account.group_account_manager')
            or self.env.user._is_admin()
        ):
            raise AccessError(_('Only Finance users can verify a QRIS payment.'))
        for transaction in self:
            if transaction.provider_code != 'custom' or transaction.provider_id.custom_mode != 'qris_static':
                raise ValidationError(_('This transaction is not a static QRIS transaction.'))
            if transaction.state == 'done':
                continue
            if transaction.state != 'pending' or not transaction.qris_proof_attachment_id:
                raise ValidationError(_('A pending or completed QRIS transaction with a payment proof is required.'))
            orders = transaction.sale_order_ids
            if (
                len(orders) != 1
                or transaction.currency_id.compare_amounts(transaction.qris_payment_amount, transaction.amount) != 0
                or transaction.currency_id.compare_amounts(transaction.amount, orders.amount_total) != 0
            ):
                raise ValidationError(_('The QRIS amount does not match the sales order total.'))
            if transaction.state == 'pending':
                transaction._set_done(state_message=_('QRIS payment verified by Finance.'))
                orders.filtered(lambda order: order.state in ('draft', 'sent')).with_context(
                    send_email=False
                ).action_confirm()
                transaction._post_process()
        return True

    def action_diligence_reject_qris_payment(self):
        self.ensure_one()
        if not (
            self.env.user.has_group('account.group_account_invoice')
            or self.env.user.has_group('account.group_account_manager')
            or self.env.user._is_admin()
        ):
            raise AccessError(_('Only Finance users can reject a QRIS payment.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reject QRIS Payment'),
            'res_model': 'payment.qris.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_transaction_id': self.id},
        }

    def _enroll_paid_courses(self):
        """Grant course access after a successful payment post-processing.

        website_sale_slides already performs this for channels configured with
        ``enroll == 'payment'`` when the linked sale order is confirmed. This
        idempotent fallback also covers existing course records that were
        created before that setting was configured.
        """
        for transaction in self.filtered(lambda tx: tx.state == 'done'):
            orders = transaction.sale_order_ids if 'sale_order_ids' in transaction._fields else self.env['sale.order']
            for order in orders.filtered(lambda so: so.state in ('sale', 'done')):
                products = order.order_line.filtered(
                    lambda line: line.product_id.service_tracking == 'course'
                ).mapped('product_id')
                channels = self.env['slide.channel'].search([
                    ('product_id', 'in', products.ids),
                ])
                channels.sudo()._action_add_members(order.partner_id)

    def _check_amount_and_confirm_order(self):
        """Confirm provider-backed payments without requiring a PDF email.

        The standard payment flow requests an order-confirmation email. In a
        local Windows environment without wkhtmltopdf, generating that email
        fails and prevents an otherwise valid payment from confirming its
        sales order. Static QRIS is excluded because receipt verification is
        required before confirmation.
        """
        # Static QRIS remains pending until Finance verifies the uploaded
        # receipt. Provider-backed QRIS callbacks use Odoo's normal flow.
        return super(
            PaymentTransaction,
            self.filtered(lambda tx: tx.provider_id.custom_mode != 'qris_static'),
        )._check_amount_and_confirm_order()

    def _create_payment(self, **extra_create_values):
        """Skip accounting-entry creation for static QRIS in this LMS setup.

        Static QRIS is confirmed from an uploaded proof. The development
        database has no accounting journal configured, so the generic payment
        post-processing would otherwise fail after the order confirmation.
        A production deployment that needs accounting reconciliation should
        configure a QRIS bank journal and remove this exception.
        """
        self.ensure_one()
        if self.provider_id.custom_mode == 'qris_static':
            return self.env['account.payment']
        return super()._create_payment(**extra_create_values)

    def _post_process(self):
        result = super()._post_process()
        self._enroll_paid_courses()
        return result
