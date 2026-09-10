from odoo import Command, fields


env = env
company = env.company
qris_provider = env['payment.provider'].search([
    ('code', '=', 'custom'),
    ('custom_mode', '=', 'qris_static'),
    ('company_id', '=', company.id),
], limit=1)
if not qris_provider:
    raise RuntimeError('No local QRIS static provider is configured.')
payment_method = qris_provider.payment_method_ids[:1]
if not payment_method:
    raise RuntimeError('The local QRIS provider has no payment method.')

student = env['res.partner'].search([
    ('email', '=', 'e2e-student-unpaid-20260910@example.test'),
], limit=1)
if not student:
    student = env['res.partner'].create({
        'name': 'E2E Student - Unpaid QRIS',
        'email': 'e2e-student-unpaid-20260910@example.test',
        'phone': '6281110002026',
        'company_id': company.id,
    })

product = env['product.product'].search([
    ('product_tmpl_id.diligence_package_type_id', '!=', False),
    ('sale_ok', '=', True),
], limit=1)
if not product:
    product = env['product.product'].create({
        'name': 'E2E Local Pending Package',
        'type': 'service',
        'list_price': 129000,
        'sale_ok': True,
    })

reference = 'E2E QRIS Pending 20260910'
tx = env['payment.transaction'].search([
    ('reference', '=', reference),
    ('partner_id', '=', student.id),
], limit=1)
if tx:
    order = tx.sale_order_ids[:1]
else:
    order = env['sale.order'].create({
        'partner_id': student.id,
        'company_id': company.id,
        'order_line': [Command.create({
            'product_id': product.id,
            'product_uom_qty': 1,
            'price_unit': product.lst_price,
        })],
    })
    tx = env['payment.transaction'].create({
        'provider_id': qris_provider.id,
        'payment_method_id': payment_method.id,
        'amount': order.amount_total,
        'currency_id': order.currency_id.id,
        'partner_id': student.id,
        'reference': reference,
        'operation': 'online_direct',
        'sale_order_ids': [Command.set([order.id])],
    })
    tx._set_pending(state_message='E2E local payment awaiting verification.')

officer_group = env.ref('diligence_learning.group_diligence_invoice_officer')
officer = env['res.users'].search([
    ('login', '=', 'e2e-invoice-officer-local-20260910'),
], limit=1)
if not officer:
    officer = env['res.users'].create({
        'name': 'E2E Invoice Officer Local',
        'login': 'e2e-invoice-officer-local-20260910',
        'email': 'e2e-invoice-officer-local@example.test',
        'group_ids': [Command.set([
            env.ref('base.group_user').id,
            officer_group.id,
        ])],
    })

pending_visible = env['payment.transaction'].with_user(officer).search([
    ('id', '=', tx.id),
])
unpaid_invoices = env['account.move'].with_user(officer).search([
    ('move_type', '=', 'out_invoice'),
])
assert pending_visible == tx, 'Invoice Officer cannot see the pending transaction.'
assert not order.invoice_ids, 'Pending transaction must not create an invoice.'
assert not unpaid_invoices.filtered(lambda invoice: invoice.id in order.invoice_ids.ids)

print('E2E_PENDING_TX_ID=%s' % tx.id)
print('E2E_ORDER_ID=%s' % order.id)
print('E2E_STUDENT_ID=%s' % student.id)
print('E2E_INVOICE_OFFICER_ID=%s' % officer.id)
print('E2E_TX_STATE=%s' % tx.state)
print('E2E_ORDER_TOTAL=%s' % order.amount_total)
print('E2E_INVOICE_COUNT=%s' % len(order.invoice_ids))
env.cr.commit()

