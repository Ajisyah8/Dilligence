# -*- coding: utf-8 -*-
{
    'name': 'eLearning YouTube Embed Cleanup',
    'version': '1.0.0',
    'summary': 'Normalize YouTube URLs and player parameters in eLearning slides',
    'category': 'Website/eLearning',
    'license': 'LGPL-3',
    'depends': ['website_slides'],
    'data': [],
    'assets': {
        'web.assets_frontend': [
            'website_slides_youtube_clean/static/src/xml/website_slides_youtube_templates.xml',
            'website_slides_youtube_clean/static/src/js/clean_video_controls.js',
            'website_slides_youtube_clean/static/src/scss/clean_video_controls.scss',
        ],
    },
    'installable': True,
    'application': False,
}
