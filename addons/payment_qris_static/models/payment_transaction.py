import base64

from odoo import _, fields, models
from odoo.exceptions import ValidationError


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    qris_proof_attachment_id = fields.Many2one(
        'ir.attachment',
        string='QRIS Payment Proof',
        readonly=True,
        copy=False,
        help='Payment proof uploaded by the customer for this QRIS transaction.',
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
        # uploaded on the payment status page, after which _save_qris_proof marks it done.
        return super()._apply_updates(payment_data)

    def _save_qris_proof(self, proof):
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

        attachment = self.env['ir.attachment'].sudo().create({
            'name': proof.filename or f'{self.reference}-qris-proof',
            'type': 'binary',
            'datas': base64.b64encode(content),
            'mimetype': proof.mimetype or 'application/octet-stream',
            'res_model': self._name,
            'res_id': self.id,
        })
        self.qris_proof_attachment_id = attachment.id
        # Static QRIS is intentionally auto-confirmed by the agreed business
        # flow: the receipt and exact order amount are validated at upload
        # time, then the normal Odoo order/invoice/access flow is executed.
        # Repeated uploads are rejected above, making this operation idempotent.
        self._set_done(state_message=_('QRIS payment proof accepted.'))
        orders = self.sale_order_ids.filtered(lambda order: order.state in ('draft', 'sent'))
        orders.with_context(send_email=False).action_confirm()
        self._post_process()

    def action_diligence_verify_qris(self):
        """Verify a static QRIS receipt and run normal post-processing."""
        if not self.env.user.has_group('account.group_account_invoice') and not self.env.user._is_admin():
            raise ValidationError(_('Only Finance users can verify a QRIS payment.'))
        for transaction in self:
            if transaction.provider_code != 'custom' or transaction.provider_id.custom_mode != 'qris_static':
                raise ValidationError(_('This transaction is not a static QRIS transaction.'))
            if transaction.state not in ('pending', 'done') or not transaction.qris_proof_attachment_id:
                raise ValidationError(_('A pending or completed QRIS transaction with a payment proof is required.'))
            orders = transaction.sale_order_ids
            if len(orders) != 1 or abs(transaction.amount - orders.amount_total) > 0.01:
                raise ValidationError(_('The QRIS amount does not match the sales order total.'))
            if transaction.state == 'pending':
                # Compatibility action for receipts submitted before the
                # automatic approval change.
                transaction._set_done(state_message=_('QRIS payment accepted.'))
                orders.filtered(lambda order: order.state in ('draft', 'sent')).with_context(
                    send_email=False
                ).action_confirm()
                transaction._post_process()
        return True

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
