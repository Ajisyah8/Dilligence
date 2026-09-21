import re
from collections import Counter

from psycopg2 import IntegrityError

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import html2plaintext


class DiligenceSeoItem(models.Model):
    _name = 'diligence.seo.item'
    _description = 'Diligence SEO Manager Item'
    _order = 'seo_status, name'

    name = fields.Char(required=True)
    website_id = fields.Many2one(
        'website', string='Website', required=True, index=True,
        default=lambda self: self.env['website'].search([], order='sequence, id', limit=1),
        ondelete='restrict',
        help='Website/domain for which this SEO record is managed.',
    )
    domain = fields.Char(
        related='website_id.domain', string='Domain', store=True, readonly=True,
    )
    content_type = fields.Selection([
        ('website.page', 'Website Page'),
        ('product.template', 'Product / Package'),
        ('slide.channel', 'Course'),
        ('blog.blog', 'Blog'),
        ('blog.post', 'Blog Post'),
    ], required=True, index=True)
    res_model = fields.Char(required=True, index=True, readonly=True)
    res_id = fields.Integer(required=True, index=True, readonly=True)
    url = fields.Char(index=True)
    seo_title = fields.Char()
    seo_description = fields.Text()
    seo_keywords = fields.Char()
    canonical_url = fields.Char()
    og_image = fields.Binary(attachment=True)
    og_title = fields.Char(string='Social Title')
    og_description = fields.Text(string='Social Description')
    robots_index = fields.Boolean(string='Robots Index', default=True)
    robots_follow = fields.Boolean(string='Robots Follow', default=True)
    keyword_source = fields.Selection([
        ('manual', 'Manual'),
        ('generated', 'Generated'),
        ('imported', 'Imported'),
    ], string='Keyword Source', default='manual')
    keywords_generated_at = fields.Datetime(string='Keywords Generated At', readonly=True)
    is_indexed = fields.Boolean(default=True)
    is_published = fields.Boolean(default=False)
    seo_score = fields.Integer(compute='_compute_seo_score_status', store=True)
    seo_status = fields.Selection([
        ('complete', 'Complete'),
        ('warning', 'Warning'),
        ('needs_improvement', 'Needs Improvement'),
    ], compute='_compute_seo_score_status', store=True)
    seo_warnings = fields.Text(compute='_compute_seo_warnings')
    duplicate_title = fields.Boolean(compute='_compute_duplicate_flags', search='_search_duplicate_title')
    duplicate_canonical = fields.Boolean(compute='_compute_duplicate_flags', search='_search_duplicate_canonical')
    search_keyword_suggestions = fields.Text(compute='_compute_search_keyword_suggestions')
    last_updated = fields.Datetime(default=fields.Datetime.now, readonly=True)
    last_audited_at = fields.Datetime(string='Last Audited At', readonly=True)

    _target_unique = models.Constraint(
        'UNIQUE(res_model, res_id)',
        'A content record can only have one SEO item.',
    )

    @api.model
    def _allowed_models(self):
        selection = self._fields['content_type'].selection
        if callable(selection):
            selection = selection(self.env)
        return dict(selection)

    def _get_target(self):
        self.ensure_one()
        if self.res_model not in self._allowed_models() or self.res_model not in self.env:
            return self.env[self.res_model].browse()
        return self.env[self.res_model].browse(self.res_id).exists()

    @api.model
    def _website_for_target(self, target):
        website = target.website_id if target and 'website_id' in target._fields else self.env['website'].browse()
        return website or self.env['website'].search([], order='sequence, id', limit=1)

    def _item_website(self, target=None):
        self.ensure_one()
        return self.website_id or self._website_for_target(target or self._get_target())

    def _canonical_for_target(self, target, website=None):
        website = website or self._website_for_target(target)
        path = False
        if target:
            if 'website_url' in target._fields:
                path = target.website_url
            elif self.res_model == 'website.page':
                path = target.url
        if not path:
            return False
        domain = (website.domain or '').rstrip('/')
        return '%s%s' % (domain, path if path.startswith('/') else '/%s' % path) if domain else path

    def _target_is_private(self, target):
        if not target:
            return True
        if self.res_model in ('website.page', 'slide.channel', 'blog.post'):
            return bool(getattr(target, 'visibility', False))
        return False

    def _target_values(self, target):
        values = {}
        for item_field, native_field in (
            ('seo_title', 'website_meta_title'),
            ('seo_description', 'website_meta_description'),
            ('seo_keywords', 'website_meta_keywords'),
            ('og_image', 'website_meta_og_img'),
        ):
            if native_field in target._fields:
                values[item_field] = target[native_field]
        if 'website_url' in target._fields:
            values['url'] = target.website_url
        elif self.res_model == 'website.page':
            values['url'] = target.url
        if 'website_published' in target._fields:
            values['is_published'] = target.website_published
        elif 'active' in target._fields:
            values['is_published'] = target.active
        if 'website_indexed' in target._fields:
            values['is_indexed'] = bool(target.website_indexed and values.get('is_published'))
        values['canonical_url'] = self._canonical_for_target(target, self._item_website(target))
        return values

    def _sync_to_target(self, vals=None):
        for item in self:
            target = item._get_target()
            if not target:
                continue
            source_values = {}
            mapping = {
                'seo_title': 'website_meta_title',
                'seo_description': 'website_meta_description',
                'seo_keywords': 'website_meta_keywords',
                'og_image': 'website_meta_og_img',
            }
            for item_field, native_field in mapping.items():
                if not vals or item_field in vals:
                    if native_field in target._fields:
                        source_values[native_field] = item[item_field]
            if not vals or 'is_indexed' in vals:
                if 'website_indexed' in target._fields:
                    source_values['website_indexed'] = item.is_indexed
            if not vals or 'is_published' in vals:
                if 'website_published' in target._fields and item.is_published != target.website_published:
                    source_values['website_published'] = item.is_published
            if source_values:
                target.sudo().write(source_values)

    def _get_seo_warnings(self):
        self.ensure_one()
        warnings = []
        title_length = len(self.seo_title or '')
        description_length = len(self.seo_description or '')
        if not self.seo_title:
            warnings.append(_('SEO title is empty.'))
        elif title_length < 30:
            warnings.append(_('SEO title is shorter than 30 characters.'))
        elif title_length > 60:
            warnings.append(_('SEO title is longer than 60 characters.'))
        if not self.seo_description:
            warnings.append(_('Meta description is empty.'))
        elif description_length < 120:
            warnings.append(_('Meta description is shorter than 120 characters.'))
        elif description_length > 160:
            warnings.append(_('Meta description is longer than 160 characters.'))
        if not self.url:
            warnings.append(_('URL is empty.'))
        website = self._item_website()
        if not website:
            warnings.append(_('Website/domain is not configured.'))
        elif self.canonical_url and website.domain and not self.canonical_url.startswith(website.domain.rstrip('/') + '/'):
            warnings.append(_('Canonical URL does not match the selected website domain.'))
        target = self._get_target()
        if self.is_indexed and (not self.is_published or self._target_is_private(target)):
            warnings.append(_('Unpublished or private content must not be indexed.'))
        return warnings

    @api.depends('seo_title', 'seo_description', 'url', 'is_indexed', 'is_published', 'res_model', 'res_id')
    def _compute_seo_warnings(self):
        for item in self:
            item.seo_warnings = '\n'.join(item._get_seo_warnings())

    @api.depends('seo_title', 'seo_description', 'url', 'is_indexed', 'is_published', 'res_model', 'res_id')
    def _compute_seo_score_status(self):
        for item in self:
            warnings = item._get_seo_warnings()
            item.seo_score = max(0, 100 - len(warnings) * 15)
            item.seo_status = 'complete' if not warnings else ('needs_improvement' if len(warnings) >= 3 else 'warning')

    def _compute_duplicate_flags(self):
        for item in self:
            item.duplicate_title = bool(item.seo_title and self.search_count([
                ('website_id', '=', item.website_id.id),
                ('seo_title', '=', item.seo_title),
                ('id', '!=', item.id),
            ]))
            item.duplicate_canonical = bool(item.canonical_url and self.search_count([
                ('website_id', '=', item.website_id.id),
                ('canonical_url', '=', item.canonical_url),
                ('id', '!=', item.id),
            ]))

    @api.model
    def _search_duplicate_title(self, operator, value):
        if operator not in ('=', '!='):
            return [('id', '=', 0)]
        items = self.search([])
        ids = items.filtered('duplicate_title').ids
        include = (operator == '=' and bool(value)) or (operator == '!=' and not value)
        return [('id', 'in' if include else 'not in', ids)]

    @api.model
    def _search_duplicate_canonical(self, operator, value):
        if operator not in ('=', '!='):
            return [('id', '=', 0)]
        items = self.search([])
        ids = items.filtered('duplicate_canonical').ids
        include = (operator == '=' and bool(value)) or (operator == '!=' and not value)
        return [('id', 'in' if include else 'not in', ids)]

    @api.constrains('res_model', 'res_id', 'is_indexed', 'url')
    def _check_target(self):
        for item in self:
            if item.content_type != item.res_model:
                raise ValidationError(_('Content Type must match the selected content model.'))
            if item.res_id <= 0 or not item._get_target():
                raise ValidationError(_('The selected content record does not exist.'))
            target = item._get_target()
            target_website = item._website_for_target(target)
            if target_website and target.website_id and item.website_id != target_website:
                raise ValidationError(_('The SEO website must match the content website.'))
            if item.is_indexed and (not item.is_published or item._target_is_private(item._get_target())):
                raise ValidationError(_('Private or unpublished content cannot be marked as indexed.'))
            if item.url and self.search_count([
                ('website_id', '=', item.website_id.id),
                ('url', '=', item.url),
                ('id', '!=', item.id),
            ]):
                raise ValidationError(_('The URL must be unique across SEO Manager items.'))

    @api.model_create_multi
    def create(self, vals_list):
        records = self.browse()
        for vals in vals_list:
            model = vals.get('res_model') or vals.get('content_type')
            content_type = vals.get('content_type') or model
            if model not in self._allowed_models():
                raise ValidationError(_('This content model is not supported by SEO Manager.'))
            target = self.env[model].browse(vals.get('res_id')).exists()
            if not target:
                raise ValidationError(_('The selected content record does not exist.'))
            defaults = self._target_values_for_create(model, target)
            defaults['website_id'] = vals.get('website_id') or self._website_for_target(target).id
            defaults.update(vals)
            defaults.update({'content_type': content_type, 'res_model': model, 'res_id': target.id})
            records |= super(DiligenceSeoItem, self).create(defaults)
        records._sync_to_target()
        return records

    def _target_values_for_create(self, model, target):
        values = {'name': target.display_name}
        for item_field, native_field in (
            ('seo_title', 'website_meta_title'),
            ('seo_description', 'website_meta_description'),
            ('seo_keywords', 'website_meta_keywords'),
            ('og_image', 'website_meta_og_img'),
        ):
            if native_field in target._fields:
                values[item_field] = target[native_field]
        if not values.get('seo_title'):
            values['seo_title'] = target.display_name
        if not values.get('seo_description'):
            description = False
            for field_name in ('description_sale', 'description', 'subtitle', 'content'):
                if field_name in target._fields and target[field_name]:
                    description = target[field_name]
                    break
            values['seo_description'] = description or target.display_name
        if not values.get('seo_keywords'):
            values['seo_keywords'] = self._generate_content_keywords(target)
        values['url'] = target.website_url if 'website_url' in target._fields else getattr(target, 'url', False)
        values['is_published'] = target.website_published if 'website_published' in target._fields else bool(getattr(target, 'active', False))
        values['is_indexed'] = bool(
            target.website_indexed and values.get('is_published')
        ) if 'website_indexed' in target._fields else False
        website = self.env['website'].browse(target.website_id.id) if 'website_id' in target._fields and target.website_id else self.env['website'].search([], order='sequence, id', limit=1)
        values['website_id'] = website.id
        values['canonical_url'] = self._canonical_for_target(target, website)
        return values

    @api.model
    def _seo_content_text(self, target):
        """Collect public-facing copy from the supported record without scraping URLs."""
        field_names = (
            'name', 'title', 'subtitle', 'description', 'description_sale',
            'description_ecommerce', 'content', 'body', 'arch',
            'website_meta_title', 'website_meta_description',
            'diligence_benefit_text',
        )
        parts = []
        for field_name in field_names:
            if field_name not in target._fields:
                continue
            value = target[field_name]
            if not value:
                continue
            if hasattr(value, 'display_name') and not isinstance(value, str):
                value = value.display_name
            value = html2plaintext(value) if isinstance(value, str) else str(value)
            parts.append(value)
        for field_name in ('diligence_package_type_id', 'diligence_delivery_mode_id'):
            if field_name in target._fields and target[field_name]:
                parts.append(target[field_name].display_name)
        return ' '.join(parts)

    @api.model
    def _generate_content_keywords(self, target, limit=10):
        """Generate deterministic keywords from the record content.

        This is intentionally local and repeatable: it does not call an external
        AI or search service, and it never changes an existing custom keyword set.
        """
        text = self._seo_content_text(target)
        words = re.findall(r"[\wÀ-ÿ]{3,}", text.lower(), flags=re.UNICODE)
        stopwords = {
            'yang', 'dan', 'dengan', 'untuk', 'dari', 'pada', 'atau', 'adalah',
            'akan', 'dalam', 'ini', 'itu', 'the', 'and', 'with', 'for', 'from',
            'your', 'you', 'are', 'this', 'that', 'our', 'learn', 'course',
            'academy', 'www', 'http', 'https',
        }
        words = [word for word in words if word not in stopwords and not word.isdigit()]
        counts = Counter(words)
        candidates = []
        display_name = getattr(target, 'display_name', '')
        if display_name:
            candidates.append(display_name.strip())
        for word, _count in counts.most_common(limit * 2):
            if word not in candidates:
                candidates.append(word)
            if len(candidates) >= limit:
                break
        return ', '.join(candidate for candidate in candidates if candidate)[:500]

    def write(self, vals):
        if 'is_indexed' in vals and vals['is_indexed']:
            for item in self:
                if not item.is_published or item._target_is_private(item._get_target()):
                    raise UserError(_('Publish the content before enabling indexing.'))
        if 'seo_keywords' in vals and vals['seo_keywords']:
            vals.setdefault('keyword_source', 'manual')
        result = super().write(vals)
        self.write({'last_updated': fields.Datetime.now()}) if 'last_updated' not in vals else None
        self._sync_to_target(vals)
        return result

    def action_set_indexed(self):
        self.write({'is_indexed': True})
        return True

    def action_set_noindex(self):
        self.write({'is_indexed': False})
        return True

    def action_set_published(self):
        self.write({'is_published': True})
        return True

    def action_set_unpublished(self):
        self.write({'is_published': False, 'is_indexed': False})
        return True

    def action_sync_from_source(self):
        for item in self:
            target = item._get_target()
            if target:
                super(DiligenceSeoItem, item).write(self._target_values(target))
        self.invalidate_recordset()
        return True

    def action_generate_defaults(self):
        """Fill only empty SEO fields and keep existing custom SEO unchanged."""
        for item in self:
            target = item._get_target()
            if not target:
                continue
            generated = item._target_values_for_create(item.res_model, target)
            vals = {
                field_name: generated[field_name]
                for field_name in ('seo_title', 'seo_description', 'seo_keywords', 'url')
                if not item[field_name] and generated.get(field_name)
            }
            if vals:
                item.write(vals)
        return True

    def action_generate_content_keywords(self):
        """Fill empty keywords from title, description and supported content fields."""
        for item in self:
            if item.seo_keywords:
                continue
            target = item._get_target()
            if target:
                item.write({
                    'seo_keywords': item._generate_content_keywords(target),
                    'keyword_source': 'generated',
                    'keywords_generated_at': fields.Datetime.now(),
                })
        return True

    def _get_search_keyword_suggestions(self, target, limit=10):
        """Return popular internal-search terms that are relevant to ``target``.

        Search terms are only suggestions. They are never written to the native
        SEO fields until a manager explicitly presses the apply button.
        """
        content = self._seo_content_text(target).lower()
        content_words = set(re.findall(r"[\wÀ-ÿ]{3,}", content, flags=re.UNICODE))
        stopwords = {
            'yang', 'dan', 'dengan', 'untuk', 'dari', 'pada', 'atau', 'adalah',
            'akan', 'dalam', 'ini', 'itu', 'the', 'and', 'with', 'for', 'from',
            'your', 'you', 'are', 'this', 'that', 'our', 'learn', 'course',
        }
        suggestions = []
        terms = self.env['diligence.seo.search.term'].sudo().search(
            [('active', '=', True)],
            order='search_count desc, last_searched desc, id desc',
            limit=100,
        )
        for term in terms:
            words = set(re.findall(r"[\wÀ-ÿ]{3,}", term.name.lower(), flags=re.UNICODE)) - stopwords
            if words and (words & content_words or term.name.lower() in content):
                suggestions.append(term.name)
            if len(suggestions) >= limit:
                break
        return suggestions

    @api.depends('seo_title', 'seo_description', 'seo_keywords', 'res_model', 'res_id')
    def _compute_search_keyword_suggestions(self):
        for item in self:
            target = item._get_target()
            item.search_keyword_suggestions = ', '.join(
                item._get_search_keyword_suggestions(target)
            ) if target else False

    def action_apply_search_keyword_suggestions(self):
        """Append relevant popular search terms without replacing custom SEO."""
        for item in self:
            target = item._get_target()
            if not target:
                continue
            suggestions = item._get_search_keyword_suggestions(target)
            existing = [part.strip() for part in (item.seo_keywords or '').split(',') if part.strip()]
            existing_keys = {part.casefold() for part in existing}
            for suggestion in suggestions:
                if suggestion.casefold() not in existing_keys:
                    existing.append(suggestion)
                    existing_keys.add(suggestion.casefold())
            if existing:
                item.write({'seo_keywords': ', '.join(existing)[:500]})
        return True

    def action_update_all_sources(self):
        """Refresh URLs and canonical URLs without overwriting custom SEO copy."""
        items = self or self.search([])
        for item in items:
            target = item._get_target()
            if not target:
                continue
            source_values = item._target_values(target)
            item.write({
                "url": source_values.get("url", False),
                "canonical_url": source_values.get("canonical_url", False),
                "last_audited_at": fields.Datetime.now(),
            })
        return True

    def action_sync_all_sources(self):
        for model in self._allowed_models():
            if model not in self.env:
                continue
            targets = self.env[model].sudo().with_context(active_test=False).search([])
            for target in targets:
                if not self.search_count([('res_model', '=', model), ('res_id', '=', target.id)]):
                    self.create({'content_type': model, 'res_model': model, 'res_id': target.id})
        return True


