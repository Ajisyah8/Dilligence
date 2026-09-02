from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase


class TestDiligenceSeoManager(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.page = cls.env['website.page'].search([], limit=1)
        cls.seo_model = cls.env['diligence.seo.item']

    def test_create_and_sync_website_page(self):
        self.assertTrue(self.page)
        item = self.seo_model.create({
            'content_type': 'website.page',
            'res_model': 'website.page',
            'res_id': self.page.id,
            'seo_title': 'Diligence Academy SEO Title Example',
            'seo_description': 'A useful description for the Diligence Academy website page.',
            'is_indexed': False,
        })
        self.assertEqual(self.page.website_meta_title, item.seo_title)
        self.assertEqual(self.page.website_meta_description, item.seo_description)
        self.assertFalse(item.is_indexed)

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
