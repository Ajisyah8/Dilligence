from odoo import fields, models


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    custom_mode = fields.Selection(
        selection_add=[('qris_static', 'Static QRIS')],
        ondelete={'qris_static': 'set null'},
    )
    qris_image = fields.Image(
        string='QRIS Image',
        max_width=1200,
        max_height=1200,
        help='Static QRIS image shown to customers during checkout.',
    )
    qris_instructions = fields.Html(
        string='QRIS Instructions',
        translate=True,
        default=(
            '<p>Scan the QRIS above, pay the exact order amount, then upload your payment proof.</p>'
            '<p><strong>Payment is confirmed automatically after the proof is submitted.</strong></p>'
        ),
    )
