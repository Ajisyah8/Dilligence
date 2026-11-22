import logging
import html

from lxml import etree

from odoo import SUPERUSER_ID, api
from odoo.tools.translate import xml_translate


_logger = logging.getLogger(__name__)


ID_TO_EN = {
    'Buka lebih banyak peluang dengan kemampuan bahasa.': 'Unlock more opportunities with language skills.',
    'Belajar Bahasa Mandarin dan Bahasa Inggris melalui program yang terstruktur, praktis, dan dirancang untuk membantu Anda berkomunikasi lebih percaya diri di dunia kerja dan kehidupan sehari-hari.': 'Learn Mandarin and English through structured, practical programs designed to help you communicate with confidence at work and in everyday life.',
    'Setiap program dirancang berdasarkan pengalaman lebih dari 20 tahun dalam pengajaran dan penerjemahan bahasa.': 'Every program is shaped by more than 20 years of experience in language teaching and translation.',
    'Temukan Program yang Tepat': 'Find the Right Program',
    'Jadwalkan Wawancara Gratis': 'Schedule a Free Interview',
    'Pengajar Anda': 'Your Teacher',
    'PENGAJAR ANDA': 'YOUR TEACHER',
    'Pengajar Bahasa Mandarin & Inggris': 'Mandarin & English Tutor',
    'Guru Mandarin & Inggris': 'Mandarin & English Tutor',
    'Guru Mandarin': 'Mandarin Tutor',
    'Guru Inggris': 'English Tutor',
    'Apa yang Baru?': "What's New",
    'Apa yang Baru di DILIGENCE ACADEMY ?': "What's New at DILIGENCE ACADEMY?",
    'Program baru untuk mendukung perjalanan belajar dan rencana masa depan Anda.': 'New programs to support your learning journey and future plans.',
    'Kelas Mandarin Online Terstruktur': 'Structured Online Mandarin Classes',
    'Belajar Mandarin dengan alur yang jelas, fleksibel, dan bisa diikuti sesuai ritme Anda.': 'Learn Mandarin through a clear, flexible path at your own pace.',
    'Lihat Program': 'Explore Programs',
    'Lihat Kursus': 'View Courses',
    'Jalur Beasiswa Kuliah ke China': 'Study in China Scholarship Pathway',
    'Kenali peluang studi ke China dan persiapkan langkah Anda bersama tim Diligence.': 'Explore study opportunities in China and plan your next steps with the Diligence team.',
    'Lihat testimoni siswa beasiswa': 'Read scholarship student stories',
    'Baca cerita siswa': 'Read student stories',
    'Ujian Sertifikasi Bahasa Inggris Cambridge': 'Cambridge English Qualifications',
    'Persiapkan kemampuan bahasa Anda dengan target sertifikasi yang jelas dan terukur.': 'Build your language skills with clear, measurable certification goals.',
    'Lihat jadwal ujian Cambridge': 'View Cambridge exam dates',
    'Lihat jadwal ujian': 'View exam dates',
    'Program Kami': 'Our Programs',
    'Program belajar yang tersedia': 'Available learning programs',
    'Pilih program English atau Mandarin sesuai kebutuhan Anda.': 'Choose an English or Mandarin program to suit your needs.',
    'Kursus Bahasa Mandarin': 'Mandarin Courses',
    'Pelajari pelafalan, nada, kosakata dasar, dan percakapan Mandarin secara bertahap.': 'Learn pronunciation, tones, essential vocabulary, and Mandarin conversation step by step.',
    'Lihat Kursus Mandarin': 'Explore Mandarin Courses',
    'Kursus Bahasa Inggris': 'English Courses',
    'Bangun kepercayaan diri, kelancaran percakapan, dan kemampuan bahasa untuk kebutuhan sehari-hari maupun profesional.': 'Build confidence, conversational fluency, and language skills for everyday and professional use.',
    'Lihat Kursus Bahasa Inggris': 'Explore English Courses',
    'Program Bahasa Inggris': 'English Programs',
    'Tingkatkan Bahasa Inggrismu secara natural': 'Improve Your English Naturally',
    'Pelajari bahasa Inggris dengan konsep belajar yang praktis dan menyenangkan.': 'Learn English through a practical and enjoyable approach.',
    'Berbicara lebih percaya diri': 'Speak with more confidence',
    'Menunjang karier': 'Support your career',
    'Materi praktis': 'Practical learning materials',
    'Alur belajar terstruktur': 'A structured learning path',
    'Paket Belajar': 'Learning Packages',
    'Pilih Paket Belajar Anda': 'Choose Your Learning Package',
    'Pilih paket belajar sesuai kebutuhan Anda dengan benefit lengkap, harga transparan, dan penawaran Early Bird.': 'Choose a package that fits your needs, with clear benefits, transparent pricing, and an Early Bird offer.',
    'Belum yakin memilih program?': 'Not sure which program to choose?',
    'Konsultasikan kebutuhan belajar Anda secara gratis bersama tim Diligence.': 'Talk with the Diligence team for a free consultation about your learning goals.',
    'Dapatkan materi belajar terbaru': 'Get the Latest Learning Resources',
    'Daftarkan email Anda untuk menerima tips belajar, materi pilihan, dan informasi program terbaru dari DILIGENCE ACADEMY.': 'Subscribe to receive study tips, selected learning resources, and the latest DILIGENCE ACADEMY program updates.',
    'Langganan': 'Subscribe',
    'Cerita dari Siswa Kami': 'Student Stories',
    'Apa kata siswa tentang DILIGENCE ACADEMY?': 'What Do Students Say About DILIGENCE ACADEMY?',
    'Pengalaman belajar yang nyata dari siswa kami.': 'Real learning experiences from our students.',
    'Kenali Pengajar Kami': 'Meet Our Teachers',
    'Belajar bersama pengajar berpengalaman': 'Learn with experienced teachers',
    'Kenali tim pengajar Diligence Academy.': 'Meet the Diligence Academy teaching team.',
    'Karier': 'Careers',
    'Bergabung dengan tim': 'Join Our Team',
    'Kami terbuka untuk pengajar dan talenta yang ingin ikut mengembangkan pendidikan.': 'We welcome teachers and talented people who want to help shape the future of education.',
    'Lihat Kesempatan': 'Explore Opportunities',
    'Madam Lilis': 'Madam Lilis',
    'Ms Lidya': 'Ms Lidya',
    'Ms Diana': 'Ms Diana',
    'Ms Liana': 'Ms Liana',
    'Ms Yuli': 'Ms Yuli',
    'Mr Steinly': 'Mr Steinly',
    'Ms Lina': 'Ms Lina',
    'Ms Henny': 'Ms Henny',
    'Ms Panggih': 'Ms Panggih',
    'Ms Yolla': 'Ms Yolla',
    'Ms Sofia': 'Ms Sofia',
    'Mr Panji': 'Mr Panji',
    'DILIGENCE ACADEMY': 'DILIGENCE ACADEMY',
}

