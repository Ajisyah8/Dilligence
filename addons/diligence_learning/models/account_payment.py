from odoo import _, models
from odoo.exceptions import UserError


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    def action_post(self):
        """Require an explicit outstanding account on manual bank payments.

        Odoo 19 already provides ``payment_account_id`` on the payment method
        line.  This guard prevents a payment from silently entering
        ``in_process`` without a journal entry when that field is empty.
        """
        for payment in self:
            method_line = payment.payment_method_line_id
            if (
                method_line
                and method_line.code == 'manual'
                and payment.journal_id.type in ('bank', 'cash')
                and not method_line.payment_account_id
            ):
                raise UserError(_(
                    "Configure an outstanding account on the %(method)s payment method "
                    "in the %(journal)s journal before posting this payment.",
                    method=method_line.name,
                    journal=payment.journal_id.display_name,
                ))
        return super().action_post()
