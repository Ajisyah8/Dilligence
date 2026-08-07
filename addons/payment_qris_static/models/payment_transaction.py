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
        self._set_done(state_message=_('QRIS payment proof submitted by customer.'))

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
        """Confirm QRIS orders without requiring a PDF email attachment.

        The standard payment flow requests an order-confirmation email. In a
        local Windows environment without wkhtmltopdf, generating that email
        fails and prevents an otherwise valid QRIS payment from confirming its
        sales order. QRIS confirmation remains automatic; only that optional
        email delivery is skipped.
        """
        qris_transactions = self.filtered(
            lambda tx: tx.provider_id.custom_mode == 'qris_static'
        )
        other_transactions = self - qris_transactions
        confirmed_orders = self.env['sale.order']

        if other_transactions:
            confirmed_orders |= super(
                PaymentTransaction, other_transactions
            )._check_amount_and_confirm_order()

        for transaction in qris_transactions:
            if len(transaction.sale_order_ids) != 1:
                continue
            quotation = transaction.sale_order_ids.filtered(
                lambda order: order.state in ('draft', 'sent')
            )
            if quotation and quotation._is_confirmation_amount_reached():
                quotation.with_context(send_email=False).action_confirm()
                confirmed_orders |= quotation

        return confirmed_orders

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
