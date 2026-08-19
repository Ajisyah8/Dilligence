from odoo import models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def get_product_multiline_description_sale(self):
        self.ensure_one()
        template = self.product_tmpl_id
        if template.diligence_package_type:
            return self.display_name + '\n' + (template.diligence_benefit_text or '')
        return super().get_product_multiline_description_sale()
