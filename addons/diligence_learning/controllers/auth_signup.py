from odoo.addons.auth_signup.controllers.main import AuthSignupHome


class DiligenceAuthSignup(AuthSignupHome):
    def _prepare_signup_values(self, qcontext):
        values = super()._prepare_signup_values(qcontext)
        values['phone'] = (qcontext.get('phone') or '').strip()
        values['diligence_newsletter_opt_in'] = qcontext.get('diligence_newsletter_opt_in') in (
            True, 'true', 'on', '1', 'yes',
        )
        return values