ID_TO_ZH = {
    'Buka lebih banyak peluang dengan kemampuan bahasa.': '掌握语言，开启更多机遇。',
    'Belajar Bahasa Mandarin dan Bahasa Inggris melalui program yang terstruktur, praktis, dan dirancang untuk membantu Anda berkomunikasi lebih percaya diri di dunia kerja dan kehidupan sehari-hari.': '通过系统且实用的课程学习中文与英文，帮助您在工作和日常生活中更自信地沟通。',
    'Setiap program dirancang berdasarkan pengalaman lebih dari 20 tahun dalam pengajaran dan penerjemahan bahasa.': '每个课程都融入了二十多年的语言教学与翻译经验。',
    'Temukan Program yang Tepat': '找到适合您的课程',
    'Jadwalkan Wawancara Gratis': '预约免费咨询',
    'Pengajar Anda': '您的导师',
    'PENGAJAR ANDA': '您的导师',
    'Pengajar Bahasa Mandarin & Inggris': '中文与英文导师',
    'Guru Mandarin & Inggris': '中文与英文老师',
    'Guru Mandarin': '中文老师',
    'Guru Inggris': '英文老师',
    'Apa yang Baru?': '最新动态',
    'Apa yang Baru di DILIGENCE ACADEMY ?': 'DILIGENCE ACADEMY 最新课程',
    'Program baru untuk mendukung perjalanan belajar dan rencana masa depan Anda.': '全新课程助力您的学习旅程与未来规划。',
    'Kelas Mandarin Online Terstruktur': '系统化在线中文课程',
    'Belajar Mandarin dengan alur yang jelas, fleksibel, dan bisa diikuti sesuai ritme Anda.': '按照清晰、灵活的学习路径，以自己的节奏学习中文。',
    'Lihat Program': '查看课程',
    'Lihat Kursus': '查看课程',
    'Jalur Beasiswa Kuliah ke China': '中国留学奖学金规划',
    'Kenali peluang studi ke China dan persiapkan langkah Anda bersama tim Diligence.': '了解赴华留学机会，并与 Diligence 团队一起规划下一步。',
    'Lihat testimoni siswa beasiswa': '查看奖学金学生分享',
    'Baca cerita siswa': '阅读学生故事',
    'Ujian Sertifikasi Bahasa Inggris Cambridge': '剑桥英语资格考试',
    'Persiapkan kemampuan bahasa Anda dengan target sertifikasi yang jelas dan terukur.': '以清晰、可衡量的目标提升语言能力并备考认证。',
    'Lihat jadwal ujian Cambridge': '查看剑桥考试日期',
    'Lihat jadwal ujian': '查看考试日期',
    'Program Kami': '我们的课程',
    'Program belajar yang tersedia': '可选学习课程',
    'Pilih program English atau Mandarin sesuai kebutuhan Anda.': '根据您的需求选择英文或中文课程。',
    'Kursus Bahasa Mandarin': '中文课程',
    'Pelajari pelafalan, nada, kosakata dasar, dan percakapan Mandarin secara bertahap.': '循序渐进地学习发音、声调、基础词汇和中文会话。',
    'Lihat Kursus Mandarin': '查看中文课程',
    'Kursus Bahasa Inggris': '英文课程',
    'Bangun kepercayaan diri, kelancaran percakapan, dan kemampuan bahasa untuk kebutuhan sehari-hari maupun profesional.': '提升自信、会话流利度，以及日常和职场所需的语言能力。',
    'Lihat Kursus Bahasa Inggris': '查看英文课程',
    'Program Bahasa Inggris': '英文课程项目',
    'Tingkatkan Bahasa Inggrismu secara natural': '自然提升英文能力',
    'Pelajari bahasa Inggris dengan konsep belajar yang praktis dan menyenangkan.': '通过实用、有趣的方式学习英文。',
    'Berbicara lebih percaya diri': '更自信地表达',
    'Menunjang karier': '助力职业发展',
    'Materi praktis': '实用学习材料',
    'Alur belajar terstruktur': '系统化学习路径',
    'Paket Belajar': '学习套餐',
    'Pilih Paket Belajar Anda': '选择适合您的学习套餐',
    'Pilih paket belajar sesuai kebutuhan Anda dengan benefit lengkap, harga transparan, dan penawaran Early Bird.': '选择符合您需求的学习套餐，享有完整权益、透明价格及早鸟优惠。',
    'Belum yakin memilih program?': '还不确定选择哪门课程？',
    'Konsultasikan kebutuhan belajar Anda secara gratis bersama tim Diligence.': '欢迎与 Diligence 团队免费讨论您的学习目标。',
    'Dapatkan materi belajar terbaru': '获取最新学习资源',
    'Daftarkan email Anda untuk menerima tips belajar, materi pilihan, dan informasi program terbaru dari DILIGENCE ACADEMY.': '订阅后即可收到学习建议、精选资料及 DILIGENCE ACADEMY 最新课程资讯。',
    'Langganan': '订阅',
    'Cerita dari Siswa Kami': '学生分享',
    'Apa kata siswa tentang DILIGENCE ACADEMY?': '学生如何评价 DILIGENCE ACADEMY？',
    'Pengalaman belajar yang nyata dari siswa kami.': '聆听学生真实的学习体验。',
    'Kenali Pengajar Kami': '认识我们的老师',
    'Belajar bersama pengajar berpengalaman': '与经验丰富的老师一起学习',
    'Kenali tim pengajar Diligence Academy.': '认识 Diligence Academy 教学团队。',
    'Karier': '加入我们',
    'Bergabung dengan tim': '加入我们的团队',
    'Kami terbuka untuk pengajar dan talenta yang ingin ikut mengembangkan pendidikan.': '欢迎有志于推动教育发展的教师与人才加入。',
    'Lihat Kesempatan': '查看机会',
    'Madam Lilis': 'Lilis 老师',
    'Ms Lidya': 'Lidya 老师',
    'Ms Diana': 'Diana 老师',
    'Ms Liana': 'Liana 老师',
    'Ms Yuli': 'Yuli 老师',
    'Mr Steinly': 'Steinly 老师',
    'DILIGENCE ACADEMY': 'DILIGENCE ACADEMY',
}

