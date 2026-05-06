# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import models
from . import controllers
from . import wizard

def uninstall_hook(env):
    dt = env.ref('website_slides.badge_data_certification_goal', raise_if_not_found=False)
    if dt:
        dt.domain = "[('completed', '=', True), (0, '=', 1)]"
