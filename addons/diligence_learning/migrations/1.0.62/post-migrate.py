import json

from odoo import SUPERUSER_ID, api


DESCRIPTIONS = {
    'id_ID': '<section class="s_text_block o_colored_level"><div class="container"><h2>Mulai Perjalanan Mandarin Anda dari Nol</h2><p>Belum pernah belajar Mandarin? Webinar ini dirancang untuk pemula. Kenali dasar-dasarnya dengan cara yang santai, praktis, dan mudah diikuti.</p><h3>Apa yang akan dipelajari?</h3><ul><li>Mengenal Pinyin dan cara membaca bunyi Mandarin.</li><li>Memahami empat nada dan nada netral melalui contoh sederhana.</li><li>Berlatih salam serta perkenalan singkat.</li><li>Mendapat tips memulai latihan Mandarin secara konsisten.</li></ul><h3>Webinar ini cocok untuk</h3><p>Pemula yang belum pernah belajar Mandarin maupun yang ingin mengulang dasar pelafalan dan percakapan.</p><h3>Susunan acara</h3><ul><li>Pengenalan dasar Mandarin dan Pinyin.</li><li>Praktik nada dan ungkapan sehari-hari.</li><li>Tanya jawab bersama pengajar.</li></ul><p><strong>Jadwal:</strong> Minggu, 22 November 2026, pukul 19.00–20.30 WIB.</p><p>Silakan isi formulir pendaftaran dengan data yang benar. Tautan Zoom akan dikirim ke email yang didaftarkan.</p></div></section>',
    'en_US': '<section class="s_text_block o_colored_level"><div class="container"><h2>Start Your Mandarin Journey from Zero</h2><p>Never studied Mandarin before? This webinar is designed for beginners. Explore the basics in a relaxed, practical, and easy-to-follow session.</p><h3>What you will learn</h3><ul><li>Meet Pinyin and learn how Mandarin sounds are written.</li><li>Understand the four tones and the neutral tone through simple examples.</li><li>Practice greetings and a short self-introduction.</li><li>Get practical tips for building a consistent Mandarin study habit.</li></ul><h3>Who should join?</h3><p>Complete beginners and learners who want to refresh pronunciation and basic conversation skills.</p><h3>Session plan</h3><ul><li>Introduction to Mandarin basics and Pinyin.</li><li>Tone and everyday-expression practice.</li><li>Live Q&amp;A with the teacher.</li></ul><p><strong>Schedule:</strong> Sunday, November 22, 2026, 7:00–8:30 PM WIB (UTC+7).</p><p>Please complete the registration form with accurate details. The Zoom link will be sent to the email address used to register.</p></div></section>',
    'zh_CN': '<section class="s_text_block o_colored_level"><div class="container"><h2>从零开启您的中文学习之旅</h2><p>从未学过中文？本次线上讲座专为初学者设计，以轻松、实用、易跟上的方式带您认识中文基础。</p><h3>您将学到什么？</h3><ul><li>认识拼音，了解中文发音的标记方式。</li><li>通过简单示例了解四声和轻声。</li><li>练习日常问候与简短自我介绍。</li><li>获得坚持练习中文的实用建议。</li></ul><h3>适合哪些人参加？</h3><p>适合零基础学习者，也适合希望复习发音和基础会话的学习者。</p><h3>活动安排</h3><ul><li>中文基础与拼音介绍。</li><li>声调和日常表达练习。</li><li>与老师现场问答。</li></ul><p><strong>时间：</strong>2026年11月22日（星期日）晚上7:00–8:30（印尼西部时间，UTC+7）。</p><p>请填写准确的报名信息。Zoom链接将发送至报名时填写的邮箱。</p></div></section>',
}

INTRO_VIEW = '''<t t-name="website_event.home-webinar-belajar-mandarin-dari-0">
    <t t-call="website_event.layout">
        <div class="oe_structure">
            <section class="s_text_block pt32 pb48">
                <div class="container">
                    <div class="row justify-content-center">
                        <div class="col-lg-9">
                            <p class="lead mb-4" t-field="event.subtitle"/>
                            <div t-field="event.description"/>
                        </div>
                    </div>
                </div>
            </section>
        </div>
    </t>
</t>'''


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    event = env['event.event'].with_context(lang='id_ID').search([
        ('name', '=', 'Webinar Belajar Mandarin dari Nol'),
    ], limit=1)
    if not event:
        return

    cr.execute(
        'UPDATE event_event SET description = %s::jsonb, write_date = now() WHERE id = %s',
        (json.dumps(DESCRIPTIONS, ensure_ascii=False), event.id),
    )
    event.invalidate_recordset(['description'])

    for menu in event.introduction_menu_ids:
        if menu.view_id:
            for language in ('en_US', 'id_ID', 'zh_CN'):
                menu.view_id.with_context(lang=language).write({'arch_db': INTRO_VIEW})
