from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccountAccount(models.Model):
    _inherit = 'account.account'

    diligence_coa_group_id = fields.Many2one(
        'account.group',
        string='Parent COA Group',
        index=True,
        ondelete='restrict',
        check_company=True,
        group_expand='_read_group_diligence_coa_group_id',
    )

    diligence_coa_group = fields.Selection(
        selection=[
            ('1', '100 Assets'),
            ('2', '200 Liabilities'),
            ('3', "300 Stockholders' equity"),
            ('4', '400 Revenues'),
            ('5', '500 Costs and expenses'),
        ],
        string='COA Group',
        compute='_compute_diligence_coa_group',
        store=True,
        index=True,
    )

    @api.depends('code')
    def _compute_diligence_coa_group(self):
        for account in self:
            prefix = (account.code or '')[:1]
            account.diligence_coa_group = prefix if prefix in {'1', '2', '3', '4', '5'} else False

    @api.model
    def _read_group_diligence_coa_group_id(self, groups, domain):
        categories = self.env['account.group'].search([
            ('company_id', '=', self.env.company.root_id.id),
            ('code_prefix_start', '=like', '_'),
            ('code_prefix_end', '=like', '_'),
        ], order='code_prefix_start')
        return categories.filtered(lambda group: group.code_prefix_start == group.code_prefix_end)

    def action_create_main_category(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('New Main COA Category'),
            'res_model': 'account.group',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_company_id': self.env.company.root_id.id,
            },
        }

    @api.constrains('code', 'diligence_coa_group_id')
    def _check_diligence_subaccount_code(self):
        for account in self.filtered('diligence_coa_group_id'):
            prefix = account.diligence_coa_group_id.code_prefix_start
            if len(account.code or '') != 6 or not account.code.startswith(prefix):
                raise ValidationError(_(
                    'A sub-account must use a 6-digit code starting with %(prefix)s, '
                    'the first digit of its COA group.',
                    prefix=prefix,
                ))


class AccountGroup(models.Model):
    _inherit = 'account.group'

    @api.depends('code_prefix_start', 'code_prefix_end', 'name')
    def _compute_display_name(self):
        super()._compute_display_name()
        for group in self:
            prefix = group.code_prefix_start or ''
            if len(prefix) == 1 and group.code_prefix_end == prefix:
                group.display_name = group.name

    diligence_account_ids = fields.One2many(
        'account.account',
        'diligence_coa_group_id',
        string='Sub-Accounts',
    )

    def action_manage_subaccounts(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Manage Sub-Accounts - %s', self.name),
            'res_model': 'account.account',
            'view_mode': 'list,form',
            'domain': [('diligence_coa_group_id', '=', self.id)],
            'context': {'default_diligence_coa_group_id': self.id},
        }

    def action_create_subaccount(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('New Sub-Account'),
            'res_model': 'account.account',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_diligence_coa_group_id': self.id},
        }
