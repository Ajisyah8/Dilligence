import logging

from odoo.addons.auth_signup.controllers.main import AuthSignupHome
from odoo.http import request

_logger = logging.getLogger(__name__)


class DiligenceAuthSignup(AuthSignupHome):
    def get_auth_signup_qcontext(self):
        qcontext = super().get_auth_signup_qcontext()
        qcontext['phone'] = (request.params.get('phone') or '').strip()
        return qcontext

    def _prepare_signup_values(self, qcontext):
        values = super()._prepare_signup_values(qcontext)
        values['phone'] = (qcontext.get('phone') or '').strip()
        return values

