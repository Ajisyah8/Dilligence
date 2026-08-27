from odoo import _, models
from odoo.exceptions import AccessError, UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_diligence_send_invoice(self):
        if not self.env.user.has_group('diligence_learning.group_diligence_invoice_officer'):
            raise AccessError(_('Only Invoice Officers can use this action.'))
        invoices = self.filtered(lambda move: move.move_type in ('out_invoice', 'out_refund'))
        if any(move.state != 'posted' for move in invoices):
            raise UserError(_('Only posted customer invoices can be sent.'))
        template = self.env.ref('account.email_template_edi_invoice', raise_if_not_found=False)
        if not template:
            raise UserError(_('The standard invoice email template is not available.'))
        for invoice in invoices:
            template.sudo().send_mail(invoice.id, force_send=False, raise_exception=True)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Invoice queued'),
                'message': _('The invoice email has been added to the outgoing mail queue.'),
                'type': 'success',
                'sticky': False,
            },
        }
