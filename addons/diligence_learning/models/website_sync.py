"""Two-way synchronisation for the two Diligence websites.

The websites share one Odoo database, so business records are already shared.
This file only synchronises presentation records that are website-specific.
SEO fields are intentionally excluded: each domain keeps its own metadata.
"""

import logging

from lxml import etree

from odoo import api, models
from odoo.tools.translate import xml_translate


_logger = logging.getLogger(__name__)


SYNC_CONTEXT = 'diligence_website_syncing'
WEBSITE_IDS = (1, 2)

# Global layout components are not website.page records and Odoo can assign
# different keys to their website-specific copies.  Keep the mapping by XML
# key rather than database ID so it remains portable between databases.
GLOBAL_VIEW_KEY_PAIRS = {
    'website.template_footer_minimalist':
        'diligence_learning.website2_sync_footer',
    'website.template_header_navlink_no_background':
        'diligence_learning.website2_sync_header_navlink',
    'website.header_hoverable_dropdown':
        'diligence_learning.website2_sync_header_hoverable',
}

HEADER_FULL_KEYS = {
    'website.template_header_boxed',
    'website.template_header_default',
}

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


def _run_website_sync_without_blocking_save(record, description, callback):
    """Keep optional cross-site mirroring from rolling back the edited record.

    Website Builder writes the source view first. A malformed/legacy paired
    view must not turn that successful source write into a validation error;
    isolate the mirror in a savepoint and log failures for later repair.
    """
    try:
        with record.env.cr.savepoint():
            callback()
    except Exception:
        _logger.exception(
            'Diligence website sync failed for %s; kept the original website save',
            description,
        )


def _xml_translation_terms(arch):
    """Return translatable XML terms in the order Odoo's QWeb translator uses."""
    terms = []
    xml_translate(lambda term: terms.append(term) or term, arch or '')
    return terms


