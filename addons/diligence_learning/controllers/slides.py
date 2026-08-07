import werkzeug

from odoo import http
from odoo.addons.website_slides.controllers.main import WebsiteSlides
from odoo.http import request


class DiligenceWebsiteSlides(WebsiteSlides):
    @http.route()
    def slide_view(self, slide, **kwargs):
        # Keep Odoo's standard completion behaviour for every other course.
        if slide.channel_id.id not in (7, 8, 9):
            return super().slide_view(slide, **kwargs)

        if not slide.channel_id.can_access_from_current_website() or not slide.active:
            raise werkzeug.exceptions.NotFound()
        membership = request.env['slide.channel.partner'].sudo().search([
            ('channel_id', '=', slide.channel_id.id),
            ('partner_id', '=', request.env.user.partner_id.commercial_partner_id.id),
            ('member_status', 'in', ('joined', 'ongoing', 'completed')),
        ], limit=1)
        if membership and not membership._diligence_access_is_valid():
            raise werkzeug.exceptions.Forbidden('This course access has expired.')
        if slide.is_category:
            return request.redirect(slide.channel_id.website_absolute_url)

        # Diligence learners decide completion through media end, quiz completion,
        # or the manual circle button. Opening an article must not mark it done.
        self._set_viewed_slide(slide)
        values = self._get_slide_detail(slide)
        if slide.question_ids:
            values.update(self._get_slide_quiz_data(slide))
        values['channel_progress'] = self._get_channel_progress(slide.channel_id, include_quiz=True)
        values['category_data'] = self._prepare_collapsed_categories(values['category_data'], slide, False)
        values.update({
            'search_category': slide.category_id if kwargs.get('search_category') else None,
            'search_tag': request.env['slide.tag'].browse(int(kwargs.get('search_tag'))) if kwargs.get('search_tag') else None,
            'slide_categories': dict(request.env['slide.slide']._fields['slide_category']._description_selection(request.env)) if kwargs.get('search_slide_category') else None,
            'search_slide_category': kwargs.get('search_slide_category'),
            'search_uncategorized': kwargs.get('search_uncategorized'),
        })
        values['channel'] = slide.channel_id
        values = self._prepare_additional_channel_values(values, **kwargs)
        values['signup_allowed'] = request.env['res.users'].sudo()._get_signup_invitation_scope() == 'b2c'
        if kwargs.get('fullscreen') == '1':
            values.update(self._slide_channel_prepare_review_values(slide.channel_id))
            return request.render('website_slides.slide_fullscreen', values)
        values.pop('channel', None)
        return request.render('website_slides.slide_main', values)
