from markupsafe import Markup, escape

from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # Kept for backward compatibility with existing products. New products
    # must use diligence_package_type_id, which is configurable from Odoo.
    diligence_package_type = fields.Selection([
        ('starter', 'Starter Pack'),
        ('community', 'Community'),
        ('consultation', 'Consultation'),
        ('zoom_group', 'Zoom Group Learning'),
        ('zoom_private', 'Zoom Private Learning'),
        ('zoom_coaching', 'Zoom Private Coaching'),
        ('business', 'Business Class'),
    ], string='Diligence Package')
    diligence_package_type_id = fields.Many2one(
        'diligence.package.type', string='Package Type',
        ondelete='restrict', index=True,
        help='Select a configurable package type. Create a new type directly from this field when allowed.',
    )
    diligence_sales_status = fields.Selection([
        ('available', 'Available'),
        ('coming_soon', 'Coming Soon'),
        ('full', 'Full Slot'),
    ], string='Package Availability', default='available', required=True, copy=False,
       help='Coming Soon or Full Slot keeps the package visible on the website, but prevents new purchases.')
    diligence_course_ids = fields.Many2many(
        'slide.channel',
        'diligence_package_slide_channel_rel',
        'product_tmpl_id',
        'channel_id',
        string='Included Courses',
        help='Courses automatically unlocked after this package is paid.',
    )
    diligence_has_coming_soon_course = fields.Boolean(
        string='Has Coming Soon Course', compute='_compute_diligence_course_availability',
    )
    diligence_has_available_course = fields.Boolean(
        string='Has Available Course', compute='_compute_diligence_course_availability',
    )
    diligence_forum_access = fields.Boolean('Community Forum Access')
    diligence_consultation = fields.Boolean('Coach Consultation Included')
    diligence_delivery_mode = fields.Selection([
        ('self', 'Self Learning'),
        ('group_zoom', 'Group Zoom'),
        ('private_zoom', 'Private Zoom'),
        ('one_on_one', 'Private 1-on-1'),
    ], string='Delivery Mode (Legacy)', default='self')
    diligence_delivery_mode_id = fields.Many2one(
        'diligence.delivery.mode', string='Delivery Mode', ondelete='restrict', index=True,
        help='Select a configurable delivery mode. New modes can be created from Sales configuration.',
    )
    diligence_session_frequency = fields.Integer(
        'Sessions per Week', default=0,
        help='Used for scheduled Zoom products. Zero means the schedule is managed manually.',
    )
    diligence_session_duration_minutes = fields.Integer('Session Duration (Minutes)', default=60)
    diligence_max_participants = fields.Integer(
        'Maximum Participants', default=0,
        help='Zero means no capacity limit. Use 1 for one-on-one coaching.',
    )
    diligence_teacher_feedback = fields.Boolean('Teacher Feedback Included')
    diligence_live_qna = fields.Boolean('Monthly Live Q&A Included')
    diligence_whatsapp_group_link = fields.Char(
        'WhatsApp Group Link', copy=False,
        help='Private group link shown only to students with a valid paid order for this package.',
    )
    diligence_whatsapp_group_jid = fields.Char(
        'WhatsApp Group ID (JID)', copy=False,
        help='Evolution API group ID, for example 1203...@g.us. If set, paid students who submit a not-continuing decision and reason are removed immediately. The connected WhatsApp account must be a group admin.',
    )
    diligence_whatsapp_payment_message = fields.Text(
        'WhatsApp Payment Message', copy=False,
        help='Optional payment confirmation for this package. Use %(order)s for the order number. The WhatsApp group link is added automatically when configured on the package.',
    )
    diligence_early_bird_enabled = fields.Boolean('Enable Early Bird', copy=False)
    diligence_early_bird_price = fields.Float('Early Bird Price', copy=False)
    diligence_early_bird_start_date = fields.Date('Early Bird Start Date', copy=False)
    diligence_early_bird_duration_days = fields.Integer(
        'Early Bird Duration (Days)', default=30, copy=False,
        help='Optional. Used only when a start date is set.',
    )
    diligence_early_bird_end_date = fields.Date(
        'Early Bird End Date', compute='_compute_diligence_early_bird_dates', store=True,
    )
    diligence_benefit_text = fields.Text(
        'Package Benefits',
        translate=True,
        help='One benefit per line. This content is used on the website and quotation automatically.',
    )
    diligence_benefit_html = fields.Html(
        'Generated Package Benefits HTML', compute='_compute_diligence_benefits', sanitize=True,
    )
    diligence_access_duration_days = fields.Integer(
        'Access Duration (Days)',
        help='Controls course access after payment and the price period shown on the website. Durations below 365 days display in days; longer durations display as years, months, and remaining days. This does not enable automatic recurring charges.',
    )

    def _diligence_access_duration_label(self):
        """Format short durations as days and longer ones as years/months/days."""
        self.ensure_one()
        days = self.diligence_access_duration_days or 0
        if days <= 0:
            return False
        if days < 365:
            return _('%(count)s day', count=days) if days == 1 else _('%(count)s days', count=days)

        years, remaining_days = divmod(days, 365)
        months, remaining_days = divmod(remaining_days, 30)
        parts = []
        if years:
            parts.append(_('%(count)s year', count=years) if years == 1 else _('%(count)s years', count=years))
        if months:
            parts.append(_('%(count)s month', count=months) if months == 1 else _('%(count)s months', count=months))
        if remaining_days or not parts:
            parts.append(_('%(count)s day', count=remaining_days) if remaining_days == 1 else _('%(count)s days', count=remaining_days))
        return ' '.join(parts)

    def _diligence_price_period_label(self):
        """Describe the configured access period beside the website price."""
        duration = self._diligence_access_duration_label()
        return '/ ' + duration if duration else False

    @api.depends(
        'diligence_course_ids', 'diligence_course_ids.diligence_availability',
        'product_variant_ids.service_tracking', 'product_variant_ids.channel_ids',
        'product_variant_ids.channel_ids.diligence_availability',
    )
    def _compute_diligence_course_availability(self):
        for product in self:
            courses = product._diligence_course_access_course_ids()
            product.diligence_has_coming_soon_course = any(
                course.diligence_availability == 'coming_soon' for course in courses
            )
            product.diligence_has_available_course = any(
                course.diligence_availability != 'coming_soon' for course in courses
            )

    @api.depends('diligence_early_bird_start_date', 'diligence_early_bird_duration_days')
    def _compute_diligence_early_bird_dates(self):
        for product in self:
            if product.diligence_early_bird_start_date and product.diligence_early_bird_duration_days > 0:
                product.diligence_early_bird_end_date = (
                    product.diligence_early_bird_start_date
                    + timedelta(days=product.diligence_early_bird_duration_days - 1)
                )
            else:
                product.diligence_early_bird_end_date = False

    @api.constrains(
        'diligence_early_bird_enabled', 'diligence_early_bird_price', 'diligence_early_bird_start_date',
        'diligence_early_bird_duration_days', 'list_price',
    )
    def _check_diligence_early_bird(self):
        for product in self:
            if not product.diligence_early_bird_enabled:
                continue
            # An empty/zero price is treated as an intentionally disabled
            # promotion, so staff can clear the Early Bird fields and save.
            if product.diligence_early_bird_price <= 0:
                continue
            if product.diligence_early_bird_price >= product.list_price:
                raise ValidationError('Early Bird Price must be lower than the normal sales price.')
            if product.diligence_early_bird_start_date and product.diligence_early_bird_duration_days <= 0:
                raise ValidationError('Early Bird Duration must be greater than zero.')

    def _diligence_early_bird_price_for_date(self, sale_date=False):
        self.ensure_one()
        sale_date = sale_date or fields.Date.context_today(self)
        if (
            self.diligence_early_bird_enabled
            and self.diligence_early_bird_price > 0
            and (
                not self.diligence_early_bird_start_date
                or (
                    self.diligence_early_bird_end_date
                    and self.diligence_early_bird_start_date <= sale_date <= self.diligence_early_bird_end_date
                )
            )
        ):
            return self.diligence_early_bird_price
        return False

    def _get_additionnal_combination_info(self, product_or_template, quantity, uom, date, website):
        """Expose the active Early Bird price to the website product page."""
        combination_info = super()._get_additionnal_combination_info(
            product_or_template, quantity, uom, date, website,
        )
        package = (
            product_or_template.product_tmpl_id
            if product_or_template._name == 'product.product'
            else product_or_template
        )
        early_bird_price = package._diligence_early_bird_price_for_date(date)
        if not early_bird_price:
            return combination_info

        currency = combination_info['currency']
        early_bird_display_price = product_or_template.currency_id._convert(
            early_bird_price,
            currency,
            self.env.company,
            date,
        )
        if currency.compare_amounts(early_bird_display_price, combination_info['price']) < 0:
            normal_price = package.currency_id._convert(
                package.list_price,
                currency,
                self.env.company,
                date,
            )
            combination_info.update({
                'price': early_bird_display_price,
                'list_price': max(combination_info['list_price'], normal_price),
                'has_discounted_price': True,
                'discount_end_date': package.diligence_early_bird_end_date,
            })
        return combination_info

    def _diligence_is_package(self):
        self.ensure_one()
        return bool((self.diligence_package_type_id or self.diligence_package_type) and self.diligence_course_ids)

    def _diligence_is_standalone_course_product(self):
        """Whether this sellable product grants course access without a tier package."""
        self.ensure_one()
        return bool(
            (self.diligence_course_ids or self.product_variant_ids.filtered(
                lambda variant: variant.service_tracking == 'course' and variant.channel_ids
            ))
            and not self.diligence_package_type_id
            and not self.diligence_package_type
        )

    def _diligence_course_access_course_ids(self):
        self.ensure_one()
        native_course_variants = self.product_variant_ids.filtered(
            lambda variant: variant.service_tracking == 'course'
        )
        return self.diligence_course_ids | native_course_variants.mapped('channel_ids')

    def _diligence_is_course_access_product(self):
        self.ensure_one()
        return self._diligence_is_package() or self._diligence_is_standalone_course_product()

    def _diligence_package_type_code(self):
        self.ensure_one()
        return self.diligence_package_type_id.code if self.diligence_package_type_id else self.diligence_package_type

    def _diligence_delivery_mode_code(self):
        self.ensure_one()
        return self.diligence_delivery_mode_id.code if self.diligence_delivery_mode_id else self.diligence_delivery_mode

    def _diligence_benefit_lines(self):
        self.ensure_one()
        lines = [
            'Learn Mandarin with practice exercises',
            'Learn correct pronunciation and tones',
            'Build your first 300 basic words',
            'Improve practical everyday conversations',
            '30 PDF learning materials',
            '30 listening audio materials',
            '30 lesson explanation videos',
            '30 quiz tests with answer keys',
            '30 dictation audio sets with answer keys',
        ]
        if self.diligence_forum_access:
            lines.append('Discussion forum with fellow learners and seniors')
        if self.diligence_consultation:
            lines.extend([
                'Progress review and learning guidance from an experienced teacher',
                'Live Q&A session once a month',
            ])
        if self.diligence_delivery_mode == 'group_zoom':
            lines.extend([
                'Unlimited website access',
                'Group Zoom learning session',
                'Private WhatsApp group discussion',
                'Free consultation',
            ])
        elif self.diligence_delivery_mode == 'private_zoom':
            lines.extend([
                'Unlimited website access',
                'Private Zoom learning session',
                'Private WhatsApp group discussion',
                'Free consultation',
            ])
        elif self.diligence_delivery_mode == 'one_on_one':
            lines.extend([
                'Unlimited website access',
                'Private one-on-one coaching',
                'Business-focused learning support',
                'Free consultation',
            ])
        if self.diligence_teacher_feedback:
            lines.append('Direct feedback from an experienced teacher')
        if self.diligence_live_qna and not self.diligence_consultation:
            lines.append('Live Q&A session once a month')
        return lines

    @api.depends('diligence_benefit_text')
    def _compute_diligence_benefits(self):
        for product in self:
            lines = [line.strip().lstrip('- ').strip() for line in (product.diligence_benefit_text or '').splitlines() if line.strip()]
            product.diligence_benefit_html = Markup(
                '<ul class="list-unstyled mb-0">%s</ul>' % ''.join(
                    '<li><i class="fa fa-check text-success me-2"></i>%s</li>' % escape(line)
                    for line in lines
                )
            ) if lines else False