def _sync_view_translations(source_view, target_view, rewrite=None):
    """Copy a view's localized XML without collapsing translations to one locale.

    ``arch_db`` is XML-translated. Writing a full architecture once per
    ``lang`` context is not a safe way to copy it: the target's base language
    may differ from the source website's, and Odoo can treat the whole write
    as a base-value change. Use Odoo's translation update API with the target
    website's base locale as the source term language instead.
    """
    source_view.ensure_one()
    target_view.ensure_one()
    target_lang = (
        target_view.website_id.default_lang_id.code
        if target_view.website_id and target_view.website_id.default_lang_id
        else source_view.website_id.default_lang_id.code
        if source_view.website_id and source_view.website_id.default_lang_id
        else 'en_US'
    )
    target_arch = target_view.with_context(lang=target_lang).arch_db or ''
    target_terms = _xml_translation_terms(target_arch)
    if not target_terms:
        return False

    language_codes = set(
        code for code, _name in source_view.env['res.lang'].get_installed()
    ) | {target_lang}
    translations = {}
    for language_code in language_codes:
        source_arch = source_view.with_context(lang=language_code).arch_db or ''
        if rewrite:
            source_arch = rewrite(source_arch)
        source_terms = _xml_translation_terms(source_arch)
        if len(source_terms) != len(target_terms):
            # The Cambridge schedule has two website-specific sibling views
            # with the same key and parent, but one was edited into a shorter
            # layout. It is a single shared page, so reconcile its target
            # structure from the saved source before applying locale strings.
            if (
                source_view.key == 'diligence_learning.diligence_cambridge_modern_design'
                and target_view.key == source_view.key
                and source_view.inherit_id == target_view.inherit_id
            ):
                source_base_arch = source_view.with_context(lang=target_lang).arch_db or ''
                target_view.with_context({
                    SYNC_CONTEXT: True,
                    'no_cow': True,
                    'lang': target_lang,
                }).write({'arch_db': source_base_arch})
                target_view.invalidate_recordset(['arch_db'])
                return _sync_view_translations(source_view, target_view, rewrite=rewrite)
            _logger.warning(
                'Skip translated view sync %s -> %s for %s: XML term count differs (%s != %s)',
                source_view.id, target_view.id, language_code,
                len(source_terms), len(target_terms),
            )
            return False
        translations[language_code] = dict(zip(target_terms, source_terms))

    target_view.with_context({SYNC_CONTEXT: True, 'no_cow': True}).update_field_translations(
        'arch_db', translations, source_lang=target_lang,
    )
    target_view.invalidate_recordset(['arch_db'])
    return True


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
        other_website = self.env['website'].browse(3 - menu.website_id.id)
        other_root = other_website.menu_id
        if menu == menu.website_id.menu_id:
            return other_root

        candidates = menu.search([
            ('website_id', '=', other_website.id),
            ('name', '=', menu.name),
            ('url', '=', menu.url),
        ], order='id')
        if len(candidates) <= 1:
            exact = candidates[:1]
        else:
            parent_name = menu.parent_id.name
            exact = candidates.filtered(
                lambda candidate: candidate.parent_id.name == parent_name
            )[:1] or candidates[:1]
        if exact:
            return exact

        # If a menu's destination was edited on one website, its URL no
        # longer matches the counterpart. Prefer a unique same-name sibling
        # under the paired parent before falling back to the old URL or page;
        # otherwise e.g. an "Event" menu can be paired with "Contact Us"
        # solely because it used to point at /contactus.
        same_name = menu.search([
            ('website_id', '=', other_website.id),
            ('name', '=', menu.name),
        ], order='id')
        if same_name:
            paired_parent = (
                self._pair_menu(menu.parent_id)
                if menu.parent_id and menu.parent_id != menu.website_id.menu_id
                else other_root
            )
            sibling_match = same_name.filtered(
                lambda candidate: candidate.parent_id == paired_parent
            )
            if sibling_match:
                return sibling_match[:1]
            if len(same_name) == 1:
                return same_name[:1]

        # Website Builder commonly changes the label while keeping the
        # destination page. Pair by the paired page before falling back to
        # URL/position, otherwise a renamed header item becomes one-way.
        if menu.page_id:
            paired_page = self._pair_page(menu.page_id)
            if paired_page:
                page_match = menu.search([
                    ('website_id', '=', other_website.id),
                    ('page_id', '=', paired_page.id),
                ], order='id', limit=1)
                if page_match:
                    return page_match

        url_match = menu.search([
            ('website_id', '=', other_website.id),
            ('url', '=', menu.url),
        ], order='sequence,id')
        if menu.parent_id and menu.parent_id != menu.website_id.menu_id:
            paired_parent = self._pair_menu(menu.parent_id)
            if paired_parent:
                url_match = url_match.filtered(
                    lambda candidate: candidate.parent_id == paired_parent
                )
        if url_match:
            return url_match[:1]

        # Last resort for items such as dropdown labels with URL '#': retain
        # the same sibling position under the paired parent without deleting
        # or recreating any menu records.
        paired_parent = other_root
        if menu.parent_id and menu.parent_id != menu.website_id.menu_id:
            paired_parent = self._pair_menu(menu.parent_id) or other_root
        siblings = menu.search([
            ('website_id', '=', other_website.id),
            ('parent_id', '=', paired_parent.id),
        ], order='sequence,id')
        source_siblings = menu.search([
            ('website_id', '=', menu.website_id.id),
            ('parent_id', '=', menu.parent_id.id if menu.parent_id else False),
        ], order='sequence,id')
        try:
            return siblings[source_siblings.ids.index(menu.id)]
        except (ValueError, IndexError):
            return menu.browse()

    @api.model
    def _pair_view(self, view):
        # Website Builder pages are the authoritative presentation mapping.
        # A homepage may use a global view on one website and a
        # website-specific view on the other, so matching by key/name alone
        # cannot find the reverse pair (for example 4540 <-> 4553).
        pages = self.env['website.page'].search([('view_id', '=', view.id)])
        for page in pages:
            if not page.website_id or page.website_id.id not in WEBSITE_IDS:
                continue
            paired_page = self._pair_page(page)
            if paired_page and paired_page.view_id and paired_page.view_id != view:
                return paired_page.view_id

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
    def _paired_views(self, view):
        """Return every presentation view that represents *view* on the other site.

        Website Builder can create a website-specific copy of a view and may
        write that copy instead of the view referenced by the published page.
        The page relation is the strongest mapping; the normalized key is a
        safe fallback for those generated copies.  SEO fields are still
        filtered by ``_safe_values`` below.
        """
        pairs = self.env['ir.ui.view'].browse()

        for page in self.env['website.page'].search([('view_id', '=', view.id)]):
            if not page.website_id or page.website_id.id not in WEBSITE_IDS:
                continue
            paired_page = self._pair_page(page)
            if paired_page and paired_page.view_id and paired_page.view_id != view:
                pairs |= paired_page.view_id

        if view.website_id and view.website_id.id in WEBSITE_IDS:
            other_id = 3 - view.website_id.id
            domain = [
                ('website_id', '=', other_id),
                ('id', '!=', view.id),
                ('mode', '=', view.mode),
            ]
            keys = [view.key] if view.key else []
            if view.key and view.key.endswith('.website2'):
                keys.append(view.key[:-len('.website2')])
            elif view.key:
                keys.append(view.key + '.website2')
            if keys:
                pairs |= view.search(domain + [('key', 'in', keys)])
            if view.name:
                pairs |= view.search(domain + [('name', '=', view.name)])

            # The live homepage of website 1 can intentionally reference a
            # global primary view (website_id=False), while Website Builder
            # writes a generated website-specific copy.  Include only global
            # views that are actually attached to a page of the other
            # website; otherwise the edit reaches the generated copy but not
            # the page visitors see.
            if keys:
                global_candidates = view.search([
                    ('website_id', '=', False),
                    ('id', '!=', view.id),
                    ('mode', '=', view.mode),
                    ('key', 'in', keys),
                ])
                for candidate in global_candidates:
                    attached_page = self.env['website.page'].search([
                        ('website_id', '=', other_id),
                        ('view_id', '=', candidate.id),
                    ], limit=1)
                    if attached_page:
                        pairs |= candidate

        # Header/footer templates can be global on one website and
        # website-specific on the other.  Also allow the default/boxed
        # header variants to pair, so both websites keep the same header
        # after a Website Builder save in either direction.
        component_keys = {view.key} if view.key else set()
        if view.key in GLOBAL_VIEW_KEY_PAIRS:
            component_keys.add(GLOBAL_VIEW_KEY_PAIRS[view.key])
        else:
            component_keys.update(
                left_key for left_key, right_key in GLOBAL_VIEW_KEY_PAIRS.items()
                if right_key == view.key
            )
        if component_keys:
            other_id = 3 - view.website_id.id if view.website_id else False
            domains = []
            if other_id:
                domains.append(('website_id', '=', other_id))
            else:
                # A global header view is rendered by both Diligence
                # websites. Include the concrete website-specific copy so a
                # save from the default website reaches the other domain.
                domains.extend(
                    ('website_id', '=', website_id)
                    for website_id in WEBSITE_IDS
                )
            domains.append(('website_id', '=', False))
            for website_domain in domains:
                pairs |= view.search([
                    website_domain,
                    ('key', 'in', list(component_keys)),
                    ('mode', '=', view.mode),
                    ('id', '!=', view.id),
                ])

        return pairs - view

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
            pair.with_context({SYNC_CONTEXT: True, 'no_cow': True}).write(values)
        # Website Builder usually edits the page's view. Keep the paired view
        # in lockstep while preserving the paired view's SEO columns.
        # The two homepages intentionally have different default languages.
        # Keep their editable HTML and QWeb translations independent.
        if 'view_id' in vals and page.url != '/' and page.view_id and pair.view_id:
            _sync_view_translations(page.view_id, pair.view_id)

    @api.model
    def sync_created_page(self, page):
        """Create the matching CMS page on the other Diligence website.

        Existing routes (notably Odoo controller routes and the homepage) are
        never duplicated or replaced. Generated Website Builder COW routes
        are also ignored; the public page is synchronized by the builder-save
        hook instead.
        """
        if not self._enabled() or not page.website_id:
            return page.browse()
        if page.website_id.id not in WEBSITE_IDS or not page.url or page.url.startswith('/-'):
            return page.browse()

        existing = self._pair_page(page)
        if existing:
            return existing

        other_website = _other_website(page)
        if not other_website:
            return page.browse()
        peer = page.with_context({
            SYNC_CONTEXT: True,
            'no_cow': True,
            'website_id': other_website.id,
        }).copy({
            'website_id': other_website.id,
            'is_published': page.is_published,
        })
        if page.view_id and peer.view_id:
            _sync_view_translations(page.view_id, peer.view_id)
        return peer

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
            # ``website.menu.name`` is translated. A regular write copies only
            # the active language's value as the target's base value and can
            # erase the other site's Indonesian/Chinese labels.
            excluded={'website_id', 'parent_id', 'page_id', 'name'},
        )
        # Mirror route links only for menus that are not bound to CMS pages.
        # Page URLs are intentionally website-specific to protect SEO routes.
        if 'url' in vals and not menu.page_id and not pair.page_id:
            values['url'] = vals['url']
        if 'parent_id' in vals and menu.parent_id:
            parent = self._pair_menu(menu.parent_id)
            if parent:
                values['parent_id'] = parent.id
        if 'page_id' in vals and menu.page_id:
            page = self._pair_page(menu.page_id)
            if page:
                values['page_id'] = page.id
        if values:
            pair.with_context({SYNC_CONTEXT: True, 'no_cow': True}).write(values)
        if 'name' in vals:
            target_lang = (
                pair.website_id.default_lang_id.code
                if pair.website_id.default_lang_id else 'en_US'
            )
            languages = {
                code for code, _name in menu.env['res.lang'].get_installed()
            } | {target_lang}
            translations = {
                language_code: menu.with_context(lang=language_code).name
                for language_code in languages
            }
            pair.with_context({SYNC_CONTEXT: True, 'no_cow': True}).update_field_translations(
                'name', translations, source_lang=target_lang,
            )

    @api.model
    def sync_created_menu(self, menu):
        """Create a paired menu while preserving each website's menu tree."""
        if not self._enabled() or not menu.website_id:
            return menu.browse()
        if menu.website_id.id not in WEBSITE_IDS or menu == menu.website_id.menu_id:
            return menu.browse()

        other_website = _other_website(menu)
        if not other_website:
            return menu.browse()
        other_parent = (
            other_website.menu_id
            if not menu.parent_id or menu.parent_id == menu.website_id.menu_id
            else self._pair_menu(menu.parent_id)
        )
        if not other_parent:
            other_parent = other_website.menu_id
        other_page = self._pair_page(menu.page_id) if menu.page_id else menu.page_id

        # If a peer route/menu already exists, leave it untouched rather than
        # creating a duplicate or stealing a route from a different feature.
        menu_model = self.env['website.menu']
        if other_page:
            candidates = menu_model.search([
                ('website_id', '=', other_website.id),
                ('page_id', '=', other_page.id),
            ], limit=1)
            if candidates:
                return candidates
        candidates = menu_model.search([
            ('website_id', '=', other_website.id),
            ('parent_id', '=', other_parent.id),
            ('url', '=', menu.url),
        ])
        if len(candidates) == 1:
            return candidates
        if not candidates and menu.url == '#':
            candidates = menu_model.search([
                ('website_id', '=', other_website.id),
                ('parent_id', '=', other_parent.id),
                ('name', '=', menu.name),
            ])
            if len(candidates) == 1:
                return candidates

        return menu.with_context({SYNC_CONTEXT: True, 'no_cow': True}).copy({
            'website_id': other_website.id,
            'parent_id': other_parent.id,
            'page_id': other_page.id if other_page else False,
        })

    @api.model
    def sync_view(self, view, vals):
        if not self._enabled():
            return
        # Homepage copy is localized per domain (English vs Indonesian).
        # Mirroring the full QWeb arch here replaces one site's language with
        # the other site's base-language content during a deploy or edit.
        if self._is_diligence_homepage_view(view):
            return
        # Old Website Builder COW records are retained for recovery only.
        # They share names with the live header templates, so name-based
        # pairing must never reactivate or overwrite them.
        if (view.key or '').startswith('legacy_disabled.'):
            return
        # Website Builder can submit the rendered XML as ``arch`` while
        # direct view edits use ``arch_db``.  Always mirror it through the
        # persisted field used by ir.ui.view on the paired website.
        vals = dict(vals)
        if 'arch' in vals and 'arch_db' not in vals:
            vals['arch_db'] = vals['arch']
        if any(field in SEO_FIELDS for field in vals):
            vals = {field: value for field, value in vals.items() if field not in SEO_FIELDS}
        pairs = self._paired_views(view)
        pairs = pairs.filtered(
            lambda pair: not (pair.key or '').startswith('legacy_disabled.')
        )
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
            sync_arch = 'arch_db' in vals
            view_vals = dict(vals)
            view_vals.pop('arch_db', None)
            values = _safe_values(
                pair,
                view_vals,
                excluded={'website_id', 'key', 'inherit_id', 'xml_id'},
            )
            if values:
                pair.with_context({SYNC_CONTEXT: True, 'no_cow': True}).write(values)
            if sync_arch:
                _sync_view_translations(view, pair)

    @api.model
    def _is_diligence_homepage_view(self, view):
        if not view:
            return False
        pages = self.env['website.page'].search([
            ('view_id', '=', view.id),
            ('url', '=', '/'),
            ('website_id', 'in', WEBSITE_IDS),
        ])
        if pages:
            return True
        homepage_keys = {
            'diligence_learning.homepage_editable',
            'diligence_learning.homepage_editable.website2',
        }
        return bool(view.key in homepage_keys and view.website_id.id in WEBSITE_IDS)


