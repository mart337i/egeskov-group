from odoo import api, fields, models, _
import requests
import json
import logging

_logger = logging.getLogger(__name__)

class ProjectProject(models.Model):
    _inherit = 'project.project'
    
    is_software_project = fields.Boolean(
        string='Software Project',
        help='Check if this is a software development project'
    )
    
    github_repository_id = fields.Many2one(
        'github.repository',
        string='GitHub Repository',
        help='Select GitHub repository for this project'
    )
    
    # Computed fields for backward compatibility
    github_repo_url = fields.Char(
        string='GitHub Repository URL',
        compute='_compute_github_fields',
        store=True,
        help='Full URL to the GitHub repository'
    )
    
    github_owner = fields.Char(
        string='Repository Owner',
        compute='_compute_github_fields',
        store=True,
        help='GitHub username or organization name'
    )
    
    github_repo_name = fields.Char(
        string='Repository Name',
        compute='_compute_github_fields',
        store=True,
        help='Name of the GitHub repository'
    )
    

    
    last_deployment_status = fields.Selection([
        ('success', 'Success'),
        ('failure', 'Failure'),
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('unknown', 'Unknown')
    ], string='Last Deployment Status', default='unknown')
    
    last_deployment_date = fields.Datetime(
        string='Last Deployment Date'
    )
    
    last_commit_sha = fields.Char(
        string='Last Commit SHA'
    )
    
    last_commit_message = fields.Text(
        string='Last Commit Message'
    )
    
    @api.onchange('github_repo_url')
    def onchange_github_repo_url(self):
        """Extract owner and repo name from GitHub URL"""
        if self.github_repo_url:
            try:
                # Parse GitHub URL to extract owner and repo
                url = self.github_repo_url.strip().rstrip('/')
                
                # Handle different GitHub URL formats
                if 'github.com' in url:
                    # Remove protocol if present
                    if url.startswith(('http://', 'https://')):
                        url = url.split('://', 1)[1]
                    
                    # Split by '/' and find github.com
                    parts = url.split('/')
                    github_index = next((i for i, part in enumerate(parts) if 'github.com' in part), -1)
                    
                    if github_index >= 0 and len(parts) > github_index + 2:
                        self.github_owner = parts[github_index + 1]
                        self.github_repo_name = parts[github_index + 2].replace('.git', '')
                    else:
                        # Clear fields if URL format is invalid
                        self.github_owner = False
                        self.github_repo_name = False
                else:
                    # Clear fields if not a GitHub URL
                    self.github_owner = False
                    self.github_repo_name = False
                    
            except Exception as e:
                _logger.warning(f"Could not parse GitHub URL: {e}")
                self.github_owner = False
                self.github_repo_name = False
    
    @api.depends('github_repository_id')
    def _compute_github_fields(self):
        for project in self:
            if project.github_repository_id:
                project.github_repo_url = project.github_repository_id.html_url
                project.github_owner = project.github_repository_id.owner
                project.github_repo_name = project.github_repository_id.name
            else:
                project.github_repo_url = False
                project.github_owner = False
                project.github_repo_name = False
    
    def action_refresh_github_status(self):
        """Refresh GitHub deployment status"""
        _logger.info("Starting GitHub status refresh for %d records", len(self))
        for record in self:
            _logger.info("Processing record ID: %s, Owner: %s, Repo: %s", 
                        record.id, record.github_owner, record.github_repo_name)
            if record.github_owner and record.github_repo_name:
                record._fetch_github_data()
            else:
                _logger.warning("Skipping record ID %s - missing owner or repo name", record.id)

    def action_refresh_github_branches(self):
        """Refresh GitHub branches"""
        for record in self:
            if record.is_software_project and record.github_repository_id:
                self.env['github.branch'].fetch_branches_for_repository(record.github_repository_id.id)

    def _fetch_github_data(self):
        """Fetch latest deployment and commit data from GitHub API"""
        _logger.info("Fetching GitHub data for %s/%s", self.github_owner, self.github_repo_name)
        
        if not self.github_owner or not self.github_repo_name:
            _logger.error("Missing GitHub owner or repo name - Owner: %s, Repo: %s", 
                        self.github_owner, self.github_repo_name)
            return
        
        headers = {'Accept': 'application/vnd.github.v3+json'}
        
        # Get GitHub token from system parameters
        github_token = self.env['ir.config_parameter'].sudo().get_param('github_integration.token')
        if github_token:
            headers['Authorization'] = f'token {github_token}'
            _logger.debug("Using GitHub token from system parameters for authentication")
        else:
            _logger.warning("No GitHub token configured in system parameters - API rate limits may apply")
    
        try:
            # Get latest deployment
            deployments_url = f'https://api.github.com/repos/{self.github_owner}/{self.github_repo_name}/deployments'
            _logger.info("Requesting deployments from: %s", deployments_url)
            
            response = requests.get(deployments_url, headers=headers, timeout=10)
            _logger.info("Deployments API response - Status: %d, Headers: %s", 
                        response.status_code, dict(response.headers))
            
            if response.status_code == 200:
                deployments = response.json()
                _logger.info("Found %d deployments", len(deployments))
                
                if deployments:
                    latest_deployment = deployments[0]
                    _logger.debug("Latest deployment data: %s", latest_deployment)
                
                    # Get deployment status
                    status_url = latest_deployment.get('statuses_url')
                    if status_url:
                        _logger.info("Requesting deployment status from: %s", status_url)
                        status_response = requests.get(status_url, headers=headers, timeout=10)
                        _logger.info("Status API response - Status: %d", status_response.status_code)
                    
                        if status_response.status_code == 200:
                            statuses = status_response.json()
                            _logger.info("Found %d deployment statuses", len(statuses))
                            
                            if statuses:
                                latest_status = statuses[0]
                                status_state = latest_status.get('state', 'unknown')
                                _logger.info("Latest deployment status: %s", status_state)
                                _logger.debug("Full status data: %s", latest_status)
                                
                                self.last_deployment_status = status_state
                                self.last_deployment_date = fields.Datetime.now()
                            else:
                                _logger.warning("No deployment statuses found")
                        else:
                            _logger.error("Failed to get deployment status - HTTP %d: %s", 
                                        status_response.status_code, status_response.text)
                    else:
                        _logger.warning("No statuses_url found in deployment data")
                else:
                    _logger.warning("No deployments found for repo")
            else:
                _logger.error("Failed to get deployments - HTTP %d: %s", 
                            response.status_code, response.text)
            
            # Get latest commit
            commits_url = f'https://api.github.com/repos/{self.github_owner}/{self.github_repo_name}/commits'
            _logger.info("Requesting commits from: %s", commits_url)
            
            commits_response = requests.get(commits_url, headers=headers, timeout=10)
            _logger.info("Commits API response - Status: %d", commits_response.status_code)
        
            if commits_response.status_code == 200:
                commits = commits_response.json()
                _logger.info("Found %d commits", len(commits))
                
                if commits:
                    latest_commit = commits[0]
                    commit_sha = latest_commit.get('sha', '')[:7]
                    commit_message = latest_commit.get('commit', {}).get('message', '')
                    
                    _logger.info("Latest commit - SHA: %s, Message: %s", commit_sha, commit_message[:100])
                    _logger.debug("Full commit data: %s", latest_commit)
                    
                    self.last_commit_sha = commit_sha
                    self.last_commit_message = commit_message
                else:
                    _logger.warning("No commits found for repo")
            else:
                _logger.error("Failed to get commits - HTTP %d: %s", 
                            commits_response.status_code, commits_response.text)
            
        except requests.exceptions.Timeout:
            _logger.error("Timeout while fetching GitHub data for %s/%s", 
                        self.github_owner, self.github_repo_name)
            self.last_deployment_status = 'unknown'
        except requests.exceptions.ConnectionError as e:
            _logger.error("Connection error while fetching GitHub data: %s", str(e))
            self.last_deployment_status = 'unknown'
        except requests.exceptions.RequestException as e:
            _logger.error("Request error while fetching GitHub data: %s", str(e))
            self.last_deployment_status = 'unknown'
        except Exception as e:
            _logger.error("Unexpected error fetching GitHub data for %s/%s: %s", 
                        self.github_owner, self.github_repo_name, str(e))
            _logger.exception("Full traceback:")
            self.last_deployment_status = 'unknown'
        
        _logger.info("Finished fetching GitHub data for %s/%s", self.github_owner, self.github_repo_name)