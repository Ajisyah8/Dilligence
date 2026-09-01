from odoo import http
from odoo.addons.auth_signup.controllers.main import AuthSignupHome


class DiligenceAuthSignup(AuthSignupHome):
    def get_auth_signup_qcontext(self):
        """Keep custom signup fields that Odoo's allow-list omits."""
        qcontext = super().get_auth_signup_qcontext()
        qcontext['phone'] = (http.request.params.get('phone') or '').strip()
        qcontext['diligence_newsletter_opt_in'] = http.request.params.get(
            'diligence_newsletter_opt_in'
        ) in (True, 'true', 'on', '1', 'yes')
        return qcontext

    def _prepare_signup_values(self, qcontext):
        values = super()._prepare_signup_values(qcontext)
        values['phone'] = qcontext['phone']
        values['diligence_newsletter_opt_in'] = qcontext['diligence_newsletter_opt_in']
        return values
