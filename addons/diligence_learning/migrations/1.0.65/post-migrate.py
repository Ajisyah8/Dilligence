from odoo import SUPERUSER_ID, api


WEBINAR_DESCRIPTION_ID = '''<section class="s_text_block o_colored_level"><div class="container"><h2>Mulai Perjalanan Mandarin Anda dari Nol</h2><p>Belum pernah belajar Mandarin? Webinar ini dirancang untuk pemula. Kenali dasar-dasarnya dengan cara yang santai, praktis, dan mudah diikuti.</p><h3>Apa yang akan Anda dapatkan?</h3><ul><li>Memahami konsep belajar bahasa.</li><li>Mendapat tips memulai latihan Mandarin secara konsisten.</li></ul><h3>Webinar ini cocok untuk</h3><p>Pemula yang belum pernah belajar Mandarin maupun yang ingin mengulang dasar pelafalan dan percakapan.</p><h3>Susunan acara</h3><ul><li>Perkenalan.</li><li>Pengenalan benefit dan hambatan siswa pada umumnya dalam belajar Mandarin.</li><li>Kupas tuntas konsep belajar bahasa.</li><li>Pengenalan dasar pembelajaran bahasa Mandarin.</li><li>Tanya jawab bersama pengajar.</li></ul><p><strong>Jadwal:</strong> Minggu, 22 November 2026, pukul 19.00–20.30 WIB.</p><p>Silakan isi formulir pendaftaran dengan data yang benar. Tautan Zoom akan dikirim ke email yang didaftarkan.</p></div></section>'''

ZOOM_EMAIL_BLOCKS = {
    'en_US': '''<t t-if="object.event_id.event_url"><div data-diligence-zoom-join-link="1" style="margin: 24px 0; padding: 16px; border: 1px solid #d8e3e8; border-radius: 8px;"><p><strong>Join the online session</strong></p><p><a t-att-href="object.event_id.event_url" style="display: inline-block; padding: 10px 16px; color: #ffffff; background-color: #11687d; text-decoration: none; border-radius: 5px;">Join Zoom meeting</a></p></div></t>''',
    'id_ID': '''<t t-if="object.event_id.event_url"><div data-diligence-zoom-join-link="1" style="margin: 24px 0; padding: 16px; border: 1px solid #d8e3e8; border-radius: 8px;"><p><strong>Gabung sesi online</strong></p><p><a t-att-href="object.event_id.event_url" style="display: inline-block; padding: 10px 16px; color: #ffffff; background-color: #11687d; text-decoration: none; border-radius: 5px;">Gabung meeting Zoom</a></p></div></t>''',
    'zh_CN': '''<t t-if="object.event_id.event_url"><div data-diligence-zoom-join-link="1" style="margin: 24px 0; padding: 16px; border: 1px solid #d8e3e8; border-radius: 8px;"><p><strong>加入线上讲座</strong></p><p><a t-att-href="object.event_id.event_url" style="display: inline-block; padding: 10px 16px; color: #ffffff; background-color: #11687d; text-decoration: none; border-radius: 5px;">加入 Zoom 会议</a></p></div></t>''',
}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    event = env['event.event'].sudo().browse(3).exists()
    if event:
        event.with_context(lang='id_ID').write({'description': WEBINAR_DESCRIPTION_ID})

    template = env.ref('event.event_subscription', raise_if_not_found=False)
    if not template:
        return
    for language_code, block in ZOOM_EMAIL_BLOCKS.items():
        current_body = template.with_context(lang=language_code).body_html or ''
        if 'data-diligence-zoom-join-link' not in current_body:
            template.with_context(lang=language_code).write({
                'body_html': current_body + block,
            })
