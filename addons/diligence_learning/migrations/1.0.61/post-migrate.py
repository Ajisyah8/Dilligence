from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    view = env.ref('website.footer_copyright_company_name', raise_if_not_found=False)
    if not view:
        return

    # Keep the permanent brand identical in every website language. Update
    # translated versions only; the company record itself is not modified.
    for language, replacements in {
        'en_US': (
            ('Copyright &copy; Diligence Academy', 'Copyright © DILIGENCE ACADEMY'),
            ('Copyright © Diligence Academy', 'Copyright © DILIGENCE ACADEMY'),
        ),
        'id_ID': (
            ('Hak Cipta © Akademi Diligence', 'Hak Cipta © DILIGENCE ACADEMY'),
            ('Hak Cipta © Diligence Academy', 'Hak Cipta © DILIGENCE ACADEMY'),
        ),
        'zh_CN': (
            ('Diligence Academy', 'DILIGENCE ACADEMY'),
            ('Akademi Diligence', 'DILIGENCE ACADEMY'),
        ),
    }.items():
        localized = view.with_context(lang=language, no_cow=True)
        arch = localized.arch_db or ''
        updated = arch
        for old, new in replacements:
            updated = updated.replace(old, new)
        if updated != arch:
            localized.write({'arch_db': updated})
