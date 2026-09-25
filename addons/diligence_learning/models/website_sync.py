"""Two-way synchronisation for the two Diligence websites.

The websites share one Odoo database, so business records are already shared.
This file only synchronises presentation records that are website-specific.
SEO fields are intentionally excluded: each domain keeps its own metadata.
"""

from odoo import api, models


SYNC_CONTEXT = 'diligence_website_syncing'
WEBSITE_IDS = (1, 2)

# Native SEO values must never be copied between the two websites.
SEO_FIELDS = {
    'website_meta_title',
    'website_meta_description',
    'website_meta_keywords',
    'website_meta_og_img',
    'website_indexed',
    'canonical_url',
    'seo_name',
    'is_seo_optimized',
}


def _other_website(record):
    website = getattr(record, 'website_id', False)
    if not website or website.id not in WEBSITE_IDS:
        return record.env['website'].browse()
    return record.env['website'].browse(3 - website.id)


def _safe_values(record, vals, excluded=()):
    """Keep only fields that exist on the target and are not identity/SEO."""
    excluded = set(excluded) | SEO_FIELDS
    return {
        field: value for field, value in vals.items()
        if field in record._fields and field not in excluded
    }


class DiligenceWebsiteSync(models.AbstractModel):
    _name = 'diligence.website.sync'
    _description = 'Diligence Website Synchronisation Helpers'

    @api.model
    def _enabled(self):
        return not self.env.context.get(SYNC_CONTEXT)

    @api.model
    def _pair_page(self, page):
        if not page.website_id or page.website_id.id not in WEBSITE_IDS:
            return page.browse()
        return page.search([
            ('website_id', '=', 3 - page.website_id.id),
            ('url', '=', page.url),
        ], order='id', limit=1)

    @api.model
    def _pair_menu(self, menu):
        if not menu.website_id or menu.website_id.id not in WEBSITE_IDS:
            return menu.browse()
        candidates = menu.search([
            ('website_id', '=', 3 - menu.website_id.id),
            ('name', '=', menu.name),
            ('url', '=', menu.url),
        ], order='id')
        if len(candidates) <= 1:
            return candidates[:1]
        parent_name = menu.parent_id.name
        return candidates.filtered(
            lambda candidate: candidate.parent_id.name == parent_name
        )[:1] or candidates[:1]

    @api.model
    def _pair_view(self, view):
        if not view.website_id or view.website_id.id not in WEBSITE_IDS:
            return view.browse()
        domain = [
            ('website_id', '=', 3 - view.website_id.id),
            ('id', '!=', view.id),
        ]
        if view.key:
            paired = view.search(domain + [('key', '=', view.key)], limit=1)
            if paired:
                return paired
        return view.search(domain + [('name', '=', view.name)], order='id', limit=1)

    @api.model
    def sync_page(self, page, vals):
        if not self._enabled() or not page.website_id:
            return
        pair = self._pair_page(page)
        if not pair:
            return
        values = _safe_values(
            pair,
            vals,
            excluded={'website_id', 'view_id', 'url', 'track'},
        )
        if values:
            pair.with_context(**{SYNC_CONTEXT: True}).write(values)
        # Website Builder usually edits the page's view. Keep the paired view
        # in lockstep while preserving the paired view's SEO columns.
        if 'view_id' in vals and page.view_id and pair.view_id:
            pair.view_id.with_context(**{SYNC_CONTEXT: True}).write({
                'arch_db': page.view_id.arch_db,
            })

    @api.model
    def sync_menu(self, menu, vals):
        if not self._enabled() or not menu.website_id:
            return
        pair = self._pair_menu(menu)
        if not pair:
            return
        values = _safe_values(
            pair,
            vals,
            excluded={'website_id', 'parent_id', 'page_id', 'url'},
        )
        if 'parent_id' in vals and menu.parent_id:
            parent = self._pair_menu(menu.parent_id)
            if parent:
                values['parent_id'] = parent.id
        if 'page_id' in vals and menu.page_id:
            page = self._pair_page(menu.page_id)
            if page:
                values['page_id'] = page.id
        if values:
            pair.with_context(**{SYNC_CONTEXT: True}).write(values)

    @api.model
    def sync_view(self, view, vals):
        if not self._enabled():
            return
        if any(field in SEO_FIELDS for field in vals):
            vals = {field: value for field, value in vals.items() if field not in SEO_FIELDS}
        pairs = self._pair_view(view) if view.website_id else view.browse()
        # Homepage and other CMS base views can be global (website_id=False).
        # Resolve those through the page relation so a change made in either
        # website still reaches its website-specific counterpart.
        if not pairs:
            for page in self.env['website.page'].search([('view_id', '=', view.id)]):
                if page.website_id and page.website_id.id in WEBSITE_IDS:
                    paired_page = self._pair_page(page)
                    if paired_page and paired_page.view_id:
                        pairs |= paired_page.view_id
        if not pairs:
            return
        for pair in pairs:
            values = _safe_values(
                pair,
                vals,
                excluded={'website_id', 'key', 'inherit_id', 'xml_id'},
            )
            if values:
                pair.with_context(**{SYNC_CONTEXT: True}).write(values)


class DiligenceWebsitePageSync(models.Model):
    _inherit = 'website.page'

    def write(self, vals):
        result = super().write(vals)
        if not self.env.context.get(SYNC_CONTEXT):
            sync = self.env['diligence.website.sync']
            for page in self:
                sync.sync_page(page, vals)
        return result


class DiligenceWebsiteMenuSync(models.Model):
    _inherit = 'website.menu'

    def write(self, vals):
        result = super().write(vals)
        if not self.env.context.get(SYNC_CONTEXT):
            sync = self.env['diligence.website.sync']
            for menu in self:
                sync.sync_menu(menu, vals)
        return result


class DiligenceIrUiViewSync(models.Model):
    _inherit = 'ir.ui.view'

    def write(self, vals):
        result = super().write(vals)
        if not self.env.context.get(SYNC_CONTEXT):
            sync = self.env['diligence.website.sync']
            for view in self:
                sync.sync_view(view, vals)
        return result


class DiligenceWebsiteSettingsSync(models.Model):
    _inherit = 'website'

    def write(self, vals):
        result = super().write(vals)
        if self.env.context.get(SYNC_CONTEXT):
            return result
        values = _safe_values(
            self,
            vals,
            excluded={
                'domain', 'name', 'company_id', 'sequence', 'theme_id',
                'default_lang_id', 'language_ids', 'website_id',
            },
        )
        if not values:
            return result
        for website in self.filtered(lambda item: item.id in WEBSITE_IDS):
            other = _other_website(website)
            if other:
                other.with_context(**{SYNC_CONTEXT: True}).write(values)
        return result
