from odoo import fields, models


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    bank_account_id = fields.Many2one(
        'res.partner.bank',
        string='Bank Account',
        domain="[('journal_id', '!=', False)]",
        check_company=True,
        help=(
            'Bank account used to display the receiving account for '
            'wire-transfer payments.'
        ),
    )
