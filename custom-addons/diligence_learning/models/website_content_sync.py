from urllib.parse import urlsplit

from odoo import models
from odoo.addons.diligence_learning.models.website_sync import _sync_view_translations


_DILIGENCE_WEBSITE_HOSTS = {
    'diligenceenglish.com': 'diligencekursusbahasa.com',
    'diligencekursusbahasa.com': 'diligenceenglish.com',
}


class DiligenceWebsiteViewSync(models.Model):
    _inherit = 'ir.ui.view'

    def write(self, vals):
        result = super().write(vals)
        if (
            'arch_db' not in vals
            or self.env.context.get('_diligence_syncing_website_view')
        ):
            return result

        website_model = self.env['website'].sudo()
        websites_by_host = {}
        for website in website_model.search([]):
            domain = website.domain or ''
            host = urlsplit(domain if '://' in domain else '//' + domain).hostname
            if host:
                websites_by_host[host.lower().removeprefix('www.')] = website

        website_pairs = {}
        for source_host, target_host in _DILIGENCE_WEBSITE_HOSTS.items():
            source = websites_by_host.get(source_host)
            target = websites_by_host.get(target_host)
            if source and target:
                website_pairs[source.id] = target.id
                website_pairs[target.id] = source.id
        if not website_pairs:
            return result

        pages = self.env['website.page'].sudo().with_context(
            active_test=False,
        ).search([
            ('view_id', 'in', self.ids),
            ('website_id', 'in', list(website_pairs)),
        ])
        for page in pages:
            # Keep homepage languages independent; this legacy mirror would
            # otherwise overwrite translated homepage content on every save.
            if page.url == '/':
                continue
            target_website_id = website_pairs[page.website_id.id]
            peer_pages = self.env['website.page'].sudo().with_context(
                active_test=False,
            ).search([
                ('url', '=', page.url),
                ('website_id', '=', target_website_id),
            ])
            for peer_page in peer_pages:
                target_view = peer_page.view_id
                if not target_view or target_view in self:
                    continue
                _sync_view_translations(page.view_id.sudo(), target_view.sudo())
        return result
