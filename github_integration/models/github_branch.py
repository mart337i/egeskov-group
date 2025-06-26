from odoo import api, fields, models, _
import requests
import logging

_logger = logging.getLogger(__name__)


class GitHubBranch(models.Model):
    _name = 'github.branch'
    _description = 'GitHub Branch'
    _rec_name = 'name'
    _order = 'name'

    name = fields.Char(string='Branch Name', required=True)
    repository_id = fields.Many2one('github.repository', string='Repository', required=True, ondelete='cascade')
    project_id = fields.Many2one('project.project', string='Project', ondelete='cascade')
    sha = fields.Char(string='SHA', help='Latest commit SHA for this branch')
    is_default = fields.Boolean(string='Default Branch', default=False)
    
    _sql_constraints = [
        ('unique_branch_repository', 'unique(name, repository_id)', 'Branch name must be unique per repository!')
    ]

    @api.model
    def fetch_branches_for_repository(self, repository_id):
        """Fetch branches from GitHub API for a specific repository"""
        repository = self.env['github.repository'].browse(repository_id)
        
        if not repository.owner or not repository.name:
            _logger.warning("Missing GitHub owner or repo name for repository %s", repository.full_name)
            return []
            
        # Get GitHub token from system parameters
        github_token = self.env['ir.config_parameter'].sudo().get_param('github_integration.token')
        headers = {'Accept': 'application/vnd.github.v3+json'}
        if github_token:
            headers['Authorization'] = f'token {github_token}'
            
        try:
            # Fetch branches from GitHub API
            branches_url = f'https://api.github.com/repos/{repository.owner}/{repository.name}/branches'
            _logger.info("Fetching branches from: %s", branches_url)
            
            response = requests.get(branches_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                branches_data = response.json()
                _logger.info("Found %d branches for repository %s", len(branches_data), repository.full_name)
                
                # Clear existing branches for this repository
                existing_branches = self.search([('repository_id', '=', repository_id)])
                existing_branches.unlink()
                
                # Create new branch records
                branch_vals = []
                for branch_data in branches_data:
                    branch_vals.append({
                        'name': branch_data['name'],
                        'repository_id': repository_id,
                        'sha': branch_data['commit']['sha'],
                        'is_default': branch_data.get('protected', False)
                    })
                
                if branch_vals:
                    self.create(branch_vals)
                    _logger.info("Created %d branch records for repository %s", len(branch_vals), repository.full_name)
                
                return branch_vals
                
            else:
                _logger.error("Failed to fetch branches - HTTP %d: %s", response.status_code, response.text)
                return []
                
        except requests.exceptions.RequestException as e:
            _logger.error("Request error while fetching branches: %s", str(e))
            return []
        except Exception as e:
            _logger.error("Unexpected error fetching branches: %s", str(e))
            return []

    @api.model
    def fetch_branches_for_project(self, project_id):
        """Fetch branches from GitHub API for a specific project (backward compatibility)"""
        project = self.env['project.project'].browse(project_id)
        if project.github_repository_id:
            return self.fetch_branches_for_repository(project.github_repository_id.id)
        return []

    @api.model
    def refresh_all_project_branches(self):
        """Refresh branches for all repositories"""
        repositories = self.env['github.repository'].search([])
        
        for repository in repositories:
            self.fetch_branches_for_repository(repository.id)

    def action_open_branch_on_github(self):
        if self.repository_id and self.repository_id.html_url:
            branch_url = f"{self.repository_id.html_url}/list/{self.name}"
            return {
                'type': 'ir.actions.act_url',
                'url': branch_url,
                'target': 'new',
            }