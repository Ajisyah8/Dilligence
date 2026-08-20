from odoo import _, models

from odoo.addons.payment.logging import get_payment_logger


_logger = get_payment_logger(__name__)


class PaymentTransaction(models.Model):
    """Payment flow used by the two currently enabled manual payment methods.

    The custom payment provider is also used by COD, which must not be marked as
    paid automatically.  Keep the decision here, in the Diligence module, so
    the generic ``payment_custom`` provider remains reusable.
    """

    _inherit = 'payment.transaction'

    def _is_diligence_auto_confirm_method(self):
        self.ensure_one()
        if self.provider_code != 'custom':
            return False
        provider_name = (self.provider_id.name or '').strip().lower()
        return 'qris' in provider_name or 'transfer' in provider_name or 'bank' in provider_name

    def _apply_updates(self, payment_data):
        auto_confirmed = self.filtered(lambda tx: tx._is_diligence_auto_confirm_method())
        remaining = self - auto_confirmed

        # Preserve the standard custom-provider behavior for COD and any future
        # custom method that has not explicitly been approved for auto-confirm.
        if remaining:
            super(PaymentTransaction, remaining)._apply_updates(payment_data)

        if auto_confirmed:
            _logger.info(
                "Auto-confirming Diligence manual payment transaction(s) %s via %s.",
                ', '.join(auto_confirmed.mapped('reference')),
                ', '.join(auto_confirmed.mapped('provider_id.name')),
            )
            auto_confirmed._set_done(
                state_message=_(
                    'Automatically confirmed for the configured Diligence manual payment method.'
                )
            )
