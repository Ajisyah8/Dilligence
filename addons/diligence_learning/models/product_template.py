from markupsafe import Markup, escape

from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    diligence_package_type = fields.Selection([
        ('starter', 'Starter Pack'),
        ('community', 'Community'),
        ('consultation', 'Consultation'),
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
    diligence_early_bird_price = fields.Float('Early Bird Price', copy=False)
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
