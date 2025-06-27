from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    github_token = fields.Char(
        string='GitHub Personal Access Token (Fallback)',
        help='Global fallback token for GitHub API authentication. Individual organization/user tokens are preferred and can be set in the GitHub Organizations/Users menu.',
        config_parameter='github_integration.token'
    )