from unittest.mock import patch

from odoo.tests.common import TransactionCase


class TestDiligencePackageRenewal(TransactionCase):

    def test_new_package_order_marks_same_package_as_renewed(self):
        student = self.env['res.partner'].create({'name': 'Renewal Test Student'})
        package = self.env['product.template'].create({
            'name': 'Renewal Test Package',
            'type': 'service',
            'sale_ok': True,
        })
        previous_order = self.env['sale.order'].create({
            'partner_id': student.id,
            'state': 'sale',
            'diligence_renewal_package_id': package.id,
            'diligence_renewal_status': 'continue',
        })
        renewal_order = self.env['sale.order'].create({
            'partner_id': student.id,
            'state': 'sale',
        })

        renewal_order._diligence_mark_previous_package_orders_renewed(package)

        self.assertEqual(previous_order.diligence_renewal_status, 'renewed')
        self.assertEqual(previous_order.diligence_renewed_by_order_id, renewal_order)

    def test_paid_opt_out_removes_student_from_whatsapp_group_immediately(self):
        student = self.env['res.partner'].create({
            'name': 'Renewal Test Student',
            'phone': '628123456789',
        })
        package = self.env['product.template'].create({
            'name': 'Renewal Test Package',
            'type': 'service',
            'sale_ok': True,
            'diligence_whatsapp_group_jid': '120363000000000000@g.us',
        })
        order = self.env['sale.order'].create({
            'partner_id': student.id,
            'state': 'sale',
            'diligence_renewal_package_id': package.id,
            'diligence_access_expires_at': '2099-01-01 00:00:00',
            'diligence_renewal_status': 'not_continue',
            'diligence_whatsapp_group_removal_state': 'pending',
        })
        service_class = type(self.env['diligence.whatsapp.service'])
        with patch.object(service_class, 'remove_group_participant', return_value={'removed': True}) as remove:
            with patch.object(type(order), '_diligence_has_valid_package_payment', autospec=True, return_value=True):
                order._diligence_remove_from_whatsapp_group()

        remove.assert_called_once_with(package.diligence_whatsapp_group_jid, student.phone)
        self.assertEqual(order.diligence_whatsapp_group_removal_state, 'removed')
        self.assertTrue(order.diligence_whatsapp_group_removed_at)

    def test_opt_out_uses_account_whatsapp_number_not_submitted_override(self):
        student = self.env['res.partner'].create({
            'name': 'Renewal Test Student',
            'phone': '628123456789',
        })
        package = self.env['product.template'].create({
            'name': 'Renewal Test Package',
            'type': 'service',
            'sale_ok': True,
            'diligence_whatsapp_group_jid': '120363000000000000@g.us',
        })
        order = self.env['sale.order'].create({
            'partner_id': student.id,
            'state': 'sale',
            'diligence_renewal_package_id': package.id,
            'diligence_access_expires_at': '2099-01-01 00:00:00',
            'diligence_renewal_whatsapp_phone': '628987654321',
            'diligence_renewal_status': 'not_continue',
            'diligence_whatsapp_group_removal_state': 'pending',
        })
        service_class = type(self.env['diligence.whatsapp.service'])
        with patch.object(service_class, 'remove_group_participant', return_value={'removed': True}) as remove:
            with patch.object(type(order), '_diligence_has_valid_package_payment', autospec=True, return_value=True):
                order._diligence_remove_from_whatsapp_group()

        remove.assert_called_once_with(package.diligence_whatsapp_group_jid, student.phone)

    def test_package_switch_joins_new_tier_group_without_leaving_old_group(self):
        student = self.env['res.partner'].create({
            'name': 'Package Switch Student',
            'phone': '628123456789',
        })
        community = self.env['product.template'].create({
            'name': 'Community Package',
            'type': 'service',
            'sale_ok': True,
            'diligence_whatsapp_group_jid': 'community@g.us',
        })
        coaching = self.env['product.template'].create({
            'name': 'Coaching Package',
            'type': 'service',
            'sale_ok': True,
            'diligence_whatsapp_group_jid': 'coaching@g.us',
        })
        previous = self.env['sale.order'].create({
            'partner_id': student.id,
            'state': 'sale',
            'diligence_renewal_package_id': community.id,
            'diligence_access_expires_at': '2099-01-01 00:00:00',
            'diligence_renewal_status': 'continue',
        })
        replacement = self.env['sale.order'].create({
            'partner_id': student.id,
            'state': 'sale',
            'diligence_package_switch_from_order_id': previous.id,
        })
        service_class = type(self.env['diligence.whatsapp.service'])
        with patch.object(service_class, 'add_group_participant', return_value={'added': True}) as add:
            with patch.object(service_class, 'remove_group_participant') as remove:
                replacement._diligence_reconcile_package_switch_groups(coaching)

        add.assert_called_once_with('coaching@g.us', student.phone)
        remove.assert_not_called()
        self.assertEqual(previous.diligence_renewal_status, 'renewed')

    def test_switch_to_group_free_package_removes_old_tier_group(self):
        student = self.env['res.partner'].create({
            'name': 'Starter Switch Student',
            'phone': '628123456789',
        })
        coaching = self.env['product.template'].create({
            'name': 'Coaching Package',
            'type': 'service',
            'sale_ok': True,
            'diligence_whatsapp_group_jid': 'coaching@g.us',
        })
        starter = self.env['product.template'].create({
            'name': 'Starter Package',
            'type': 'service',
            'sale_ok': True,
        })
        previous = self.env['sale.order'].create({
            'partner_id': student.id,
            'state': 'sale',
            'diligence_renewal_package_id': coaching.id,
            'diligence_access_expires_at': '2099-01-01 00:00:00',
            'diligence_renewal_status': 'continue',
        })
        replacement = self.env['sale.order'].create({
            'partner_id': student.id,
            'state': 'sale',
            'diligence_package_switch_from_order_id': previous.id,
        })
        service_class = type(self.env['diligence.whatsapp.service'])
        with patch.object(service_class, 'remove_group_participant', return_value={'removed': True}) as remove:
            replacement._diligence_reconcile_package_switch_groups(starter)

        remove.assert_called_once_with('coaching@g.us', student.phone)
        self.assertEqual(previous.diligence_whatsapp_group_removal_state, 'removed')

    def test_draft_test_order_does_not_remove_anyone_from_group(self):
        student = self.env['res.partner'].create({
            'name': 'Draft Renewal Test Student',
            'phone': '628123456789',
        })
        package = self.env['product.template'].create({
            'name': 'Draft Renewal Test Package',
            'type': 'service',
            'sale_ok': True,
            'diligence_whatsapp_group_jid': '120363000000000000@g.us',
        })
        order = self.env['sale.order'].create({
            'partner_id': student.id,
            'diligence_renewal_package_id': package.id,
            'diligence_access_expires_at': '2099-01-01 00:00:00',
            'diligence_renewal_status': 'not_continue',
            'diligence_whatsapp_group_removal_state': 'pending',
        })
        service_class = type(self.env['diligence.whatsapp.service'])
        with patch.object(service_class, 'remove_group_participant') as remove:
            order._diligence_remove_from_whatsapp_group()

        remove.assert_not_called()
        self.assertEqual(order.diligence_whatsapp_group_removal_state, 'not_required')
