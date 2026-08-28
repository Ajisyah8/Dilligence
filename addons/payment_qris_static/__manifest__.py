{
    'name': 'Payment Provider: Static QRIS',
    'version': '1.0.0',
    'category': 'Accounting/Payment Providers',
    'summary': 'Static QRIS payment with Finance verification of payment proof',
    'depends': ['payment_custom', 'website_sale_slides'],
    'data': [
        'views/payment_provider_views.xml',
        'views/payment_qris_templates.xml',
        'views/payment_transaction_views.xml',
        'views/payment_reject_wizard.xml',
        'security/ir.model.access.csv',
        'data/payment_provider_data.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'license': 'LGPL-3',
    'author': 'Project ADS',
}
