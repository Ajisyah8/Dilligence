from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase


class TestDiligenceSeoManager(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.seo_model = cls.env['diligence.seo.item']
        existing_page_ids = cls.seo_model.search([
            ('res_model', '=', 'website.page'),
        ]).mapped('res_id')
        cls.page = cls.env['website.page'].search([
            ('id', 'not in', existing_page_ids),
        ], limit=1)

    def test_create_and_sync_website_page(self):
        self.assertTrue(self.page)
        item = self.seo_model.create({
            'content_type': 'website.page',
            'res_model': 'website.page',
            'res_id': self.page.id,
            'seo_title': 'Diligence Academy SEO Title Example',
            'seo_description': 'A useful description for the Diligence Academy website page.',
            'seo_keywords': 'Diligence Academy, Mandarin course',
            'is_indexed': False,
        })
        self.assertEqual(self.page.website_meta_title, item.seo_title)
        self.assertEqual(self.page.website_meta_description, item.seo_description)
        if 'website_meta_keywords' in self.page._fields:
            self.assertEqual(self.page.website_meta_keywords, item.seo_keywords)
        self.assertFalse(item.is_indexed)

    def test_seo_item_is_scoped_to_website_and_domain(self):
        website = self.env['website'].search([], limit=1)
        previous_domain = website.domain
        website.domain = 'https://seo-local.example'
        try:
            item = self.seo_model.create({
                'content_type': 'website.page',
                'res_model': 'website.page',
                'res_id': self.page.id,
                'is_indexed': False,
            })
            self.assertEqual(item.website_id, website)
            self.assertEqual(item.domain, 'https://seo-local.example')
            self.assertTrue(item.canonical_url.startswith('https://seo-local.example/'))
        finally:
            website.domain = previous_domain

    def test_generate_defaults_fills_empty_keywords_without_overwriting_custom_keywords(self):
        item = self.seo_model.create({
            'content_type': 'website.page',
            'res_model': 'website.page',
            'res_id': self.page.id,
            'seo_keywords': False,
            'is_indexed': False,
        })
        item.action_generate_defaults()
        self.assertTrue(item.seo_keywords)
        item.write({'seo_keywords': 'Custom keyword set'})
        item.action_generate_defaults()
        self.assertEqual(item.seo_keywords, 'Custom keyword set')

    def test_content_keyword_generator_uses_description(self):
        product = self.env['product.template'].create({
            'name': 'Mandarin Course SEO Test',
            'list_price': 100000,
            'description_sale': 'Structured Mandarin speaking practice for university preparation.',
        })
        item = self.seo_model.create({
            'content_type': 'product.template',
            'res_model': 'product.template',
            'res_id': product.id,
            'seo_keywords': False,
            'is_indexed': False,
        })
        item.action_generate_content_keywords()
        self.assertIn('Mandarin', item.seo_keywords)
        self.assertIn('speaking', item.seo_keywords)
        self.assertEqual(item.keyword_source, 'generated')
        self.assertTrue(item.keywords_generated_at)

        item.write({'seo_keywords': 'Custom keyword set'})
        item.action_generate_content_keywords()
        self.assertEqual(item.seo_keywords, 'Custom keyword set')

    def test_duplicate_target_and_url_are_rejected(self):
        item = self.seo_model.create({
            'content_type': 'website.page',
            'res_model': 'website.page',
            'res_id': self.page.id,
            'url': '/seo-manager-test',
        })
        with self.assertRaises(Exception):
            self.seo_model.create({
                'content_type': 'website.page',
                'res_model': 'website.page',
                'res_id': self.page.id,
            })
        other_page = self.env['website.page'].search([('id', '!=', self.page.id)], limit=1)
        if other_page:
            with self.assertRaises(ValidationError):
                self.seo_model.create({
                    'content_type': 'website.page',
                    'res_model': 'website.page',
                    'res_id': other_page.id,
                    'url': item.url,
                })

    def test_indexing_unpublished_content_is_rejected(self):
        item = self.seo_model.create({
            'content_type': 'website.page',
            'res_model': 'website.page',
            'res_id': self.page.id,
            'is_indexed': False,
        })
        item.write({'is_published': False})
        with self.assertRaises(UserError):
            item.write({'is_indexed': True})

    def test_editor_has_read_write_but_not_manager_permissions(self):
        editor = self.env['res.users'].create({
            'name': 'SEO Editor Test',
            'login': 'seo-editor-test@example.com',
            'group_ids': [(6, 0, [self.env.ref('website.group_website_designer').id])],
        })
        self.seo_model.with_user(editor).check_access('write')
        with self.assertRaises(AccessError):
            self.seo_model.with_user(editor).check_access('create')

    def test_internal_search_terms_are_aggregated_without_identity(self):
        terms = self.env['diligence.seo.search.term']
        first = terms.record_query('  Kursus   Mandarin  ')
        second = terms.record_query('kursus mandarin', result_count=3)
        self.assertEqual(first, second)
        self.assertEqual(second.name, 'Kursus Mandarin')
        self.assertEqual(second.search_count, 2)
        self.assertEqual(second.result_count, 3)
        self.assertNotIn('email', second._fields)
        self.assertNotIn('ip', second._fields)

    def test_relevant_search_keywords_can_be_applied_without_overwriting_custom(self):
        self.env['diligence.seo.search.term'].record_query('kursus Mandarin online')
        product = self.env['product.template'].create({
            'name': 'Kursus Mandarin Online',
            'list_price': 100000,
            'description_sale': 'Program belajar Mandarin online untuk pemula.',
        })
        item = self.seo_model.create({
            'content_type': 'product.template',
            'res_model': 'product.template',
            'res_id': product.id,
            'seo_keywords': 'keyword manual',
            'is_indexed': False,
        })
        self.assertIn('kursus Mandarin online', item.search_keyword_suggestions)
        item.action_apply_search_keyword_suggestions()
        self.assertIn('keyword manual', item.seo_keywords)
        self.assertIn('kursus Mandarin online', item.seo_keywords)
