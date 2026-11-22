from unittest.mock import patch

from odoo.tests import TransactionCase


class TestDiligenceWebsiteSync(TransactionCase):

    def test_homepages_are_kept_localized_per_website(self):
        sync = self.env['diligence.website.sync']
        websites = self.env['website'].browse([1, 2]).exists()
        self.assertEqual(len(websites), 2)
        for website in websites:
            homepage = self.env['website.page'].search([
                ('website_id', '=', website.id),
                ('url', '=', '/'),
            ], limit=1)
            self.assertTrue(homepage)
            self.assertTrue(sync._is_diligence_homepage_view(homepage.view_id))
            # Homepage HTML is intentionally not mirrored across the English
            # and Indonesian domains.
            sync.sync_view(homepage.view_id, {'arch_db': '<t>localized</t>'})

    def test_cross_website_sync_error_does_not_rollback_view_save(self):
        view = self.env['ir.ui.view'].create({
            'name': 'Website sync save isolation test',
            'type': 'qweb',
            'arch_db': '<t><div>Before</div></t>',
            'website_id': self.env.ref('website.default_website').id,
        })
        sync_model = type(self.env['diligence.website.sync'])

        with patch.object(
            sync_model,
            'sync_view',
            autospec=True,
            side_effect=ValueError('can only parse strings'),
        ):
            view.write({'name': 'Website sync save isolation test - saved'})

        self.assertEqual(view.name, 'Website sync save isolation test - saved')
