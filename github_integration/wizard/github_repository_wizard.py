from odoo import api, fields, models, _
from odoo.exceptions import UserError


class GitHubRepositoryWizard(models.TransientModel):
    _name = 'github.repository.wizard'
    _description = 'GitHub Repository Fetch Wizard'

    username = fields.Char(
        string='GitHub Username/Organization',
        required=True,
        help='Enter GitHub username or organization name to fetch repositories'
    )
    
    fetch_type = fields.Selection([
        ('user', 'User Repositories'),
        ('org', 'Organization Repositories'),
        ('authenticated', 'All Accessible Repositories (requires token)')
    ], string='Fetch Type', default='user', required=True)
    
    def action_fetch_repositories(self):
        """Fetch repositories based on the selected type"""
        if not self.username and self.fetch_type != 'authenticated':
            raise UserError(_('Please enter a username or organization name.'))
        
        github_repo_model = self.env['github.repository']
        
        try:
            if self.fetch_type == 'user':
                repositories = github_repo_model.fetch_user_repositories(self.username)
            elif self.fetch_type == 'org':
                repositories = github_repo_model.fetch_org_repositories(self.username)
            elif self.fetch_type == 'authenticated':
                repositories = github_repo_model.fetch_authenticated_user_repositories()
            
            if repositories:
                message = _('Successfully fetched %d repositories.') % len(repositories)
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Success'),
                        'message': message,
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('No Repositories'),
                        'message': _('No repositories found or accessible.'),
                        'type': 'warning',
                        'sticky': False,
                    }
                }
                
        except Exception as e:
            raise UserError(_('Error fetching repositories: %s') % str(e))