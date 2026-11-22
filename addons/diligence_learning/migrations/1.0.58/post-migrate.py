import logging

from odoo import SUPERUSER_ID, api


_logger = logging.getLogger(__name__)


ENGLISH_HOMEPAGE_HERO_COPY = {
    'Buka lebih banyak peluang dengan kemampuan bahasa.':
        'Unlock more opportunities with language skills.',
    'Belajar Bahasa Mandarin dan Bahasa Inggris melalui program yang terstruktur, praktis, dan dirancang untuk membantu Anda berkomunikasi lebih percaya diri di dunia kerja dan kehidupan sehari-hari.':
        'Learn Mandarin and English through structured, practical programs designed to help you communicate with confidence at work and in everyday life.',
    'Setiap program dirancang berdasarkan pengalaman lebih dari 20 tahun dalam pengajaran dan penerjemahan bahasa.':
        'Every program is shaped by more than 20 years of experience in language teaching and translation.',
    'Temukan Program yang Tepat': 'Find the Right Program',
    'Pengajar Anda': 'Your Teacher',
    'Mandarin Teacher & Bahasa Inggris': 'Mandarin & English Teacher',
    'Pengajar Mandarin & Bahasa Inggris': 'Mandarin & English Teacher',
    'BAHASA INGGRIS': 'ENGLISH',
}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    website = env['website'].search([
        ('domain', 'ilike', 'diligenceenglish.com'),
    ], limit=1)
    homepage = env['website.page'].search([
        ('website_id', '=', website.id),
        ('url', '=', '/'),
    ], order='id', limit=1) if website else env['website.page'].browse()
    view = homepage.view_id if homepage else env['ir.ui.view'].browse()
    if not view:
        _logger.warning('English homepage hero translation skipped: homepage not found')
        return

    language = website.default_lang_id.code or 'en_US'
    localized_view = view.with_context(lang=language)
    arch = localized_view.arch_db or ''
    updated_arch = arch
    translated_count = 0
    for source in sorted(ENGLISH_HOMEPAGE_HERO_COPY, key=len, reverse=True):
        if source in updated_arch:
            updated_arch = updated_arch.replace(source, ENGLISH_HOMEPAGE_HERO_COPY[source])
            translated_count += 1

    if updated_arch != arch:
        localized_view.with_context(
            lang=language,
            diligence_website_syncing=True,
            no_cow=True,
        ).write({'arch_db': updated_arch})
    _logger.info(
        'Translated English homepage hero in view %s (%s replacements)',
        view.id, translated_count,
    )
