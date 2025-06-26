from odoo import api, fields, models, _
import requests
import logging

_logger = logging.getLogger(__name__)


class GitHubRepository(models.Model):
    _name = 'github.repository'
    _description = 'GitHub Repository'
    _rec_name = 'full_name'
    _order = 'full_name'

    name = fields.Char(string='Repository Name', required=True)
    full_name = fields.Char(string='Full Name', required=True, help='owner/repository format')
    owner = fields.Char(string='Owner', required=True)
    description = fields.Text(string='Description')
    html_url = fields.Char(string='GitHub URL', required=True)
    clone_url = fields.Char(string='Clone URL')
    ssh_url = fields.Char(string='SSH URL')
    default_branch = fields.Char(string='Default Branch', default='main')
    is_private = fields.Boolean(string='Private Repository', default=False)
    is_fork = fields.Boolean(string='Is Fork', default=False)
    language = fields.Char(string='Primary Language')
    stars_count = fields.Integer(string='Stars Count', default=0)
    forks_count = fields.Integer(string='Forks Count', default=0)
    open_issues_count = fields.Integer(string='Open Issues', default=0)
    created_at = fields.Datetime(string='Created At')
    updated_at = fields.Datetime(string='Updated At')
    pushed_at = fields.Datetime(string='Last Push')
    size = fields.Integer(string='Size (KB)', default=0)
    
    # Relations
    branch_ids = fields.One2many('github.branch', 'repository_id', string='Branches')
    project_ids = fields.One2many('project.project', 'github_repository_id', string='Projects')
    
    _sql_constraints = [
        ('unique_full_name', 'unique(full_name)', 'Repository full name must be unique!')
    ]

    @api.model
    def fetch_user_repositories(self, username):
        """Fetch all repositories for a specific user"""
        return self._fetch_repositories(f'https://api.github.com/users/{username}/repos')

    @api.model
    def fetch_org_repositories(self, org_name):
        """Fetch all repositories for a specific organization"""
        return self._fetch_repositories(f'https://api.github.com/orgs/{org_name}/repos')

    @api.model
    def fetch_authenticated_user_repositories(self):
        """Fetch all repositories for the authenticated user (including private ones)"""
        return self._fetch_repositories('https://api.github.com/user/repos')

    @api.model
    def _fetch_repositories(self, api_url):
        """Generic method to fetch repositories from GitHub API"""
        github_token = self.env['ir.config_parameter'].sudo().get_param('github_integration.token')
        headers = {'Accept': 'application/vnd.github.v3+json'}
        if github_token:
            headers['Authorization'] = f'token {github_token}'
        
        repositories = []
        page = 1
        per_page = 100
        
        try:
            while True:
                url = f"{api_url}?page={page}&per_page={per_page}&sort=updated"
                _logger.info("Fetching repositories from: %s", url)
                
                response = requests.get(url, headers=headers, timeout=30)
                
                if response.status_code == 200:
                    repos_data = response.json()
                    
                    if not repos_data:  # No more repositories
                        break
                        
                    _logger.info("Found %d repositories on page %d", len(repos_data), page)
                    
                    for repo_data in repos_data:
                        repo_vals = self._prepare_repository_values(repo_data)
                        repositories.append(repo_vals)
                    
                    page += 1
                    
                    # GitHub API returns less than per_page when it's the last page
                    if len(repos_data) < per_page:
                        break
                        
                elif response.status_code == 404:
                    _logger.warning("User/Organization not found: %s", api_url)
                    break
                else:
                    _logger.error("Failed to fetch repositories - HTTP %d: %s", 
                                response.status_code, response.text)
                    break
                    
        except requests.exceptions.RequestException as e:
            _logger.error("Request error while fetching repositories: %s", str(e))
        except Exception as e:
            _logger.error("Unexpected error fetching repositories: %s", str(e))
        
        # Create or update repository records
        if repositories:
            self._create_or_update_repositories(repositories)
            _logger.info("Processed %d repositories", len(repositories))
        
        return repositories

    def _prepare_repository_values(self, repo_data):
        """Prepare repository values from GitHub API response"""
        return {
            'name': repo_data['name'],
            'full_name': repo_data['full_name'],
            'owner': repo_data['owner']['login'],
            'description': repo_data.get('description', ''),
            'html_url': repo_data['html_url'],
            'clone_url': repo_data['clone_url'],
            'ssh_url': repo_data['ssh_url'],
            'default_branch': repo_data.get('default_branch', 'main'),
            'is_private': repo_data['private'],
            'is_fork': repo_data['fork'],
            'language': repo_data.get('language', ''),
            'stars_count': repo_data['stargazers_count'],
            'forks_count': repo_data['forks_count'],
            'open_issues_count': repo_data['open_issues_count'],
            'created_at': self._parse_github_datetime(repo_data['created_at']),
            'updated_at': self._parse_github_datetime(repo_data['updated_at']),
            'pushed_at': self._parse_github_datetime(repo_data['pushed_at']),
            'size': repo_data['size'],
        }

    def _parse_github_datetime(self, datetime_str):
        """Parse GitHub datetime string to Odoo datetime"""
        if not datetime_str:
            return False
        try:
            from datetime import datetime
            return datetime.strptime(datetime_str, '%Y-%m-%dT%H:%M:%SZ')
        except (ValueError, TypeError):
            return False

    def _create_or_update_repositories(self, repositories_data):
        """Create or update repository records"""
        for repo_data in repositories_data:
            existing_repo = self.search([('full_name', '=', repo_data['full_name'])], limit=1)
            if existing_repo:
                existing_repo.write(repo_data)
            else:
                self.create(repo_data)

    def action_fetch_branches(self):
        """Fetch branches for this repository"""
        for repo in self:
            self.env['github.branch'].fetch_branches_for_repository(repo.id)

    @api.model
    def refresh_all_repositories(self):
        """Refresh all repositories from their sources"""
        # Get unique owners from existing repositories
        owners = self.search([]).mapped('owner')
        unique_owners = list(set(owners))
        
        for owner in unique_owners:
            # Try to fetch as user first, then as org
            repos = self.fetch_user_repositories(owner)
            if not repos:
                self.fetch_org_repositories(owner)

    def name_get(self):
        """Custom name display for repository selection"""
        result = []
        for repo in self:
            name = f"{repo.full_name}"
            if repo.description:
                name += f" - {repo.description[:50]}{'...' if len(repo.description) > 50 else ''}"
            result.append((repo.id, name))
        return result