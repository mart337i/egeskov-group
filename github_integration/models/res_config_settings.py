from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    github_token = fields.Char(
        string='GitHub Personal Access Token',
        help='Personal access token for GitHub API authentication',
        config_parameter='github_integration.token'
    )