# Persist representative fixtures for the non-checkout features. Every record
# uses an explicit E2E marker and is looked up before creation.
newsletter = env['mailing.list'].search([
    ('name', '=', 'Diligence Academy Newsletter'),
], limit=1)
newsletter_contact = env['mailing.contact'].search([
    ('email', '=', 'e2e-newsletter-20260910@example.test'),
], limit=1)
if newsletter and not newsletter_contact:
    newsletter_contact = env['mailing.contact'].create({
        'name': 'E2E Newsletter Subscriber',
        'email': 'e2e-newsletter-20260910@example.test',
    })
if newsletter and newsletter_contact:
    subscription = env['mailing.subscription'].search([
        ('contact_id', '=', newsletter_contact.id),
        ('list_id', '=', newsletter.id),
    ], limit=1)
    if not subscription:
        env['mailing.subscription'].create({
            'contact_id': newsletter_contact.id,
            'list_id': newsletter.id,
            'opt_out': False,
        })
    env['diligence.newsletter.delivery']._ensure_deliveries()

page = env['website.page'].search([('url', '=', '/about-us')], limit=1)
seo_item = env['diligence.seo.item'].search([
    ('res_model', '=', 'website.page'), ('res_id', '=', page.id),
], limit=1) if page else env['diligence.seo.item']
if page and not seo_item:
    seo_item = env['diligence.seo.item'].create({
        'content_type': 'website.page',
        'res_model': 'website.page',
        'res_id': page.id,
        'url': page.url,
        'seo_title': 'E2E Diligence Academy About Us',
        'seo_description': 'E2E SEO fixture for the Diligence Academy About Us page.',
        'seo_keywords': 'Diligence Academy, E2E SEO',
        'is_indexed': False,
    })

segment = env['diligence.contact.segment'].search([
    ('code', '=', 'e2e_test_segment'),
], limit=1)
if not segment:
    segment = env['diligence.contact.segment'].create({
        'name': 'E2E Test Students',
        'code': 'e2e_test_segment',
    })

survey = env['survey.survey'].search([
    ('title', '=', 'E2E Placement Test'),
], limit=1)
if not survey:
    survey = env['survey.survey'].create({
        'title': 'E2E Placement Test',
        'diligence_is_placement_test': True,
    })
level = env['diligence.placement.level'].search([
    ('survey_id', '=', survey.id), ('name', '=', 'E2E Beginner'),
], limit=1)
if not level:
    level = env['diligence.placement.level'].create({
        'name': 'E2E Beginner',
        'survey_id': survey.id,
        'min_score': 0,
        'max_score': 49.99,
        'recommendation': 'E2E placement recommendation.',
    })

affiliate = env['res.partner'].search([
    ('email', '=', 'e2e-affiliate-20260910@example.test'),
], limit=1)
if not affiliate:
    affiliate = env['res.partner'].create({
        'name': 'E2E Affiliate',
        'email': 'e2e-affiliate-20260910@example.test',
        'diligence_is_affiliate': True,
        'diligence_referral_code': 'E2E20260910',
    })
referral = env['diligence.referral'].search([
    ('referral_code', '=', 'E2E20260910'),
    ('student_id', '=', student.id),
], limit=1)
if not referral:
    referral = env['diligence.referral'].create({
        'affiliate_id': affiliate.id,
        'student_id': student.id,
        'sale_order_id': order.id,
        'program_id': product.product_tmpl_id.id,
        'referral_code': 'E2E20260910',
        'status': 'pending_payment',
    })

env.cr.commit()
print('E2E_NEWSLETTER_DELIVERIES=%s' % env['diligence.newsletter.delivery'].search_count([
    ('mailing_contact_id', '=', newsletter_contact.id if newsletter_contact else 0),
]))
print('E2E_SEO_ITEM_ID=%s' % (seo_item.id if seo_item else 0))
print('E2E_SEGMENT_ID=%s' % segment.id)
print('E2E_PLACEMENT_SURVEY_ID=%s' % survey.id)
print('E2E_PLACEMENT_LEVEL_ID=%s' % level.id)
print('E2E_REFERRAL_ID=%s' % referral.id)
