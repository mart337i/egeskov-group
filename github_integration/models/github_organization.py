from odoo import api, fields, models, _
import requests
import logging

_logger = logging.getLogger(__name__)


class GitHubOrganization(models.Model):
    _name = 'github.organization'
    _description = 'GitHub Organization/User'
    _rec_name = 'login'
    _order = 'login'

    login = fields.Char(string='Username/Organization', required=True, help='GitHub username or organization name')
    name = fields.Char(string='Display Name', help='Full name or organization display name')
    type = fields.Selection([
        ('User', 'User'),
        ('Organization', 'Organization')
    ], string='Type', required=True, default='User')
    
    # GitHub API data
    github_id = fields.Integer(string='GitHub ID')
    avatar_url = fields.Char(string='Avatar URL')
    html_url = fields.Char(string='GitHub URL')
    description = fields.Text(string='Description')
    blog = fields.Char(string='Website/Blog')
    location = fields.Char(string='Location')
    email = fields.Char(string='Email')
    company = fields.Char(string='Company')
    
    # Statistics
    public_repos = fields.Integer(string='Public Repositories', default=0)
    public_gists = fields.Integer(string='Public Gists', default=0)
    followers = fields.Integer(string='Followers', default=0)
    following = fields.Integer(string='Following', default=0)
    
    # Organization specific fields
    total_private_repos = fields.Integer(string='Private Repositories', default=0)
    owned_private_repos = fields.Integer(string='Owned Private Repositories', default=0)
    private_gists = fields.Integer(string='Private Gists', default=0)
    disk_usage = fields.Integer(string='Disk Usage (KB)', default=0)
    collaborators = fields.Integer(string='Collaborators', default=0)
    
    # Sync management
    is_active = fields.Boolean(string='Active Sync', default=True, help='Whether to sync repositories for this organization/user')
    github_token = fields.Char(string='GitHub Token', help='Personal Access Token for this organization/user')
    last_sync_date = fields.Datetime(string='Last Sync Date')
    sync_status = fields.Selection([
        ('never', 'Never Synced'),
        ('success', 'Success'),
        ('error', 'Error'),
        ('in_progress', 'In Progress')
    ], string='Sync Status', default='never')
    sync_error_message = fields.Text(string='Last Sync Error')
    auto_sync = fields.Boolean(string='Auto Sync', default=True, help='Automatically sync during scheduled jobs')
    
    # Relations
    repository_ids = fields.One2many('github.repository', 'organization_id', string='Repositories')
    starred_repository_ids = fields.Many2many('github.repository', 'github_org_starred_repo_rel', 'organization_id', 'repository_id', string='Starred Repositories')
    all_repository_ids = fields.Many2many('github.repository', compute='_compute_all_repositories', string='All Repositories (Owned + Starred)')
    repository_count = fields.Integer(string='Repository Count', compute='_compute_repository_count', store=True)
    starred_count = fields.Integer(string='Starred Count', compute='_compute_starred_count', store=True)
    
    # Dates
    created_at = fields.Datetime(string='Created At')
    updated_at = fields.Datetime(string='Updated At')
    
    _sql_constraints = [
        ('unique_login', 'unique(login)', 'GitHub username/organization must be unique!')
    ]

    @api.depends('repository_ids')
    def _compute_repository_count(self):
        """Compute the number of repositories"""
        for org in self:
            org.repository_count = len(org.repository_ids)

    @api.depends('starred_repository_ids')
    def _compute_starred_count(self):
        """Compute the number of starred repositories"""
        for org in self:
            org.starred_count = len(org.starred_repository_ids)

    @api.depends('repository_ids', 'starred_repository_ids')
    def _compute_all_repositories(self):
        """Compute all repositories (owned + starred) for this organization/user"""
        for org in self:
            # Combine owned and starred repositories, removing duplicates
            all_repos = org.repository_ids | org.starred_repository_ids
            org.all_repository_ids = all_repos

    def get_all_repositories(self):
        """Get all repositories (owned + starred) for this organization/user"""
        return self.all_repository_ids

    @api.model
    def create_or_update_from_github_data(self, github_data):
        """Create or update organization from GitHub API data"""
        login = github_data['login']
        existing_org = self.search([('login', '=', login)], limit=1)
        
        org_vals = self._prepare_organization_values(github_data)
        
        if existing_org:
            existing_org.write(org_vals)
            return existing_org
        else:
            return self.create(org_vals)

    def _prepare_organization_values(self, github_data):
        """Prepare organization values from GitHub API response"""
        return {
            'login': github_data['login'],
            'name': github_data.get('name', ''),
            'type': github_data['type'],
            'github_id': github_data['id'],
            'avatar_url': github_data.get('avatar_url', ''),
            'html_url': github_data['html_url'],
            'description': github_data.get('description', ''),
            'blog': github_data.get('blog', ''),
            'location': github_data.get('location', ''),
            'email': github_data.get('email', ''),
            'company': github_data.get('company', ''),
            'public_repos': github_data.get('public_repos', 0),
            'public_gists': github_data.get('public_gists', 0),
            'followers': github_data.get('followers', 0),
            'following': github_data.get('following', 0),
            'total_private_repos': github_data.get('total_private_repos', 0),
            'owned_private_repos': github_data.get('owned_private_repos', 0),
            'private_gists': github_data.get('private_gists', 0),
            'disk_usage': github_data.get('disk_usage', 0),
            'collaborators': github_data.get('collaborators', 0),
            'created_at': self._parse_github_datetime(github_data.get('created_at')),
            'updated_at': self._parse_github_datetime(github_data.get('updated_at')),
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

    def _validate_github_token(self, github_token):
        """Validate GitHub token and return scope information"""
        if not github_token:
            return {'valid': False, 'scopes': [], 'message': 'No token provided'}
        
        try:
            headers = {'Accept': 'application/vnd.github.v3+json', 'Authorization': f'token {github_token}'}
            response = requests.get('https://api.github.com/user', headers=headers, timeout=10)
            
            if response.status_code == 200:
                scopes = response.headers.get('X-OAuth-Scopes', '').split(', ') if response.headers.get('X-OAuth-Scopes') else []
                return {
                    'valid': True, 
                    'scopes': scopes, 
                    'user': response.json().get('login'),
                    'message': f'Token valid for user: {response.json().get("login")}'
                }
            else:
                return {'valid': False, 'scopes': [], 'message': f'Invalid token - HTTP {response.status_code}'}
        except Exception as e:
            return {'valid': False, 'scopes': [], 'message': f'Token validation error: {str(e)}'}

    def action_sync_repositories(self):
        """Sync repositories for this organization/user"""
        for org in self:
            org.sync_status = 'in_progress'
            org.sync_error_message = False
            
            try:
                # Get token (can be None for public repos only)
                github_token = org.github_token or self.env['ir.config_parameter'].sudo().get_param('github_integration.token')
                
                # Validate token if provided, but continue without it if not available
                token_valid = False
                if github_token:
                    token_info = org._validate_github_token(github_token)
                    token_valid = token_info['valid']
                    if token_valid:
                        _logger.info("Using valid token for user '%s' with scopes: %s", 
                                   token_info.get('user'), ', '.join(token_info.get('scopes', [])))
                    else:
                        _logger.warning("Token invalid (%s), will sync public repositories only", token_info['message'])
                        github_token = None
                else:
                    _logger.info("No token provided, will sync public repositories only")
                
                # Fetch organization/user details first (works with or without token)
                org._fetch_organization_details()
                
                # Fetch repositories - will get public repos if no valid token
                if org.type == 'Organization':
                    repositories = self.env['github.repository'].fetch_org_repositories(org.login, github_token)
                else:
                    repositories = self.env['github.repository'].fetch_user_repositories(org.login, github_token)
                
                # Fetch starred repositories for users (only works with valid token)
                if org.type == 'User' and token_valid:
                    starred_repos = org._fetch_starred_repositories(github_token)
                
                # Update organization reference in repositories
                repo_records = self.env['github.repository'].search([
                    ('owner', '=', org.login)
                ])
                repo_records.write({'organization_id': org.id})
                
                org.last_sync_date = fields.Datetime.now()
                org.sync_status = 'success'
                
                # Prepare success message
                starred_count = len(starred_repos) if org.type == 'User' and token_valid else 0
                if token_valid:
                    if org.type == 'User' and starred_count > 0:
                        message = _('Successfully synced %d repositories and %d starred repositories for %s (including private repos)') % (len(repositories), starred_count, org.login)
                    else:
                        message = _('Successfully synced %d repositories for %s (including private repos)') % (len(repositories), org.login)
                else:
                    message = _('Successfully synced %d public repositories for %s (no valid token for private repos)') % (len(repositories), org.login)
                
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
                
            except Exception as e:
                _logger.error("Error syncing repositories for %s: %s", org.login, str(e))
                org.sync_status = 'error'
                org.sync_error_message = str(e)
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Error'),
                        'message': _('Error syncing repositories: %s') % str(e),
                        'type': 'danger',
                        'sticky': True,
                    }
                }

    def _fetch_organization_details(self):
        """Fetch detailed organization/user information from GitHub API"""
        # Use organization-specific token, fallback to system token
        github_token = self.github_token or self.env['ir.config_parameter'].sudo().get_param('github_integration.token')
        headers = {'Accept': 'application/vnd.github.v3+json'}
        if github_token:
            headers['Authorization'] = f'token {github_token}'
        
        try:
            if self.type == 'Organization':
                url = f'https://api.github.com/orgs/{self.login}'
            else:
                url = f'https://api.github.com/users/{self.login}'
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                github_data = response.json()
                org_vals = self._prepare_organization_values(github_data)
                self.write(org_vals)
            else:
                _logger.warning("Failed to fetch details for %s - HTTP %d", self.login, response.status_code)
                
        except Exception as e:
            _logger.error("Error fetching organization details for %s: %s", self.login, str(e))

    def _fetch_starred_repositories(self, github_token):
        """Fetch starred repositories for this user"""
        if not github_token or self.type != 'User':
            return []
        
        headers = {'Accept': 'application/vnd.github.v3+json', 'Authorization': f'token {github_token}'}
        starred_repos = []
        page = 1
        
        try:
            while True:
                url = f'https://api.github.com/users/{self.login}/starred?per_page=100&page={page}'
                response = requests.get(url, headers=headers, timeout=30)
                
                if response.status_code == 200:
                    repos_data = response.json()
                    if not repos_data:
                        break
                    
                    _logger.info("Found %d starred repositories on page %d for %s", len(repos_data), page, self.login)
                    
                    for repo_data in repos_data:
                        # Create or update repository record
                        repo_vals = self.env['github.repository']._prepare_repository_values(repo_data)
                        existing_repo = self.env['github.repository'].search([('full_name', '=', repo_vals['full_name'])], limit=1)
                        
                        if existing_repo:
                            existing_repo.write(repo_vals)
                            starred_repos.append(existing_repo.id)
                        else:
                            # Create organization for the repo owner if it doesn't exist
                            owner_login = repo_vals['owner']
                            organization = self.env['github.organization'].search([('login', '=', owner_login)], limit=1)
                            if not organization:
                                organization = self.env['github.organization'].create({
                                    'login': owner_login,
                                    'type': 'User',
                                    'is_active': False,  # Don't auto-sync starred repo owners
                                })
                            repo_vals['organization_id'] = organization.id
                            new_repo = self.env['github.repository'].create(repo_vals)
                            starred_repos.append(new_repo.id)
                    
                    page += 1
                    if len(repos_data) < 100:
                        break
                        
                elif response.status_code == 404:
                    _logger.warning("User not found or no starred repositories: %s", self.login)
                    break
                elif response.status_code == 403:
                    _logger.error("Access forbidden when fetching starred repos for %s", self.login)
                    break
                else:
                    _logger.error("Failed to fetch starred repositories - HTTP %d: %s", response.status_code, response.text[:200])
                    break
                    
        except Exception as e:
            _logger.error("Error fetching starred repositories for %s: %s", self.login, str(e))
        
        # Update the starred repositories relationship
        if starred_repos:
            self.starred_repository_ids = [(6, 0, starred_repos)]
            _logger.info("Updated %d starred repositories for %s", len(starred_repos), self.login)
        
        return starred_repos

    def action_sync_starred_repositories(self):
        """Sync starred repositories for this user"""
        if self.type != 'User':
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Warning'),
                    'message': _('Starred repositories can only be synced for users, not organizations'),
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        github_token = self.github_token or self.env['ir.config_parameter'].sudo().get_param('github_integration.token')
        if not github_token:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('GitHub token is required to fetch starred repositories'),
                    'type': 'danger',
                    'sticky': True,
                }
            }
        
        try:
            starred_repos = self._fetch_starred_repositories(github_token)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Successfully synced %d starred repositories') % len(starred_repos),
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('Error syncing starred repositories: %s') % str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }

    def action_view_repositories(self):
        """View repositories for this organization"""
        return {
            'name': _('Repositories - %s') % self.login,
            'type': 'ir.actions.act_window',
            'res_model': 'github.repository',
            'view_mode': 'kanban,list,form',
            'domain': [('organization_id', '=', self.id)],
            'context': {'default_organization_id': self.id}
        }

    def action_view_starred_repositories(self):
        """View starred repositories for this user"""
        return {
            'name': _('Starred Repositories - %s') % self.login,
            'type': 'ir.actions.act_window',
            'res_model': 'github.repository',
            'view_mode': 'kanban,list,form',
            'domain': [('id', 'in', self.starred_repository_ids.ids)],
            'context': {'search_default_starred': 1}
        }

    def action_open_github(self):
        """Open organization/user on GitHub"""
        return {
            'type': 'ir.actions.act_url',
            'url': self.html_url,
            'target': 'new',
        }

    @api.model
    def sync_all_active_organizations(self):
        """Sync repositories for all active organizations (called by cron)"""
        active_orgs = self.search([('is_active', '=', True), ('auto_sync', '=', True)])
        for org in active_orgs:
            org.action_sync_repositories()

    def name_get(self):
        """Custom name display"""
        result = []
        for org in self:
            name = org.login
            if org.name:
                name = f"{org.name} ({org.login})"
            if org.type:
                name += f" [{org.type}]"
            result.append((org.id, name))
        return result

    def action_test_token(self):
        """Test GitHub token access for this organization"""
        github_token = self.github_token or self.env['ir.config_parameter'].sudo().get_param('github_integration.token')
        token_info = self._validate_github_token(github_token)
        
        if token_info['valid']:
            # Test organization access
            try:
                headers = {'Accept': 'application/vnd.github.v3+json', 'Authorization': f'token {github_token}'}
                if self.type == 'Organization':
                    test_url = f'https://api.github.com/orgs/{self.login}/repos?per_page=1'
                else:
                    test_url = f'https://api.github.com/users/{self.login}/repos?per_page=1'
                
                response = requests.get(test_url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    repos = response.json()
                    private_access = any(repo.get('private', False) for repo in repos) if repos else False
                    message = f"✅ Token valid!\n\nUser: {token_info['user']}\nScopes: {', '.join(token_info['scopes'])}\nPrivate repo access: {'Yes' if private_access else 'No'}"
                    msg_type = 'success'
                else:
                    message = f"⚠️ Token valid but limited access to {self.login}\n\nHTTP {response.status_code}: {response.text[:200]}"
                    msg_type = 'warning'
                    
            except Exception as e:
                message = f"⚠️ Token valid but error testing access: {str(e)}"
                msg_type = 'warning'
        else:
            message = f"❌ Token invalid: {token_info['message']}"
            msg_type = 'danger'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'GitHub Token Test',
                'message': message,
                'type': msg_type,
                'sticky': True,
            }
        }