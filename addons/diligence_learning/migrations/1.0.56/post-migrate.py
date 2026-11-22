import logging

from odoo import SUPERUSER_ID, api


_logger = logging.getLogger(__name__)


ENGLISH_HOMEPAGE_COPY = {
    'Apa yang Baru?': "What's New",
    'Apa yang Baru di DILIGENCE ACADEMY ?': "What's New at DILIGENCE ACADEMY?",
    'Program baru untuk mendukung perjalanan belajar dan rencana masa depan Anda.':
        'New programs to support your learning journey and future plans.',
    'Kelas Mandarin Online Terstruktur': 'Structured Online Mandarin Classes',
    'Belajar Mandarin dengan alur yang jelas, fleksibel, dan bisa diikuti sesuai ritme Anda.':
        'Learn Mandarin through a clear, flexible path at your own pace.',
    'Lihat Program': 'Explore Programs',
    'Lihat Kursus': 'View Courses',
    'Jalur Beasiswa Kuliah ke China': 'Study in China Scholarship Pathway',
    'Kenali peluang studi ke China dan persiapkan langkah Anda bersama tim Diligence.':
        'Explore study opportunities in China and plan your next steps with the Diligence team.',
    'Lihat testimoni siswa beasiswa': 'Read scholarship student stories',
    'Baca cerita siswa': 'Read student stories',
    'Ujian Sertifikasi Bahasa Inggris Cambridge': 'Cambridge English Qualifications',
    'Persiapkan kemampuan bahasa Anda dengan target sertifikasi yang jelas dan terukur.':
        'Build your language skills with clear, measurable certification goals.',
    'Lihat jadwal ujian Cambridge': 'View Cambridge exam dates',
    'Lihat jadwal ujian': 'View exam dates',
    'Program Kami': 'Our Programs',
    'Program belajar yang tersedia': 'Available learning programs',
    'Pilih program English atau Mandarin sesuai kebutuhan Anda.':
        'Choose an English or Mandarin program to suit your needs.',
    'Kursus Bahasa Mandarin': 'Mandarin Courses',
    'Pelajari pelafalan, nada, kosakata dasar, dan percakapan Mandarin secara bertahap.':
        'Learn pronunciation, tones, essential vocabulary, and Mandarin conversation step by step.',
    'Lihat Kursus Mandarin': 'Explore Mandarin Courses',
    'Kursus Bahasa Inggris': 'English Courses',
    'Bangun kepercayaan diri, kelancaran percakapan, dan kemampuan bahasa untuk kebutuhan sehari-hari maupun profesional.':
        'Build confidence, conversational fluency, and language skills for everyday and professional use.',
    'Lihat Kursus Bahasa Inggris': 'Explore English Courses',
    'Program Bahasa Inggris': 'English Programs',
    'Tingkatkan Bahasa Inggrismu secara natural': 'Improve Your English Naturally',
    'Pelajari bahasa Inggris dengan konsep belajar yang praktis dan menyenangkan.':
        'Learn English through a practical and enjoyable approach.',
    'Berbicara lebih percaya diri': 'Speak with more confidence',
    'Menunjang karier': 'Support your career',
    'Materi praktis': 'Practical learning materials',
    'Alur belajar terstruktur': 'A structured learning path',
    'Jadwalkan Wawancara Gratis': 'Schedule a Free Interview',
    'Paket Belajar': 'Learning Packages',
    'Pilih Paket Belajar Anda': 'Choose Your Learning Package',
    'Pilih paket belajar sesuai kebutuhan Anda dengan benefit lengkap, harga transparan, dan penawaran Early Bird.':
        'Choose a package that fits your needs, with clear benefits, transparent pricing, and an Early Bird offer.',
    'Belum yakin memilih program?': 'Not sure which program to choose?',
    'Konsultasikan kebutuhan belajar Anda secara gratis bersama tim Diligence.':
        'Talk with the Diligence team for a free consultation about your learning goals.',
    'Dapatkan materi belajar terbaru': 'Get the Latest Learning Resources',
    'Daftarkan email Anda untuk menerima tips belajar, materi pilihan, dan informasi program terbaru dari DILIGENCE ACADEMY.':
        'Subscribe to receive study tips, selected learning resources, and the latest DILIGENCE ACADEMY program updates.',
    'Langganan': 'Subscribe',
    'Cerita dari Siswa Kami': 'Student Stories',
    'Apa kata siswa tentang DILIGENCE ACADEMY?': 'What Do Students Say About DILIGENCE ACADEMY?',
    'Pengalaman belajar yang nyata dari siswa kami.': 'Real learning experiences from our students.',
    'Menulis saya telah meningkat setelah tiga bulan belajar. Saya pikir kursus Bahasa Inggris ini adalah keputusan terbaik yang pernah saya buat.':
        'My writing has improved after three months of learning. I think this English course was the best decision I have ever made.',
    'Laoshinya ramah, metode belajarnya bagus dan fleksibel untuk atur jadwal.':
        'The teacher is friendly, the teaching method is effective, and the schedule is flexible.',
    'Untuk pembelajaran cara menyampaikan materi lebih mudah untuk di pahami, lebih asik, dan bisa membawa suasana kelas menjadi lebih santai.':
        'The lessons are easy to understand and engaging, and the relaxed classroom atmosphere makes learning enjoyable.',
    'Miss Diana sangat tegas dan detail dalam mengajar, sehingga membantu saya sebagai beginner untuk belajar bahasa mandarin dari basic. Miss Diana juga selalu memberikan homework agar saya terus melatih penulisan huruf dan homework hapalan agar saya tetap on track dalam belajar bahasa mandarin.':
        'Miss Diana is disciplined and thorough, which has helped me learn Mandarin from the basics as a beginner. She also gives me writing and memorization homework so I can keep practicing and stay on track.',
    'Cara mengajar miss sangat detail, dan penjelasannya mudah di pahami. Dan Miss selalu memastikan apakah kita mengerti materi atau tidak.':
        'The teacher explains everything in detail and makes it easy to understand. She always checks that we understand the material.',
    'Seru ya, laoshi sering memotivasi kami gitu, serius tapi santai. Pokoknya ruang kelas jadi nyaman, proses pembelajaran jadi nyaman.':
        'It is fun! Our teacher often motivates us. The class is focused but relaxed, and the learning environment feels comfortable.',
    'Sebelumnya': 'Previous',
    'Berikutnya': 'Next',
    'Kenali Pengajar Kami': 'Meet Our Teachers',
    'Belajar bersama pengajar berpengalaman': 'Learn with experienced teachers',
    'Kenali tim pengajar Diligence Academy.': 'Meet the Diligence Academy teaching team.',
    'Pengajar Mandarin & Bahasa Inggris': 'Mandarin & English Teacher',
    'Pengajar Mandarin': 'Mandarin Teacher',
    'Pengajar Bahasa Inggris': 'English Teacher',
    'Karier': 'Careers',
    'Bergabung dengan tim': 'Join Our Team',
    'Kami terbuka untuk pengajar dan talenta yang ingin ikut mengembangkan pendidikan.':
        'We welcome teachers and talented people who want to help shape the future of education.',
    'Lihat Kesempatan': 'Explore Opportunities',
}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    english_website = env['website'].search([
        ('domain', 'ilike', 'diligenceenglish.com'),
    ], limit=1)
    if not english_website:
        _logger.warning('English homepage translation skipped: website not found')
        return

    homepage = env['website.page'].search([
        ('website_id', '=', english_website.id),
        ('url', '=', '/'),
    ], order='id', limit=1)
    view = homepage.view_id if homepage else env['ir.ui.view'].browse()
    if not view:
        _logger.warning('English homepage translation skipped: homepage view not found')
        return

    language = english_website.default_lang_id.code or 'en_US'
    localized_view = view.with_context(lang=language)
    arch = localized_view.arch_db or ''
    updated_arch = arch
    translated_count = 0
    for source in sorted(ENGLISH_HOMEPAGE_COPY, key=len, reverse=True):
        target = ENGLISH_HOMEPAGE_COPY[source]
        if source in updated_arch:
            updated_arch = updated_arch.replace(source, target)
            translated_count += 1

    if updated_arch != arch:
        localized_view.with_context(
            lang=language,
            diligence_website_syncing=True,
            no_cow=True,
        ).write({'arch_db': updated_arch})
    _logger.info(
        'Restored English homepage copy in view %s (%s replacements)',
        view.id, translated_count,
    )
