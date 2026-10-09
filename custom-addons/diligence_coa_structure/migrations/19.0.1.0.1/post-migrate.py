def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    groups = env['account.group'].search([
        ('code_prefix_start', 'in', ['1', '2', '3', '4', '5']),
        ('company_id', '=', env.company.root_id.id),
    ])
    groups_by_prefix = {group.code_prefix_start: group for group in groups}
    accounts = env['account.account'].search([('code', '!=', False)])
    for account in accounts:
        group = groups_by_prefix.get(account.code[:1])
        if group:
            account.diligence_coa_group_id = group