TEACHER_NAMES = {
    'Ibu Lilis': 'Madam Lilis',
    'Ibu Lidya': 'Ms Lidya',
    'Ibu Diana': 'Ms Diana',
    'Ibu Liana': 'Ms Liana',
    'Ibu Yuli': 'Ms Yuli',
    'Bapak Steinly': 'Mr Steinly',
    'Ibu Lina': 'Ms Lina',
    'Ibu Henny': 'Ms Henny',
    'Ibu Panggih': 'Ms Panggih',
    'Ibu Yolla': 'Ms Yolla',
    'Nona Sofia': 'Ms Sofia',
    'Tuan Panji': 'Mr Panji',
}
TEACHER_NAMES_ZH = {
    'Madam Lilis': 'Lilis 老师',
    'Ms Lidya': 'Lidya 老师',
    'Ms Diana': 'Diana 老师',
    'Ms Liana': 'Liana 老师',
    'Ms Yuli': 'Yuli 老师',
    'Mr Steinly': 'Steinly 老师',
}
ROLE_ID_TO_EN_ZH = {
    'Pengajar Bahasa Mandarin & Inggris': ('Mandarin & English Tutor', '中文与英文导师'),
    'Guru Mandarin & Inggris': ('Mandarin & English Tutor', '中文与英文老师'),
    'Guru Mandarin': ('Mandarin Tutor', '中文老师'),
    'Guru Inggris': ('English Tutor', '英文老师'),
}