class DiligenceSeoSearchTerm(models.Model):
    _name = 'diligence.seo.search.term'
    _description = 'Diligence Internal Search Keyword'
    _order = 'search_count desc, last_searched desc, name'

    name = fields.Char(required=True, index=True)
    normalized_term = fields.Char(required=True, index=True)
    search_count = fields.Integer(default=0, required=True)
    result_count = fields.Integer(default=0)
    first_searched = fields.Datetime(default=fields.Datetime.now, readonly=True)
    last_searched = fields.Datetime(default=fields.Datetime.now, required=True)
    active = fields.Boolean(default=True)

    _term_unique = models.Constraint(
        'UNIQUE(normalized_term)',
        'This search term is already being tracked.',
    )

    @api.model
    def record_query(self, query, result_count=0):
        """Record an anonymous, normalized search query.

        No visitor identity, IP address, cookie, or request headers are stored.
        """
        query = re.sub(r'\s+', ' ', str(query or '')).strip()[:120]
        if len(query) < 2 or not re.search(r'[\wÀ-ÿ]', query, flags=re.UNICODE):
            return self.browse()
        normalized = query.casefold()
        now = fields.Datetime.now()
        values = {
            'name': query,
            'normalized_term': normalized,
            'result_count': max(0, int(result_count or 0)),
            'last_searched': now,
        }
        Term = self.sudo()
        term = Term.search([('normalized_term', '=', normalized)], limit=1)
        if term:
            term.write({
                'search_count': term.search_count + 1,
                'result_count': values['result_count'],
                'last_searched': now,
            })
            return term
        try:
            with self.env.cr.savepoint():
                return Term.create(values | {'search_count': 1})
        except IntegrityError:
            term = Term.search([('normalized_term', '=', normalized)], limit=1)
            if term:
                term.write({
                    'search_count': term.search_count + 1,
                    'result_count': values['result_count'],
                    'last_searched': now,
                })
            return term
