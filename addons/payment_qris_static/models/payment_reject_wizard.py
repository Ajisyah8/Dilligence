from odoo import _, fields, models
from odoo.exceptions import AccessError, ValidationError


class PaymentQrisRejectWizard(models.TransientModel):
    _name = 'payment.qris.reject.wizard'
    _description = 'Reject QRIS Payment Wizard'

    transaction_id = fields.Many2one('payment.transaction', required=True, readonly=True)
    reason = fields.Text(string='Rejection Reason', required=True)

    def action_reject(self):
        self.ensure_one()
        if not (
            self.env.user.has_group('account.group_account_invoice')
            or self.env.user.has_group('account.group_account_manager')
            or self.env.user._is_admin()
        ):
            raise AccessError(_('Only Finance users can reject a QRIS payment.'))
        transaction = self.transaction_id
        if transaction.state != 'pending':
            raise ValidationError(_('Only pending QRIS payments can be rejected.'))
        transaction.write({'qris_rejection_reason': self.reason})
        transaction._set_canceled(state_message=_('QRIS payment rejected: %s') % self.reason)
        for order in transaction.sale_order_ids:
            order.message_post(body=_('QRIS payment rejected by Finance: %s') % self.reason)
        return {'type': 'ir.actions.act_window_close'}
