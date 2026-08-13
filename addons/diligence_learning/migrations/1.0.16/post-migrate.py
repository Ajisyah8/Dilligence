from odoo import SUPERUSER_ID, api
from odoo.addons.diligence_learning.hooks import _ensure_package_template


def migrate(cr, version):
    if version:
        _ensure_package_template(api.Environment(cr, SUPERUSER_ID, {}))
