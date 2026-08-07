from . import controllers
from . import models

from odoo import Command
from odoo.addons.payment import reset_payment_provider, setup_provider


def post_init_hook(env):
    setup_provider(env, 'custom', custom_mode='qris_static')
    qris_provider = env['payment.provider'].search([
        ('code', '=', 'custom'),
        ('custom_mode', '=', 'qris_static'),
    ], limit=1)
    qris_method = env['payment.method'].with_context(active_test=False).search(
        [('code', '=', 'wire_transfer')], limit=1
    )
    if qris_provider and qris_method:
        qris_method.write({'name': 'Static QRIS', 'code': 'qris_static', 'active': True})
        qris_provider.payment_method_ids = [Command.set(qris_method.ids)]


def uninstall_hook(env):
    reset_payment_provider(env, 'custom', custom_mode='qris_static')