class DiligenceWebsitePageSync(models.Model):
    _inherit = 'website.page'

    @api.model_create_multi
    def create(self, vals_list):
        pages = super().create(vals_list)
        if not self.env.context.get(SYNC_CONTEXT):
            sync = self.env['diligence.website.sync']
            for page in pages:
                sync.sync_created_page(page)
        return pages

    def write(self, vals):
        result = super().write(vals)
        if not self.env.context.get(SYNC_CONTEXT):
            sync = self.env['diligence.website.sync']
            for page in self:
                sync.sync_page(page, vals)
        return result


class DiligenceWebsiteMenuSync(models.Model):
    _inherit = 'website.menu'

    @api.model_create_multi
    def create(self, vals_list):
        menus = super().create(vals_list)
        if not self.env.context.get(SYNC_CONTEXT):
            sync = self.env['diligence.website.sync']
            for menu in menus:
                sync.sync_created_menu(menu)
        return menus

    def write(self, vals):
        result = super().write(vals)
        if not self.env.context.get(SYNC_CONTEXT):
            sync = self.env['diligence.website.sync']
            for menu in self:
                sync.sync_menu(menu, vals)
        return result


class DiligenceIrUiViewSync(models.Model):
    _inherit = 'ir.ui.view'

    @api.model
    def _diligence_fix_contact_translation_targets(self):
        """Attach Contact page translation markers to each live page view."""
        targets = (
            (
                'diligence_learning.diligence_contact_translation_en',
                'https://diligenceenglish.com',
            ),
            (
                'diligence_learning.diligence_contact_translation_id',
                'https://diligencekursusbahasa.com',
            ),
        )
        page_model = self.env['website.page']
        for xmlid, domain in targets:
            page = page_model.search([
                ('url', '=', '/contactus'),
                ('website_id.domain', '=', domain),
            ], limit=1)
            if not page or not page.view_id:
                _logger.warning(
                    'Diligence translation marker: no live Contact page for %s',
                    domain,
                )
                continue
            try:
                marker_view = self.env.ref(xmlid)
            except ValueError:
                _logger.warning('Missing Contact translation view %s', xmlid)
                continue
            if marker_view.inherit_id != page.view_id:
                marker_view.with_context({
                    SYNC_CONTEXT: True,
                    'no_cow': True,
                }).write({
                    'inherit_id': page.view_id.id,
                    'website_id': page.website_id.id,
                    'mode': 'extension',
                })

    def _diligence_normalize_carousels(self, view):
        """Restore Bootstrap carousel navigation attributes after editing.

        Website Builder can leave generated indicator buttons without
        ``data-bs-slide-to``. Bootstrap then receives ``null`` while changing
        the active indicator and raises on ``classList``. Normalise only
        complete carousels whose indicator and item counts match.
        """
        arch = view.arch_db or ''
        if 'carousel' not in arch or 'carousel-item' not in arch:
            return False
        try:
            root = etree.fromstring(arch.encode())
        except etree.XMLSyntaxError:
            return False

        changed = False
        carousels = root.xpath(
            "//*[contains(concat(' ', normalize-space(@class), ' '), "
            "' carousel ')][@id]"
        )
        for carousel in carousels:
            carousel_id = carousel.get('id')
            indicators = carousel.xpath(
                ".//*[contains(concat(' ', normalize-space(@class), ' '), "
                "' carousel-indicators ')]/button"
            )
            items = carousel.xpath(
                ".//*[contains(concat(' ', normalize-space(@class), ' '), "
                "' carousel-inner ')]/*[contains(concat(' ', "
                "normalize-space(@class), ' '), ' carousel-item ')]"
            )
            if not indicators or len(indicators) != len(items):
                continue
            for index, button in enumerate(indicators):
                expected = {
                    'type': 'button',
                    'data-bs-target': f'#{carousel_id}',
                    'data-bs-slide-to': str(index),
                }
                for attribute, value in expected.items():
                    if button.get(attribute) != value:
                        button.set(attribute, value)
                        changed = True
            for button in carousel.xpath(
                ".//button[contains(concat(' ', normalize-space(@class), "
                "' '), ' carousel-control-prev ')]"
            ):
                if button.get('data-bs-slide') != 'prev':
                    button.set('data-bs-slide', 'prev')
                    changed = True
            for button in carousel.xpath(
                ".//button[contains(concat(' ', normalize-space(@class), "
                "' '), ' carousel-control-next ')]"
            ):
                if button.get('data-bs-slide') != 'next':
                    button.set('data-bs-slide', 'next')
                    changed = True

        if changed:
            view.with_context({
                SYNC_CONTEXT: True,
                'no_cow': True,
            }).write({
                'arch_db': etree.tostring(root, encoding='unicode'),
                'arch_updated': True,
            })
        return changed

    def _diligence_is_full_header(self, view):
        """Identify the complete header template, not small header addons."""
        arch = view.arch_db or ''
        return bool(
            view.key in HEADER_FULL_KEYS
            or ('//header//nav' in arch and 'position="replace"' in arch)
        )

    def _diligence_sync_full_header(self, source_view):
        """Keep all active full-header variants on the same markup.

        Odoo Website Builder can save either a global boxed template or a
        website-specific default-template copy. Matching only the XML key
        therefore leaves the other domain on a different header. Full header
        variants are presentation-only and are safe to mirror; SEO fields
        are not part of these views.
        """
        if not self._diligence_is_full_header(source_view):
            return
        arch = source_view.arch_db
        if not arch:
            return
        targets = self.search([
            ('id', '!=', source_view.id),
            ('active', '=', True),
            ('key', 'in', list(HEADER_FULL_KEYS)),
            ('website_id', 'in', [False, *WEBSITE_IDS]),
        ])
        for target in targets:
            if target.arch_db == arch:
                continue
            target.with_context({
                SYNC_CONTEXT: True,
                'no_cow': True,
            }).write({'arch_db': arch, 'arch_updated': True})
            _logger.info(
                'Diligence website sync: full header %s -> %s',
                source_view.id, target.id,
            )

    def _diligence_builder_source_view(self, website, original_key):
        """Return the concrete COW view written by Website Builder."""
        if not original_key:
            return self
        concrete = self.search([
            ('website_id', '=', website.id),
            ('key', '=', original_key),
            ('active', '=', True),
        ], order='write_date desc, id desc', limit=1)
        return concrete or self

    def _diligence_sync_builder_save(self, website, original_view, source_view):
        """Mirror a Website Builder save to the live page of the other site.

        Odoo's ``save`` method may update translated/COW view data without a
        normal ``write`` on the live page view.  Synchronising here makes the
        operation deterministic and keeps both directions working.
        """
        if website.id not in WEBSITE_IDS or not source_view.arch_db:
            return

        other_id = 3 - website.id
        page_model = self.env['website.page']
        source_pages = page_model.search([
            '|',
            ('view_id', '=', original_view.id),
            ('view_id', '=', source_view.id),
        ])
        urls = source_pages.filtered(
            lambda page: page.website_id.id in WEBSITE_IDS
        ).mapped('url')

        # The homepage has generated editor copies with technical URLs such
        # as /-1.  Its public route is always '/', so explicitly target the
        # live homepage instead of the generated page.
        keys = {original_view.key, source_view.key}
        if keys & {
            'diligence_learning.homepage_editable',
            'diligence_learning.homepage_editable.website2',
        }:
            urls = ['/']

        # Update both public page views.  Website 1's editor writes a COW
        # view, while its public homepage can still point to a global view.
        # Without updating the source website's own live view, an English
        # edit appears only on the Kursus Bahasa website.
        homepage_save = bool(keys & {
            'diligence_learning.homepage_editable',
            'diligence_learning.homepage_editable.website2',
        })
        target_website_ids = (website.id,) if homepage_save else (website.id, other_id)
        for target_website_id in target_website_ids:
            for url in set(urls):
                target_page = page_model.search([
                    ('website_id', '=', target_website_id),
                    ('url', '=', url),
                ], order='is_published desc, id', limit=1)
                if target_page and target_page.view_id != source_view:
                    _sync_view_translations(source_view, target_page.view_id)
                    _logger.info(
                        'Diligence website sync: source view %s (website %s) '
                        'to live view %s (website %s, url %s)',
                        source_view.id, website.id, target_page.view_id.id,
                        target_website_id, url,
                    )

        # Keep generated editor copies aligned too, otherwise the next edit
        # could reopen stale content and overwrite the live page again.
        normalized_keys = set(filter(None, keys))
        for key in list(normalized_keys):
            if key.endswith('.website2'):
                normalized_keys.add(key[:-len('.website2')])
            else:
                normalized_keys.add(key + '.website2')
        generated_targets = self.browse() if homepage_save else self.search([
            ('website_id', '=', other_id),
            ('key', 'in', list(normalized_keys)),
            ('id', '!=', source_view.id),
        ])
        for target in generated_targets:
            _sync_view_translations(source_view, target)

        # Header/footer components inherit website.layout directly and have
        # no website.page URL.  Their custom keys differ between both sites,
        # so synchronise their explicitly registered counterpart here.
        component_key = source_view.key or original_view.key
        target_key = GLOBAL_VIEW_KEY_PAIRS.get(component_key)
        if not target_key:
            target_key = next((
                left_key
                for left_key, right_key in GLOBAL_VIEW_KEY_PAIRS.items()
                if right_key == component_key
            ), False)
        if target_key:
            target_component = self.search([
                ('website_id', 'in', [False, other_id]),
                ('key', '=', target_key),
                ('active', '=', True),
            ], order='website_id desc, write_date desc, id desc', limit=1)
            if target_component:
                def rewrite_component_images(arch):
                    return arch.replace(
                        f'/web/image/website/{website.id}/',
                        f'/web/image/website/{other_id}/',
                    )

                _sync_view_translations(
                    source_view, target_component,
                    rewrite=rewrite_component_images,
                )
                _logger.info(
                    'Diligence website sync: global component %s '
                    '(website %s) to %s (website %s)',
                    source_view.id, website.id, target_component.id, other_id,
                )

    def save(self, value, xpath=None):
        self.ensure_one()
        if self.env.context.get(SYNC_CONTEXT):
            return super().save(value, xpath=xpath)

        # RPC calls made by Website Builder can resolve get_current_website()
        # to the default website.  The edited view itself is authoritative.
        website = self.website_id
        if not website or website.id not in WEBSITE_IDS:
            website = self.env['website'].get_current_website()
        original_view = self
        original_key = self.key
        try:
            result = super().save(value, xpath=xpath)
        except Exception:
            # Odoo's RPC validation message hides the parsing traceback from
            # normal logs. Record only payload types/size (never page content)
            # so malformed Website Builder saves can be diagnosed safely.
            _logger.exception(
                'Diligence Website Builder save failed before cross-site sync: '
                'view=%s key=%s website=%s value_type=%s value_length=%s xpath_type=%s',
                original_view.id,
                original_key,
                original_view.website_id.id or False,
                type(value).__name__,
                len(value) if isinstance(value, (str, bytes)) else False,
                type(xpath).__name__,
            )
            raise

        if website and website.id in WEBSITE_IDS:
            def sync_builder_save():
                source_view = self._diligence_builder_source_view(
                    website, original_key,
                )
                self._diligence_normalize_carousels(source_view)
                self._diligence_sync_builder_save(
                    website, original_view, source_view,
                )

            _run_website_sync_without_blocking_save(
                self, f'Website Builder view {original_view.id}', sync_builder_save,
            )
        return result

    def write(self, vals):
        result = super().write(vals)
        if not self.env.context.get(SYNC_CONTEXT):
            sync = self.env['diligence.website.sync']
            for view in self:
                def sync_view(view=view):
                    self._diligence_normalize_carousels(view)
                    sync.sync_view(view, vals)

                _run_website_sync_without_blocking_save(
                    view, f'view {view.id}', sync_view,
                )
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
                other.with_context({SYNC_CONTEXT: True, 'no_cow': True}).write(values)
        return result
