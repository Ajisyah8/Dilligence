# -*- coding: utf-8 -*-
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from markupsafe import Markup, escape

from odoo import api, models


class SlideSlide(models.Model):
    _inherit = 'slide.slide'

    @api.depends(
        'slide_category', 'source_type', 'binary_content', 'google_drive_id',
        'video_url', 'video_source_type', 'youtube_id', 'vimeo_id',
    )
    def _compute_embed_code(self):
        """Keep the standard Odoo embed generation and normalize YouTube only.

        Vimeo, Google Drive, local uploads, and other external videos are left
        untouched. No database fields or tables are added by this module.
        """
        super()._compute_embed_code()
        for slide in self.filtered(lambda record: record.video_source_type == 'youtube'):
            embed_url = self._youtube_embed_url(slide)
            if not embed_url:
                continue
            iframe = Markup(
                '<iframe src="%s" allowFullScreen="true" frameborder="0" '
                'enablejsapi="1" '
                'allow="accelerometer; autoplay; clipboard-write; encrypted-media; '
                'gyroscope; picture-in-picture; web-share" '
                'referrerpolicy="strict-origin-when-cross-origin" '
                'aria-label="YouTube"></iframe>'
            ) % escape(embed_url)
            slide.embed_code = iframe
            slide.embed_code_external = iframe

        for slide in self.filtered(lambda record: record.video_source_type == 'external'):
            if not slide.video_url or not re.search(
                r'\.(?:mp4|webm|ogg)(?:[?#].*)?$', slide.video_url, re.IGNORECASE
            ):
                continue
            video = Markup(
                '<video preload="metadata" playsinline '
                'class="w-100 h-100 o_wslides_clean_video" aria-label="External video">'
                '<source src="%s"></source>'
                '</video>'
            ) % escape(slide.video_url)
            slide.embed_code = video
            slide.embed_code_external = video

    def _youtube_embed_url(self, slide):
        """Build one canonical embed URL for watch, short, and embed links."""
        if not slide.youtube_id:
            return False

        original_url = slide.video_url or ''
        original_query = dict(parse_qsl(urlsplit(original_url).query, keep_blank_values=True))
        # The source URL may contain playback options such as start/end.
        original_query.pop('v', None)
        original_query.update({
            'rel': '0',
            'modestbranding': '1',
            'playsinline': '1',
            'enablejsapi': '1',
            'origin': slide.get_base_url().rstrip('/'),
        })
        return urlunsplit((
            'https',
            'www.youtube-nocookie.com',
            '/embed/%s' % slide.youtube_id,
            urlencode(original_query),
            '',
        ))
