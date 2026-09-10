from odoo import Command, _, fields, models

import base64
from odoo.exceptions import AccessError, ValidationError

class PaymentTransaction(models.Model):
    """Payment flow used by the two currently enabled manual payment methods.

    The custom payment provider is also used by COD, which must not be marked as
    paid automatically.  Keep the decision here, in the Diligence module, so
    the generic ``payment_custom`` provider remains reusable.
    """

    _inherit = 'payment.transaction'

    def _set_done(self, *, state_message=None, extra_allowed_states=()):
        manual_without_proof = self.filtered(
            lambda tx: tx.provider_code == "custom"
            and tx.provider_id.custom_mode == "wire_transfer"
            and not tx.qris_proof_attachment_id
        )
        if manual_without_proof:
            raise ValidationError(
                _("A bank-transfer payment proof is required before Finance can verify it.")
            )
        # payment_qris_static overrides _set_done without the optional
        # extra_allowed_states keyword. Keep this override compatible with
        # both the QRIS and the native Odoo implementations.
        return super()._set_done(state_message=state_message)


    def _save_wire_transfer_proof(self, proof, paid_amount=None):
        self.ensure_one()
        if self.state not in ("draft", "pending"):
            raise ValidationError(_("This payment is no longer awaiting a bank-transfer proof."))
        if self.qris_proof_attachment_id:
            raise ValidationError(_("A payment proof has already been submitted."))
        if not proof or not hasattr(proof, "read"):
            raise ValidationError(_("Please upload your bank-transfer payment proof."))

        content = proof.read()
        if not content:
            raise ValidationError(_("The uploaded payment proof is empty."))
        if len(content) > 8 * 1024 * 1024:
            raise ValidationError(_("The payment proof must be smaller than 8 MB."))
        allowed_mimetypes = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
        if proof.mimetype not in allowed_mimetypes:
            raise ValidationError(_("Please upload a JPG, PNG, WEBP, or PDF payment proof."))
        try:
            paid_amount = float(paid_amount)
        except (TypeError, ValueError) as error:
            raise ValidationError(_("Enter a valid payment amount.")) from error
        if self.currency_id.compare_amounts(paid_amount, self.amount) != 0:
            raise ValidationError(_("The payment amount does not match the order total."))

        attachment = self.env["ir.attachment"].sudo().create({
            "name": proof.filename or f"{self.reference}-bank-transfer-proof",
            "type": "binary",
            "datas": base64.b64encode(content),
            "mimetype": proof.mimetype or "application/octet-stream",
            "res_model": self._name,
            "res_id": self.id,
        })
        self.write({
            "qris_proof_attachment_id": attachment.id,
            "qris_payment_amount": paid_amount,
            "qris_proof_uploaded_at": fields.Datetime.now(),
            "qris_proof_uploaded_by": self.env.uid if not self.env.user._is_public() else False,
            "state_message": _("Bank-transfer payment proof uploaded. Waiting for Finance verification."),
        })
        if self.state == "draft":
            self._set_pending(state_message=_("Bank-transfer payment proof uploaded."))
        for order in self.sale_order_ids:
            order.message_post(body=_("Bank-transfer payment proof uploaded and is waiting for Finance verification."))


    def _save_qris_proof(self, proof, paid_amount=None):
        wire_transfers = self.filtered(
            lambda tx: tx.provider_code == "custom"
            and tx.provider_id.custom_mode == "wire_transfer"
        )
        if wire_transfers:
            if len(wire_transfers) != len(self):
                raise ValidationError(_("Upload one payment proof type at a time."))
            return self._save_wire_transfer_proof(proof, paid_amount)

        """Store the receipt first, then send the pending-order email once."""
        result = super()._save_qris_proof(proof, paid_amount)
        for transaction in self.filtered(
            lambda tx: tx.provider_id.custom_mode == 'qris_static'
            and tx.qris_proof_attachment_id
        ):
            transaction.sale_order_ids.with_context(
                diligence_allow_pending_payment_email=True,
            )._send_payment_succeeded_for_order_mail()
        return result

    def _diligence_has_exact_package_payment(self, order):
        """Return whether a package order is paid for by the exact checkout total.

        Odoo allows a sale order with ``require_payment`` disabled to be
        confirmed by any completed transaction. Package access is a paid
        entitlement in Diligence, so an under/over-payment must not confirm the
        order, create an invoice, or unlock a course.
        """
        package_order = order.order_line.filtered(
            lambda line: line.product_template_id.diligence_package_type_id
            or line.product_template_id.diligence_package_type
        )
        if not package_order:
            return True
        paid_amount = sum(
            transaction.amount
            for transaction in order.transaction_ids
            if transaction.state in ('authorized', 'done')
        )
        # Finance verifies a bank transfer (and static QRIS proof) while the
        # current transaction is still pending. Include that one transaction
        # in the amount check, but do not count unrelated pending attempts.
        if self in order.transaction_ids and self.state == 'pending':
            paid_amount += self.amount
        return order.currency_id.compare_amounts(paid_amount, order.amount_total) == 0

    def _diligence_payment_amount_is_valid(self):
        self.ensure_one()
        return all(
            self._diligence_has_exact_package_payment(order)
            for order in self.sale_order_ids
        )

    def _check_amount_and_confirm_order(self):
        """Confirm only exactly paid Diligence package orders."""
        eligible = self.filtered(
            lambda transaction: (
                len(transaction.sale_order_ids) != 1
                or self._diligence_has_exact_package_payment(transaction.sale_order_ids[:1])
            )
        )
        return super(PaymentTransaction, eligible)._check_amount_and_confirm_order()

    def _post_process(self):
        """Keep the payment transaction linked to invoices created by Sale.

        Sale creates the invoice from the confirmed order during the standard
        payment post-processing. The explicit link below is an idempotent
        fallback for installations where another accounting extension creates
        the invoice relation from the sale order side only.
        """
        result = super()._post_process()
        for transaction in self.filtered(lambda tx: tx.state == 'done'):
            invoices = transaction.sale_order_ids.mapped('invoice_ids')
            if invoices and transaction.invoice_ids != invoices:
                transaction.invoice_ids = [Command.set(invoices.ids)]
        return result

    def _apply_updates(self, payment_data):
        # Custom providers must remain pending until a valid gateway callback
        # (QRIS) or an authorized Finance verification (bank transfer) moves
        # them to done. This also makes repeated callbacks idempotent.
        return super()._apply_updates(payment_data)

    def action_diligence_verify_payment(self):
        """Verify a bank transfer and run the normal payment post-processing."""
        if not self.env.user.has_group('account.group_account_invoice'):
            raise AccessError(_('Only Finance users can verify a payment.'))

        transfers = self.filtered(
            lambda tx: tx.provider_code == 'custom'
            and tx.provider_id.custom_mode == 'wire_transfer'
            and tx.state == 'pending'
        )
        without_proof = transfers.filtered(lambda tx: not tx.qris_proof_attachment_id)
        if without_proof:
            raise ValidationError(_("Upload the bank-transfer payment proof before verification."))
        if not transfers:
            raise ValidationError(_('Only pending bank-transfer payments can be verified.'))
        invalid = transfers.filtered(lambda tx: not tx._diligence_payment_amount_is_valid())
        if invalid:
            raise ValidationError(_(
                'The payment amount does not match the order total. Verify the amount before confirming.'
            ))

        transfers._set_done(state_message=_('Bank transfer verified by Finance.'))
        transfers._post_process()
        return True