def _replace_teacher_terms(arch, website_language):
    """Apply agreed teacher names/roles to homepage base copy only."""
    if not arch:
        return arch, 0
    try:
        root = etree.fromstring(arch.encode())
    except etree.XMLSyntaxError:
        return arch, 0
    changed = 0
    for node in root.iter():
        for attribute in ('text', 'tail'):
            raw = getattr(node, attribute)
            if not raw:
                continue
            normalized = raw.strip()
            decoded = normalized
            while '&amp;' in decoded:
                decoded = html.unescape(decoded)
            role_node = node if attribute == 'text' else node.getparent()
            role_classes = role_node.get('class', '') if role_node is not None else ''
            replacement = TEACHER_NAMES.get(decoded)
            if website_language == 'id_ID':
                if decoded == 'Pengajar Mandarin & Bahasa Inggris':
                    replacement = (
                        'Guru Mandarin & Inggris' if 'text-muted' in role_classes
                        else 'Pengajar Bahasa Mandarin & Inggris'
                    )
                elif decoded == 'Pengajar Mandarin':
                    replacement = 'Guru Mandarin'
                elif decoded == 'Pengajar Bahasa Inggris':
                    replacement = 'Guru Inggris'
            else:
                replacement = replacement or {
                    'Pengajar Anda': 'Your Teacher',
                    'Pengajar Mandarin & Bahasa Inggris': 'Mandarin & English Tutor',
                    'Mandarin Teacher & Bahasa Inggris': 'Mandarin & English Tutor',
                    'Pengajar Mandarin': 'Mandarin Tutor',
                    'Pengajar Bahasa Inggris': 'English Tutor',
                }.get(decoded)
            if decoded == 'Akademi Diligence':
                replacement = 'DILIGENCE ACADEMY'
            if replacement and replacement != decoded:
                leading = raw[:len(raw) - len(raw.lstrip())]
                trailing = raw[len(raw.rstrip()):]
                setattr(node, attribute, leading + replacement + trailing)
                changed += 1
    return etree.tostring(root, encoding='unicode'), changed


def _homepage_views(env, website):
    page = env['website.page'].search([
        ('website_id', '=', website.id), ('url', '=', '/'),
    ], order='id', limit=1)
    views = page.view_id if page and page.view_id else env['ir.ui.view'].browse()
    views |= env['ir.ui.view'].search([
        ('website_id', '=', website.id),
        ('key', 'in', [
            'diligence_learning.homepage_editable',
            'diligence_learning.homepage_editable.website2',
        ]),
        ('active', '=', True),
    ])
    return views


