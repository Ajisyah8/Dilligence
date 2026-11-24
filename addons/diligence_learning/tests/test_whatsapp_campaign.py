from odoo.tests.common import TransactionCase


class TestDiligenceWhatsAppCampaign(TransactionCase):

    def test_send_batch_only_selects_never_attempted_lines(self):
        campaign = self.env['diligence.whatsapp.campaign'].create({
            'name': 'WhatsApp batch selection test',
            'message_template': 'Hello %(name)s',
        })
        line_model = self.env['diligence.whatsapp.campaign.line']
        sent_line = line_model.create({
            'campaign_id': campaign.id,
            'phone': '628111111111',
            'message': 'Already sent',
            'state': 'sent',
        })
        error_line = line_model.create({
            'campaign_id': campaign.id,
            'phone': '628222222222',
            'message': 'Needs review',
            'state': 'error',
        })
        pending_line = line_model.create({
            'campaign_id': campaign.id,
            'phone': '628333333333',
            'message': 'Not yet attempted',
            'state': 'pending',
        })

        batch = self.env['diligence.whatsapp.campaign']._get_pending_delivery_batch(
            campaign.id,
            10,
        )

        self.assertEqual(batch.ids, [pending_line.id])
        self.assertNotIn(sent_line, batch)
        self.assertNotIn(error_line, batch)
