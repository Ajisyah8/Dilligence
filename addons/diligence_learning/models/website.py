from odoo import models


class DiligenceWebsite(models.Model):
    _inherit = 'website'

    def new_page(self, name=False, *args, **kwargs):
        """Reuse an existing CMS page instead of silently creating ``-1``.

        Website Builder's Create Page action can be triggered while a page
        with the same slug already exists. Native Odoo then creates a suffix
        URL. Returning the existing page keeps menu/page editing idempotent;
        once the original page is deleted, the normal creation path remains
        available.
        """
        if name:
            slug = '/' + self.env['ir.http']._slugify(name, max_length=1024, path=True)
            website = self.env['website'].get_current_website()
            existing = self.env['website.page'].sudo().search([
                ('url', '=', slug),
                ('website_id', 'in', [False, website.id]),
            ], order='id', limit=1)
            if existing:
                duplicates = self.env['website.page'].sudo().with_context(
                    active_test=False
                ).search([
                    ('website_id', '=', website.id),
                    ('url', '=like', slug + '-%'),
                    ('track', '=', True),
                ]).filtered(lambda page: (
                    not page.menu_ids
                    and not page.is_homepage
                    and not page.view_id.arch_fs
                    and page.url.rsplit('-', 1)[-1].isdigit()
                ))
                duplicates.unlink()
                return {
                    'url': existing.url,
                    'page_id': existing.id,
                    'view_id': existing.view_id.id,
                }
        return super().new_page(name=name, *args, **kwargs)