def _translations_for_view(view, source_lang, translations_by_lang):
    localized = view.with_context(lang=source_lang)
    arch = localized.arch_db or ''
    terms = []
    xml_translate(lambda term: terms.append(term) or term, arch)
    translations = {}
    for language, mapping in translations_by_lang.items():
        translated_terms = {}
        for term in terms:
            translated = term
            for source in sorted(mapping, key=len, reverse=True):
                target = mapping[source]
                candidates = (html.escape(source, quote=False), source)
                for candidate in candidates:
                    if candidate in translated:
                        translated = translated.replace(
                            candidate, html.escape(target, quote=False),
                        )
            if translated != term:
                translated_terms[term] = translated
        if translated_terms:
            translations[language] = translated_terms
    translations = {language: mapping for language, mapping in translations.items() if mapping}
    if translations:
        localized.with_context(no_cow=True).update_field_translations(
            'arch_db', translations, source_lang=source_lang,
        )


def _update_footer(env, website):
    footer = env['ir.ui.view'].search([
        ('key', '=', 'website.footer_custom'),
        ('website_id', '=', website.id),
        ('active', '=', True),
    ], limit=1)
    if footer:
        arch = footer.arch_db or ''
        updated = arch.replace('Akademi Diligence', 'DILIGENCE ACADEMY')
        marker = 'href="https://web.facebook.com/diligenceenglishcourse"'
        if 'diligenceenglishcourse/?hl=en' not in updated and marker in updated:
            close = updated.find('</li>', updated.find(marker))
            if close >= 0:
                close += len('</li>')
                instagram = (
                    '<li><i class="fa fa-instagram fa-fw me-2"></i>'
                    '<a style="color:#f5f7f8 !important;" '
                    'href="https://www.instagram.com/diligenceenglishcourse/?hl=en" '
                    'target="_blank" rel="noopener noreferrer">Instagram</a></li>'
                )
                updated = updated[:close] + instagram + updated[close:]
        if updated != arch:
            footer.with_context(no_cow=True).write({'arch_db': updated})
    website.write({
        'social_instagram': 'https://www.instagram.com/diligenceenglishcourse/?hl=en',
    })


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    websites = env['website'].search([
        ('domain', 'ilike', 'diligenceenglish.com'),
    ]) | env['website'].search([
        ('domain', 'ilike', 'diligencekursusbahasa.com'),
    ])
    for website in websites:
        source_lang = website.default_lang_id.code or 'en_US'
        is_indonesian_source = source_lang == 'id_ID'
        views = _homepage_views(env, website)
        for view in views:
            localized = view.with_context(lang=source_lang)
            arch = localized.arch_db or ''
            updated, names_changed = _replace_teacher_terms(arch, source_lang)
            if updated != arch:
                localized.with_context(
                    no_cow=True,
                    diligence_website_syncing=True,
                    _diligence_syncing_website_view=True,
                ).write({'arch_db': updated})
            if is_indonesian_source:
                _translations_for_view(view, source_lang, {
                    'en_US': ID_TO_EN,
                    'zh_CN': ID_TO_ZH,
                })
                # The Indonesian source itself uses the academy's permanent
                # brand and teacher copy specified by the client.
            else:
                # This site's stored homepage is English; provide Indonesian
                # and Chinese translations for the language selector.
                english_to_id = {english: indonesian for indonesian, english in ID_TO_EN.items()}
                english_to_id.update({
                    'Unlock more opportunities with language skills.': 'Buka lebih banyak peluang dengan kemampuan bahasa.',
                    'Your Teacher': 'Pengajar Anda',
                    'Mandarin & English Tutor': 'Pengajar Bahasa Mandarin & Inggris',
                })
                english_to_zh = {english: chinese for indonesian, english in ID_TO_EN.items()
                                 for chinese in [ID_TO_ZH.get(indonesian)] if chinese}
                english_to_zh.update({
                    'Unlock more opportunities with language skills.': '掌握语言，开启更多机遇。',
                    'Your Teacher': '您的导师',
                    'Mandarin & English Tutor': '中文与英文导师',
                })
                _translations_for_view(view, source_lang, {
                    'id_ID': english_to_id,
                    'zh_CN': english_to_zh,
                })
            _logger.info(
                'Localized Diligence homepage view %s for %s (%s teacher/brand edits)',
                view.id, website.domain, names_changed,
            )
        _update_footer(env, website)

