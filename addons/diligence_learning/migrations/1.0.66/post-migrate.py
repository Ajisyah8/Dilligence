from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    # The Indonesian translation of the event CTA was mistakenly imported as
    # "Registrasi rawat inap". Correct the website event navbar only.
    navbar = env.ref('website_event.navbar', raise_if_not_found=False)
    if navbar:
        navbar_id = navbar.with_context(lang='id_ID')
        arch = navbar_id.arch_db or ''
        if 'Registrasi rawat inap' in arch:
            navbar_id.write({'arch_db': arch.replace('Registrasi rawat inap', 'Daftar')})

    # The gender selection question had the Indonesian title "Email", while
    # its answers were still Perempuan/Laki Laki. Correct its translated title.
    event = env['event.event'].with_context(lang='id_ID').search([
        ('name', '=', 'Webinar Belajar Mandarin dari Nol'),
    ], limit=1)
    if event:
        gender_question = event.question_ids.with_context(lang='en_US').filtered(
            lambda question: question.title == 'Jenis Kelamin'
        )
        if len(gender_question) == 1:
            gender_question.with_context(lang='id_ID').write({'title': 'Jenis Kelamin'})
