{
    'name': 'Payment Provider: Static QRIS',
    'version': '1.0.0',
    'category': 'Accounting/Payment Providers',
    'summary': 'Static QRIS payment with automatic confirmation after proof upload',
    'depends': ['payment_custom', 'website_sale_slides'],
    'data': [
        'views/payment_provider_views.xml',
        'views/payment_qris_templates.xml',
        'data/payment_provider_data.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'license': 'LGPL-3',
    'author': 'Project ADS',
}
