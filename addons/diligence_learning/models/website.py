from odoo import models
from odoo.http import request


class DiligenceWebsite(models.Model):
    _inherit = 'website'

    def _prepare_checkout_page_values(self, order_sudo, **kwargs):
        values = super()._prepare_checkout_page_values(order_sudo, **kwargs)
        values['address_url'] = '/paket-belajar/address'
        return values

    def _get_checkout_step_values(self):
        package_path = request.httprequest.path.startswith('/paket-belajar')
        if not package_path:
            values = super()._get_checkout_step_values()
        else:
            # The standard checkout-step records retain Odoo's canonical
            # /shop paths. Resolve the current package path against those
            # records, then expose the package-friendly URLs to the browser.
            canonical_path = request.httprequest.path.replace('/paket-belajar', '/shop', 1)
            rewrite = lambda path: self.env['ir.http'].url_rewrite(path)[0]
            href = rewrite(canonical_path)
            allowed = self._get_allowed_steps_domain()
            current_step = request.env['website.checkout.step'].sudo()
            for step in current_step.search(allowed):
                if rewrite(step.step_href) == href:
                    current_step = step
                    break
            next_step = current_step._get_next_checkout_step(allowed)
            previous_step = current_step._get_previous_checkout_step(allowed)
            values = {
                'current_website_checkout_step_href': canonical_path,
                'previous_website_checkout_step': previous_step,
                'next_website_checkout_step': next_step,
                'next_website_checkout_step_href': next_step.step_href,
            }
        for key in ('current_website_checkout_step_href', 'next_website_checkout_step_href'):
            if values.get(key):
                values[key] = values[key].replace('/shop/', '/paket-belajar/')
        return values
