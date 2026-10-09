{
    'name': 'Diligence COA Structure',
    'version': '1.0.4',
    'summary': 'Expandable 100–500 account groups for Diligence Academy',
    'category': 'Accounting/Accounting',
    'author': 'Project ADS',
    'license': 'LGPL-3',
    'depends': ['account'],
    'data': [
        'data/coa_account_groups.xml',
        'views/account_group_subaccounts.xml',
        'views/account_coa_groupby.xml',
        'views/account_coa_inline_create.xml',
        'views/account_coa_hide_legacy_manage.xml',
    ],
    'application': False,
    'installable': True,
}
