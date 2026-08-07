from odoo import fields, models


class SlideChannelPartner(models.Model):
    _inherit = 'slide.channel.partner'

    diligence_package_id = fields.Many2one('product.template', 'Access Package', copy=False)
    diligence_access_expires_at = fields.Datetime('Access Expires At', copy=False)

    def _diligence_access_is_valid(self):
        self.ensure_one()
        return not self.diligence_access_expires_at or self.diligence_access_expires_at >= fields.Datetime.now()
