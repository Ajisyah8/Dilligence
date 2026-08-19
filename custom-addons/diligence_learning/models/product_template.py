from markupsafe import Markup, escape

from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    diligence_package_type = fields.Selection([
        ('starter', 'Starter Pack'),
        ('community', 'Community'),
        ('consultation', 'Consultation'),
        ('zoom_group', 'Zoom Group Learning'),
        ('zoom_private', 'Zoom Private Learning'),
        ('zoom_coaching', 'Zoom Private Coaching'),
        ('business', 'Business Class'),
    ], string='Diligence Package')
    diligence_course_ids = fields.Many2many(
        'slide.channel',
        'diligence_package_slide_channel_rel',
        'product_tmpl_id',
        'channel_id',
        string='Included Courses',
        help='Courses automatically unlocked after this package is paid.',
    )
    diligence_forum_access = fields.Boolean('Community Forum Access')
    diligence_consultation = fields.Boolean('Coach Consultation Included')
    diligence_delivery_mode = fields.Selection([
        ('self', 'Self Learning'),
        ('group_zoom', 'Group Zoom'),
        ('private_zoom', 'Private Zoom'),
        ('one_on_one', 'Private 1-on-1'),
    ], string='Delivery Mode', default='self')
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
        help='One benefit per line. This content is used on the website and quotation automatically.',
    )
    diligence_benefit_html = fields.Html(
        'Generated Package Benefits HTML', compute='_compute_diligence_benefits', sanitize=True,
    )
    diligence_access_duration_days = fields.Integer(
        'Access Duration (Days)',
        help='Leave empty/zero for unlimited access. Expiry automation is not enabled in Phase 1.',
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
        return bool(self.diligence_package_type and self.diligence_course_ids)

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
