from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class DiligenceSeoItem(models.Model):
    _name = 'diligence.seo.item'
    _description = 'Diligence SEO Manager Item'
    _order = 'seo_status, name'

    name = fields.Char(required=True)
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
    is_indexed = fields.Boolean(default=True)
    is_published = fields.Boolean(default=False)
    seo_score = fields.Integer(compute='_compute_seo_score_status', store=True)
    seo_status = fields.Selection([
        ('complete', 'Complete'),
        ('warning', 'Warning'),
        ('needs_improvement', 'Needs Improvement'),
    ], compute='_compute_seo_score_status', store=True)
    seo_warnings = fields.Text(compute='_compute_seo_warnings')
    last_updated = fields.Datetime(default=fields.Datetime.now, readonly=True)

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
        values['canonical_url'] = values.get('url')
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

    @api.constrains('res_model', 'res_id', 'is_indexed', 'url')
    def _check_target(self):
        for item in self:
            if item.content_type != item.res_model:
                raise ValidationError(_('Content Type must match the selected content model.'))
            if item.res_id <= 0 or not item._get_target():
                raise ValidationError(_('The selected content record does not exist.'))
            if item.is_indexed and (not item.is_published or item._target_is_private(item._get_target())):
                raise ValidationError(_('Private or unpublished content cannot be marked as indexed.'))
            if item.url and self.search_count([('url', '=', item.url), ('id', '!=', item.id)]):
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
        values['url'] = target.website_url if 'website_url' in target._fields else getattr(target, 'url', False)
        values['is_published'] = target.website_published if 'website_published' in target._fields else bool(getattr(target, 'active', False))
        values['is_indexed'] = bool(
            target.website_indexed and values.get('is_published')
        ) if 'website_indexed' in target._fields else False
        values['canonical_url'] = values['url']
        return values

    def write(self, vals):
        if 'is_indexed' in vals and vals['is_indexed']:
            for item in self:
                if not item.is_published or item._target_is_private(item._get_target()):
                    raise UserError(_('Publish the content before enabling indexing.'))
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
                for field_name in ('seo_title', 'seo_description', 'url')
                if not item[field_name] and generated.get(field_name)
            }
            if vals:
                item.write(vals)
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
                "canonical_url": source_values.get("url", False),
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
