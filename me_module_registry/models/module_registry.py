# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
import logging
import requests
import json
import base64
import re
import os
import subprocess
import shutil
import tempfile
from pathlib import Path

_logger = logging.getLogger(__name__)


class ModuleRegistry(models.Model):
    _name = 'module.registry'
    _description = 'Module Version (Specific Version Information)'
    _rec_name = 'display_name'
    _order = 'template_id, version desc'
    
    # Local Repository Cloning Strategy:
    # For repositories marked as odoo_module_repo=True, this module now uses local git clones
    # instead of GitHub API calls to avoid rate limiting issues during heavy operations.
    # 
    # Local clones are stored in: {filestore}/module_repos/{repository_full_name_sanitized}/
    # 
    # Benefits:
    # - No GitHub API rate limiting for scanning operations
    # - Faster access to multiple branches and files
    # - Better handling of large repositories
    # - Offline capability once cloned
    #
    # The system automatically:
    # - Clones repositories on first sync
    # - Updates existing clones on subsequent syncs
    # - Cleans up clones for unmarked repositories (via cron job)

    # Link to template (static information)
    template_id = fields.Many2one('module.template', 'Module Template', 
                                required=True, ondelete='cascade', index=True)
    
    # Version-specific information
    sequence = fields.Integer('Sequence')
    version = fields.Char('Module Version', required=True, readonly=True, index=True)
    odoo_version_id = fields.Many2one('odoo.version', 'Odoo Version', readonly=True)
    
    # Version tracking and lifecycle management
    major_version = fields.Char('Major Version', compute='_compute_version_parts', store=True, index=True)
    minor_version = fields.Char('Minor Version', compute='_compute_version_parts', store=True)
    patch_version = fields.Char('Patch Version', compute='_compute_version_parts', store=True)
    version_status = fields.Selection([
        ('active', 'Active'),
        ('deprecated', 'Deprecated'),
        ('obsolete', 'Obsolete'),
        ('migration_needed', 'Migration Needed'),
        ('beta', 'Beta'),
        ('alpha', 'Alpha')
    ], 'Version Status', default='active')
    deprecation_date = fields.Date('Deprecation Date')
    end_of_life_date = fields.Date('End of Life Date')
    
    # Version-specific manifest data
    manifest_data = fields.Json('Full Manifest Data', readonly=True)
    
    # Module status and compatibility
    installable = fields.Boolean('Installable', default=True, readonly=True)
    auto_install = fields.Boolean('Auto Install', default=False, readonly=True)
    
    # GitHub integration
    github_repository_id = fields.Many2one('github.repository', 'GitHub Repository', 
                                         related='template_id.github_repository_id', store=True, readonly=True)
    library_id = fields.Many2one('module.library', 'Module Library', 
                               related='template_id.library_id', store=True, readonly=True)
    github_branch = fields.Char('GitHub Branch', readonly=True)
    manifest_url = fields.Char('Manifest URL', readonly=True)
    readme_url = fields.Char('README URL', readonly=True)
    
    # Template-related fields (for easy access)
    name = fields.Char('Module Name', related='template_id.name', readonly=True)
    technical_name = fields.Char('Technical Name', related='template_id.technical_name', readonly=True)
    summary = fields.Text('Summary', related='template_id.summary', readonly=True)
    description = fields.Html('Description', related='template_id.description', readonly=True)
    author = fields.Char('Author', related='template_id.author', readonly=True)
    website = fields.Char('Website', related='template_id.website', readonly=True)
    license = fields.Char('License', related='template_id.license', readonly=True)
    category = fields.Char('Category', related='template_id.category', readonly=True)
    application = fields.Boolean('Application', related='template_id.application', readonly=True)
    github_path = fields.Char('Path in Repository', related='template_id.github_path', readonly=True)
    
    # Dependencies (from GitHub manifest - readonly)
    depends = fields.Text(string='Dependencies', readonly=True, help='JSON list of module dependencies from GitHub manifest')
    external_dependencies = fields.Text(string='External Dependencies', readonly=True, help='JSON list of external dependencies from GitHub manifest')
    
    # Module files and assets (from GitHub manifest - readonly)
    data_files = fields.Text(string='Data Files', readonly=True, help='JSON list of data files from GitHub manifest')
    demo_files = fields.Text(string='Demo Files', readonly=True, help='JSON list of demo files from GitHub manifest')
    assets = fields.Text(string='Assets', readonly=True, help='JSON dict of assets from GitHub manifest')
    
    # Metadata (system managed - readonly)
    last_sync = fields.Datetime(string='Last Sync', default=fields.Datetime.now, readonly=True)
    sync_status = fields.Selection([
        ('success', 'Success'),
        ('error', 'Error'),
        ('pending', 'Pending')
    ], string='Sync Status', default='pending', readonly=True)
    sync_error = fields.Text(string='Sync Error', readonly=True)
    
    # Computed fields
    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)
    full_name = fields.Char(string='Full Name', compute='_compute_full_name', store=True)
    github_url = fields.Char(string='GitHub URL', compute='_compute_github_url', store=True)
    
    # Formatted display fields
    depends_formatted = fields.Html(string='Dependencies', compute='_compute_formatted_fields', store=True)
    external_dependencies_formatted = fields.Html(string='External Dependencies', compute='_compute_formatted_fields', store=True)
    data_files_formatted = fields.Html(string='Data Files', compute='_compute_formatted_fields', store=True)
    demo_files_formatted = fields.Html(string='Demo Files', compute='_compute_formatted_fields', store=True)
    assets_formatted = fields.Text(string='Assets (Formatted)', compute='_compute_formatted_fields', store=True)
    manifest_data_formatted = fields.Text(string='Manifest Data (Formatted)', compute='_compute_formatted_fields', store=True)
    
    # Version analysis computed fields
    is_latest_version = fields.Boolean(string='Is Latest Version', compute='_compute_version_analysis', store=True)
    has_newer_version = fields.Boolean(string='Has Newer Version', compute='_compute_version_analysis', store=True)
    newer_versions_count = fields.Integer(string='Newer Versions Count', compute='_compute_version_analysis', store=True)
    all_versions_ids = fields.Many2many('module.registry', compute='_compute_all_versions', string='All Versions')
    version_family_count = fields.Integer(string='Version Family Count', compute='_compute_version_analysis', store=True)
    
    _sql_constraints = [
        ('unique_template_branch_version', 'unique(template_id, github_branch, version)', 
         'Version must be unique per template and branch!'),
    ]

    @api.depends('template_id', 'version')
    def _compute_display_name(self):
        for version in self:
            if version.template_id and version.version:
                version.display_name = f"{version.template_id.name} v{version.version}"
            elif version.template_id:
                version.display_name = version.template_id.name
            else:
                version.display_name = f"Version {version.version or 'Unknown'}"

    @api.depends('github_repository_id', 'github_path', 'github_branch')
    def _compute_github_url(self):
        for version in self:
            if version.github_repository_id and version.github_path and version.github_branch:
                version.github_url = f"{version.github_repository_id.html_url}/tree/{version.github_branch}/{version.github_path}"
            else:
                version.github_url = False

    @api.depends('template_id', 'github_branch', 'version')
    def _compute_full_name(self):
        for version in self:
            if version.template_id and version.template_id.github_repository_id:
                branch_info = f" ({version.github_branch})" if version.github_branch and version.github_branch != version.template_id.github_repository_id.default_branch else ""
                version_info = f" v{version.version}" if version.version else ""
                version.full_name = f"{version.template_id.github_repository_id.full_name}/{version.template_id.technical_name}{version_info}{branch_info}"
            else:
                version.full_name = f"{version.template_id.technical_name or 'Unknown'} v{version.version or 'Unknown'}"

    @api.depends('depends', 'external_dependencies', 'data_files', 'demo_files', 'assets', 'manifest_data')
    def _compute_formatted_fields(self):
        for module in self:
            # Format dependencies
            module.depends_formatted = module._format_list_field(module.depends, 'Dependencies')
            
            # Format external dependencies
            module.external_dependencies_formatted = module._format_external_deps(module.external_dependencies)
            
            # Format data files
            module.data_files_formatted = module._format_list_field(module.data_files, 'Data Files')
            
            # Format demo files
            module.demo_files_formatted = module._format_list_field(module.demo_files, 'Demo Files')
            
            # Format assets
            module.assets_formatted = module._format_json_field(module.assets, 'Assets')
            
            # Format manifest data
            module.manifest_data_formatted = module._format_manifest_data(module.manifest_data)

    def _format_list_field(self, json_field, title):
        """Format a JSON list field for nice HTML display"""
        if not json_field:
            return f"<p><em>No {title.lower()}</em></p>"
        
        try:
            items = json.loads(json_field) if isinstance(json_field, str) else json_field
            if not items:
                return f"<p><em>No {title.lower()}</em></p>"
            
            html = f"<div><strong>{title}:</strong><ul>"
            for item in items:
                html += f"<li><code>{item}</code></li>"
            html += "</ul></div>"
            return html
        except (json.JSONDecodeError, TypeError):
            return f"<p><em>Invalid {title.lower()} format</em></p>"

    def _format_external_deps(self, json_field):
        """Format external dependencies for nice HTML display"""
        if not json_field:
            return "<p><em>No external dependencies</em></p>"
        
        try:
            deps = json.loads(json_field) if isinstance(json_field, str) else json_field
            if not deps:
                return "<p><em>No external dependencies</em></p>"
            
            html = "<div><strong>External Dependencies:</strong>"
            for dep_type, dep_list in deps.items():
                if dep_list:
                    html += f"<h5>{dep_type.title()}:</h5><ul>"
                    for dep in dep_list:
                        html += f"<li><code>{dep}</code></li>"
                    html += "</ul>"
            html += "</div>"
            return html
        except (json.JSONDecodeError, TypeError):
            return "<p><em>Invalid external dependencies format</em></p>"

    def _format_json_field(self, json_field, field_name):
        """Format a JSON field for nice text display"""
        if not json_field:
            return f"No {field_name.lower()} data available"
        
        try:
            # If it's already a dict/list, use it directly
            if isinstance(json_field, (dict, list)):
                data = json_field
            else:
                # If it's a string, try to parse it
                data = json.loads(json_field)
            
            # Format as pretty JSON
            return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True)
        except (json.JSONDecodeError, TypeError) as e:
            return f"Invalid {field_name.lower()} format: {str(e)}"

    def _format_manifest_data(self, manifest_data):
        """Format manifest data for nice text display"""
        return self._format_json_field(manifest_data, 'Manifest Data')

    @api.depends('version')
    def _compute_version_parts(self):
        for module in self:
            if not module.version:
                module.major_version = '0.0'
                module.minor_version = '0'
                module.patch_version = '0'
                continue
                
            # Use our improved version parsing
            parsed_parts = self._parse_version(module.version)
            
            # Extract meaningful parts
            if parsed_parts[0] > 0 or parsed_parts[1] > 0:
                module.major_version = f"{parsed_parts[0]}.{parsed_parts[1]}"
                module.minor_version = str(parsed_parts[2])
                module.patch_version = str(parsed_parts[3]) if parsed_parts[3] > 0 else '0'
            else:
                # Fallback for unusual version formats
                module.major_version = module.version
                module.minor_version = '0'
                module.patch_version = '0'

    @api.depends('template_id', 'github_branch', 'version', 'major_version')
    def _compute_version_analysis(self):
        for version in self:
            if not version.template_id or not version.version:
                version._reset_version_analysis()
                continue
                
            branch_versions = self._get_branch_versions(version)
            all_versions = self._get_all_template_versions(version)
            
            version.version_family_count = len(all_versions)
            newer_versions = self._get_newer_versions(version, branch_versions)
            
            version.newer_versions_count = len(newer_versions)
            version.has_newer_version = bool(newer_versions)
            version.is_latest_version = not newer_versions

    def _reset_version_analysis(self):
        """Reset version analysis fields to default values"""
        self.is_latest_version = False
        self.has_newer_version = False
        self.newer_versions_count = 0
        self.version_family_count = 0

    def _get_branch_versions(self, version):
        """Get all versions of the same template in the same branch"""
        return self.search([
            ('template_id', '=', version.template_id.id),
            ('github_branch', '=', version.github_branch)
        ])

    def _get_all_template_versions(self, version):
        """Get all versions of the same template across all branches"""
        return self.search([('template_id', '=', version.template_id.id)])

    def _get_newer_versions(self, version_record, branch_versions):
        """Get versions newer than the current version in the same branch"""
        current_version = self._parse_version(version_record.version)
        newer_versions = []
        
        for other_version in branch_versions:
            if (other_version.id != version_record.id and other_version.version and
                self._parse_version(other_version.version) > current_version):
                newer_versions.append(other_version)
        
        return newer_versions

    def _compute_all_versions(self):
        for version in self:
            if version.template_id:
                all_versions = self.search([
                    ('template_id', '=', version.template_id.id)
                ])
                version.all_versions_ids = all_versions
            else:
                version.all_versions_ids = self.browse()

    def _parse_version(self, version_str):
        """Parse version string into comparable tuple with better handling"""
        if not version_str:
            return (0, 0, 0, 0, 0)
        
        # Clean up the version string
        clean_version = version_str.strip().lower()
        
        # Remove common prefixes
        clean_version = re.sub(r'^v\.?', '', clean_version)
        
        # Extract numeric parts using regex
        # This handles versions like "18.0.1.2.3", "1.0", "2.1.0-beta", etc.
        numeric_parts = re.findall(r'\d+', clean_version)
        
        if not numeric_parts:
            return (0, 0, 0, 0, 0)
        
        # Convert to integers and pad to 4 parts for consistent comparison
        parts = [int(part) for part in numeric_parts[:4]]
        while len(parts) < 4:
            parts.append(0)
        
        # Handle pre-release versions (alpha, beta, rc) by adding a negative component
        if any(keyword in clean_version for keyword in ['alpha', 'beta', 'rc', 'dev', 'pre']):
            # Add a 5th element to indicate pre-release (negative sorts before positive)
            parts.append(-1)
        else:
            # Add a 5th element for final releases
            parts.append(0)
        
        return tuple(parts)

    def _get_module_repos_path(self):
        """Get the path where module repositories are stored in filestore"""
        filestore_path = self.env['ir.attachment']._filestore()
        repos_path = os.path.join(filestore_path, 'module_repos')
        os.makedirs(repos_path, exist_ok=True)
        return repos_path

    def _get_repository_local_path(self, repository):
        """Get the local path for a repository"""
        repos_path = self._get_module_repos_path()
        # Use repository full_name but replace / with _ for filesystem safety
        safe_name = repository.full_name.replace('/', '_')
        return os.path.join(repos_path, safe_name)

    def _get_or_create_local_clone(self, repository):
        """Get or create a local clone of the repository"""
        repo_path = self._get_repository_local_path(repository)
        
        if os.path.exists(repo_path):
            # Repository exists, update it
            try:
                _logger.info(f"Updating existing clone at {repo_path}")
                self._update_local_repository(repo_path)
                return repo_path
            except Exception as e:
                _logger.warning(f"Failed to update repository at {repo_path}: {str(e)}. Re-cloning...")
                shutil.rmtree(repo_path, ignore_errors=True)
        
        # Clone the repository
        try:
            _logger.info(f"Cloning repository {repository.full_name} to {repo_path}")
            clone_url = self._get_clone_url(repository)
            
            # Create parent directory if it doesn't exist
            os.makedirs(os.path.dirname(repo_path), exist_ok=True)
            
            # Clone repository normally (not mirror)
            result = subprocess.run([
                'git', 'clone', clone_url, repo_path
            ], check=True, capture_output=True, text=True, timeout=300)
            
            # Fetch all branches
            subprocess.run([
                'git', 'fetch', '--all'
            ], cwd=repo_path, check=True, capture_output=True, text=True, timeout=120)
            
            _logger.info(f"Successfully cloned repository {repository.full_name}")
            return repo_path
            
        except subprocess.TimeoutExpired:
            _logger.error(f"Timeout while cloning repository {repository.full_name}")
            shutil.rmtree(repo_path, ignore_errors=True)
            return None
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            _logger.error(f"Failed to clone repository {repository.full_name}: {error_msg}")
            shutil.rmtree(repo_path, ignore_errors=True)
            return None
        except Exception as e:
            _logger.error(f"Error cloning repository {repository.full_name}: {str(e)}")
            shutil.rmtree(repo_path, ignore_errors=True)
            return None

    def _get_clone_url(self, repository):
        """Get the clone URL for the repository, using token if available"""
        github_token = self.env['ir.config_parameter'].sudo().get_param('github_integration.token')
        
        if github_token:
            # Use authenticated HTTPS URL
            return f"https://{github_token}@github.com/{repository.full_name}.git"
        else:
            # Use public HTTPS URL
            return f"https://github.com/{repository.full_name}.git"

    def _update_local_repository(self, repo_path):
        """Update an existing local repository"""
        try:
            # Fetch all updates
            subprocess.run([
                'git', 'fetch', '--all', '--prune'
            ], cwd=repo_path, check=True, capture_output=True, text=True, timeout=120)
            
            # Reset to latest state (only if we're on a branch)
            try:
                subprocess.run([
                    'git', 'reset', '--hard', 'HEAD'
                ], cwd=repo_path, check=True, capture_output=True, text=True, timeout=30)
            except subprocess.CalledProcessError:
                # If reset fails, we might be in detached HEAD state, which is fine
                pass
            
            _logger.info(f"Successfully updated repository at {repo_path}")
            
        except subprocess.TimeoutExpired:
            _logger.error(f"Timeout while updating repository at {repo_path}")
            raise
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            _logger.error(f"Failed to update repository at {repo_path}: {error_msg}")
            raise

    def _get_local_repository_branches(self, repo_path):
        """Get all branches from a local git repository"""
        try:
            # Get all remote branches
            result = subprocess.run([
                'git', 'branch', '-r'
            ], cwd=repo_path, check=True, capture_output=True, text=True)
            
            branches = []
            for line in result.stdout.strip().split('\n'):
                if line.strip() and not line.strip().startswith('origin/HEAD'):
                    # Extract branch name (remove 'origin/' prefix)
                    branch_name = line.strip().replace('origin/', '')
                    # Include main branches and version branches
                    if (branch_name in ['main', 'master', 'develop'] or 
                        re.match(r'^\d+\.\d+$', branch_name) or  # Version branches like 18.0, 17.0
                        re.match(r'^v?\d+\.\d+', branch_name)):  # Version branches like v18.0, 18.0-dev
                        branches.append(branch_name)
            
            # Always include default branch if not already included
            if not branches:
                branches = ['main']  # Fallback
                
            return branches
            
        except subprocess.CalledProcessError as e:
            _logger.error(f"Failed to get branches from {repo_path}: {e.stderr}")
            return ['main']  # Fallback
        except Exception as e:
            _logger.error(f"Error getting branches from {repo_path}: {str(e)}")
            return ['main']  # Fallback

    def _discover_modules_in_local_branch(self, repository, repo_path, branch):
        """Discover all Odoo modules in a specific branch of a local repository"""
        try:
            # Checkout the branch
            subprocess.run([
                'git', 'checkout', f'origin/{branch}'
            ], cwd=repo_path, check=True, capture_output=True, text=True, timeout=30)
            
            modules_found = []
            
            # Scan root directory for modules
            modules_found.extend(self._scan_local_directory_for_modules(repo_path, repository, "", branch))
            
            # Also check common module directories
            common_dirs = ['addons', 'modules', 'odoo-addons', 'src']
            for dir_name in common_dirs:
                dir_path = os.path.join(repo_path, dir_name)
                if os.path.exists(dir_path) and os.path.isdir(dir_path):
                    modules_found.extend(self._scan_local_directory_for_modules(dir_path, repository, dir_name, branch))
            
            return modules_found
            
        except subprocess.TimeoutExpired:
            _logger.error(f"Timeout while checking out branch {branch} in {repo_path}")
            return []
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            _logger.warning(f"Failed to checkout branch {branch} in {repo_path}: {error_msg}")
            return []
        except Exception as e:
            _logger.error(f"Error discovering modules in local branch {branch}: {str(e)}")
            return []

    def _scan_local_directory_for_modules(self, directory_path, repository, base_path="", branch=None):
        """Scan a local directory for Odoo modules"""
        modules_found = []
        
        try:
            if not os.path.exists(directory_path):
                return modules_found
                
            for item in os.listdir(directory_path):
                item_path = os.path.join(directory_path, item)
                
                if os.path.isdir(item_path):
                    # Check if this directory contains a __manifest__.py file
                    manifest_path = os.path.join(item_path, '__manifest__.py')
                    
                    if os.path.exists(manifest_path):
                        # This is an Odoo module
                        module_path = f"{base_path}/{item}" if base_path else item
                        module_data = self._parse_manifest_from_local_file(manifest_path, repository, module_path, branch)
                        if module_data:
                            modules_found.append(module_data)
                            
        except Exception as e:
            _logger.warning(f"Error scanning local directory {directory_path}: {str(e)}")
            
        return modules_found

    def _parse_manifest_from_local_file(self, manifest_path, repository, module_path, branch=None):
        """Parse __manifest__.py content from local file"""
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Remove comments and parse
            content = re.sub(r'#.*', '', content)
            import ast
            manifest_dict = ast.literal_eval(content)
            
            # Build module data similar to GitHub API version
            version_str = manifest_dict.get('version', '')
            technical_name = module_path.split('/')[-1]
            url_branch = branch or repository.default_branch
            
            # Create URLs that point to GitHub (for consistency with existing data)
            manifest_url = f"{repository.html_url}/blob/{url_branch}/{module_path}/__manifest__.py"
            readme_url = f"{repository.html_url}/blob/{url_branch}/{module_path}/README.md"
            
            module_data = {
                'technical_name': technical_name,
                'name': manifest_dict.get('name', technical_name),
                'version': version_str,
                'odoo_version': self._extract_odoo_version(version_str),
                'summary': manifest_dict.get('summary', ''),
                'description': manifest_dict.get('description', ''),
                'author': manifest_dict.get('author', ''),
                'website': manifest_dict.get('website', ''),
                'license': manifest_dict.get('license', ''),
                'category': manifest_dict.get('category', 'Uncategorized'),
                'installable': manifest_dict.get('installable', True),
                'auto_install': manifest_dict.get('auto_install', False),
                'application': manifest_dict.get('application', False),
                'depends': json.dumps(manifest_dict.get('depends', [])),
                'external_dependencies': json.dumps(manifest_dict.get('external_dependencies', {})),
                'data_files': json.dumps(manifest_dict.get('data', [])),
                'demo_files': json.dumps(manifest_dict.get('demo', [])),
                'assets': json.dumps(manifest_dict.get('assets', {})),
                'manifest_data': manifest_dict,
                'github_path': module_path,
                'manifest_url': manifest_url,
                'readme_url': readme_url,
            }
            
            return module_data
            
        except Exception as e:
            _logger.error(f"Error parsing local manifest {manifest_path}: {str(e)}")
            return None

    @api.model
    def sync_modules_from_repository(self, repository_id):
        """Sync all modules from a GitHub repository across multiple branches"""
        repository = self.env['github.repository'].browse(repository_id)
        if not repository.exists():
            return False
            
        if not repository.odoo_module_repo:
            _logger.warning(f"Repository {repository.full_name} is not marked as an Odoo module repository. Skipping sync.")
            return False

        try:
            # Use local cloning for odoo_module_repo=True repositories
            if repository.odoo_module_repo:
                return self._sync_modules_from_local_clone(repository)
            else:
                # Fallback to GitHub API for non-module repos (shouldn't happen due to check above)
                github_token = self.env['ir.config_parameter'].sudo().get_param('github_integration.token')
                return self._sync_modules_from_github_api(repository, github_token)
        except Exception as e:
            _logger.error(f"Error syncing modules from repository {repository.full_name}: {str(e)}")
            return False

    def _sync_modules_from_local_clone(self, repository):
        """Sync modules using local git clone instead of GitHub API"""
        _logger.info(f"Syncing repository {repository.full_name} using local clone")
        
        # Get or create local clone
        repo_path = self._get_or_create_local_clone(repository)
        if not repo_path:
            return False
            
        try:
            # Get all branches from local repository
            branches = self._get_local_repository_branches(repo_path)
            _logger.info(f"Found {len(branches)} branches in local repository {repository.full_name}")
            
            total_modules = 0
            for branch in branches:
                modules_found = self._discover_modules_in_local_branch(repository, repo_path, branch)
                _logger.info(f"Found {len(modules_found)} modules in branch {branch} of repository {repository.full_name}")
                
                # Process modules in smaller batches to avoid large transaction issues
                batch_size = 10
                for i in range(0, len(modules_found), batch_size):
                    batch = modules_found[i:i + batch_size]
                    
                    for module_data in batch:
                        module_data['github_branch'] = branch
                        self._create_or_update_module(module_data, repository)
                    
                    # Commit after each batch to avoid large transactions
                    try:
                        self.env.cr.commit()
                    except Exception as commit_e:
                        _logger.warning(f"Error committing batch for branch {branch}: {str(commit_e)}")
                        self.env.cr.rollback()
                
                total_modules += len(modules_found)
            
            _logger.info(f"Total modules synced: {total_modules} across {len(branches)} branches")
            return True
        except Exception as e:
            _logger.error(f"Error syncing modules from local clone {repository.full_name}: {str(e)}")
            return False

    def _sync_modules_from_github_api(self, repository, github_token):
        """Original GitHub API sync method (fallback)"""
        # Get all branches from the repository
        branches = self._get_repository_branches(repository, github_token)
        _logger.info(f"Found {len(branches)} branches in repository {repository.full_name}")
        
        total_modules = 0
        for branch in branches:
            modules_found = self._discover_modules_in_repository_branch(repository, branch, github_token)
            _logger.info(f"Found {len(modules_found)} modules in branch {branch} of repository {repository.full_name}")
            
            # Process modules in smaller batches to avoid large transaction issues
            batch_size = 10
            for i in range(0, len(modules_found), batch_size):
                batch = modules_found[i:i + batch_size]
                
                for module_data in batch:
                    module_data['github_branch'] = branch
                    self._create_or_update_module(module_data, repository)
                
                # Commit after each batch to avoid large transactions
                try:
                    self.env.cr.commit()
                except Exception as commit_e:
                    _logger.warning(f"Error committing batch for branch {branch}: {str(commit_e)}")
                    self.env.cr.rollback()
            
            total_modules += len(modules_found)
        
        _logger.info(f"Total modules synced: {total_modules} across {len(branches)} branches")
        return True

    def _get_repository_branches(self, repository, github_token=None):
        """Get all branches from a GitHub repository"""
        headers = {'Accept': 'application/vnd.github.v3+json'}
        if github_token:
            headers['Authorization'] = f'token {github_token}'

        api_url = f"https://api.github.com/repos/{repository.full_name}/branches"
        branches = []
        
        try:
            response = requests.get(api_url, headers=headers, timeout=30)
            if response.status_code == 200:
                branch_data = response.json()
                # Focus on main branches and version branches
                for branch in branch_data:
                    branch_name = branch['name']
                    # Include main branches and version-like branches (e.g., 18.0, 17.0, main, master)
                    if (branch_name in ['main', 'master', 'develop'] or 
                        re.match(r'^\d+\.\d+$', branch_name) or  # Version branches like 18.0, 17.0
                        re.match(r'^v?\d+\.\d+', branch_name)):  # Version branches like v18.0, 18.0-dev
                        branches.append(branch_name)
                
                # Always include default branch if not already included
                if repository.default_branch and repository.default_branch not in branches:
                    branches.append(repository.default_branch)
            else:
                _logger.warning(f"Could not fetch branches for {repository.full_name}: {response.status_code}")
                # Fallback to default branch
                branches = [repository.default_branch] if repository.default_branch else ['main']
                
        except Exception as e:
            _logger.error(f"Error fetching branches for {repository.full_name}: {str(e)}")
            # Fallback to default branch
            branches = [repository.default_branch] if repository.default_branch else ['main']
            
        return branches

    def _discover_modules_in_repository_branch(self, repository, branch, github_token=None):
        """Discover all Odoo modules in a specific branch of a GitHub repository"""
        headers = {'Accept': 'application/vnd.github.v3+json'}
        if github_token:
            headers['Authorization'] = f'token {github_token}'

        # Get repository contents for specific branch
        api_url = f"https://api.github.com/repos/{repository.full_name}/contents"
        modules_found = []
        
        try:
            # First, check root directory for modules
            modules_found.extend(self._scan_directory_for_modules(api_url, repository, headers, "", branch))
            
            # Also check common module directories
            common_dirs = ['addons', 'modules', 'odoo-addons', 'src']
            for dir_name in common_dirs:
                dir_url = f"{api_url}/{dir_name}"
                modules_found.extend(self._scan_directory_for_modules(dir_url, repository, headers, dir_name, branch))
                
        except Exception as e:
            _logger.error(f"Error discovering modules in {repository.full_name} branch {branch}: {str(e)}")
            
        return modules_found

    def _scan_directory_for_modules(self, api_url, repository, headers, base_path="", branch=None):
        """Scan a directory for Odoo modules in a specific branch"""
        modules_found = []
        
        # Add branch parameter to API URL if specified
        branch_param = f"?ref={branch}" if branch else ""
        
        try:
            response = requests.get(f"{api_url}{branch_param}", headers=headers, timeout=30)
            if response.status_code != 200:
                return modules_found
                
            contents = response.json()
            
            for item in contents:
                if item['type'] == 'dir':
                    # Check if this directory contains a __manifest__.py file
                    manifest_url = f"{api_url}/{item['name']}/__manifest__.py{branch_param}"
                    manifest_response = requests.get(manifest_url, headers=headers, timeout=10)
                    
                    if manifest_response.status_code == 200:
                        # This is an Odoo module
                        module_path = f"{base_path}/{item['name']}" if base_path else item['name']
                        module_data = self._parse_manifest_from_github(manifest_response.json(), repository, module_path, branch)
                        if module_data:
                            modules_found.append(module_data)
                            
        except Exception as e:
            _logger.warning(f"Error scanning directory {api_url} in branch {branch}: {str(e)}")
            
        return modules_found

    def _parse_manifest_from_github(self, manifest_file_data, repository, module_path, branch=None):
        """Parse __manifest__.py content from GitHub API response"""
        try:
            manifest_dict = self._decode_and_parse_manifest(manifest_file_data['content'])
            return self._build_module_data(manifest_dict, manifest_file_data, repository, module_path, branch)
        except Exception as e:
            _logger.error(f"Error parsing manifest for {module_path} in branch {branch}: {str(e)}")
            return None

    def _decode_and_parse_manifest(self, base64_content):
        """Decode and parse manifest content"""
        import ast
        content = base64.b64decode(base64_content).decode('utf-8')
        content = re.sub(r'#.*', '', content)  # Remove comments
        return ast.literal_eval(content)

    def _extract_odoo_version(self, version_str):
        """Extract Odoo version from version string using improved parsing"""
        if not version_str:
            return '18.0'
        
        # Use our improved version parsing to get the parts
        parsed = self._parse_version(version_str)
        
        # For Odoo versions, we typically want the first two parts (e.g., 18.0)
        if parsed[0] > 0:
            return f"{parsed[0]}.{parsed[1]}"
        
        # Fallback to regex for edge cases
        match = re.match(r'^(\\d+\\.\\d+)', version_str)
        return match.group(1) if match else '18.0'

    def _build_module_data(self, manifest_dict, manifest_file_data, repository, module_path, branch):
        """Build module data dictionary from manifest"""
        version_str = manifest_dict.get('version', '')
        technical_name = module_path.split('/')[-1]
        url_branch = branch or repository.default_branch
        
        return {
            'technical_name': technical_name,
            'name': manifest_dict.get('name', technical_name),
            'version': version_str,
            'odoo_version': self._extract_odoo_version(version_str),
            'summary': manifest_dict.get('summary', ''),
            'description': manifest_dict.get('description', ''),
            'author': manifest_dict.get('author', ''),
            'website': manifest_dict.get('website', ''),
            'license': manifest_dict.get('license', ''),
            'category': manifest_dict.get('category', 'Uncategorized'),
            'installable': manifest_dict.get('installable', True),
            'auto_install': manifest_dict.get('auto_install', False),
            'application': manifest_dict.get('application', False),
            'depends': json.dumps(manifest_dict.get('depends', [])),
            'external_dependencies': json.dumps(manifest_dict.get('external_dependencies', {})),
            'data_files': json.dumps(manifest_dict.get('data', [])),
            'demo_files': json.dumps(manifest_dict.get('demo', [])),
            'assets': json.dumps(manifest_dict.get('assets', {})),
            'manifest_data': manifest_dict,
            'github_path': module_path,
            'manifest_url': manifest_file_data['html_url'],
            'readme_url': f"{repository.html_url}/blob/{url_branch}/{module_path}/README.md",
        }

    def _create_or_update_module(self, module_data, repository):
        """Create or update a module version record"""
        # Use a savepoint to handle potential transaction errors
        try:
            with self.env.cr.savepoint():
                odoo_version = self._find_odoo_version(module_data['odoo_version'])
                if not odoo_version:
                    _logger.error(f"unable to determine Odoo version for {module_data['technical_name']}")
                    return
                
                template = self.env['module.template'].find_or_create_template(module_data, repository)
                version_data = self._prepare_version_data(module_data, template, odoo_version, repository)
                
                existing_version = self._find_existing_version(template, module_data, repository)
                
                if existing_version:
                    existing_version.write(version_data)
                    _logger.info(f"Updated version {module_data['technical_name']} v{module_data['version']} "
                               f"from {repository.full_name} ({module_data.get('github_branch', 'default')})")
                else:
                    self.create(version_data)
                    _logger.info(f"Created version {module_data['technical_name']} v{module_data['version']} "
                               f"from {repository.full_name} ({module_data.get('github_branch', 'default')})")
                    
        except Exception as e:
            _logger.error(f"Error creating/updating module version {module_data.get('technical_name', 'unknown')}: {str(e)}")
            # Handle sync error in a separate transaction to avoid transaction abort issues
            self._handle_sync_error_safe(module_data, repository, str(e))

    def _find_odoo_version(self, version_name):
        """Find or create Odoo version record"""
        return self.env['odoo.version'].find_version(version_name)

    def _prepare_version_data(self, module_data, template, odoo_version, repository):
        """Prepare version data for create/update"""
        return {
            'template_id': template.id,
            'version': module_data['version'],
            'odoo_version_id': odoo_version.id,
            'github_branch': module_data.get('github_branch', repository.default_branch),
            'installable': module_data.get('installable', True),
            'auto_install': module_data.get('auto_install', False),
            'manifest_data': module_data.get('manifest_data', {}),
            'manifest_url': module_data.get('manifest_url', ''),
            'readme_url': module_data.get('readme_url', ''),
            'depends': module_data.get('depends', '[]'),
            'external_dependencies': module_data.get('external_dependencies', '{}'),
            'data_files': module_data.get('data_files', '[]'),
            'demo_files': module_data.get('demo_files', '[]'),
            'assets': module_data.get('assets', '{}'),
            'last_sync': fields.Datetime.now(),
            'sync_status': 'success',
            'sync_error': False,
        }

    def _find_existing_version(self, template, module_data, repository):
        """Find existing version record"""
        return self.search([
            ('template_id', '=', template.id),
            ('github_branch', '=', module_data.get('github_branch', repository.default_branch)),
            ('version', '=', module_data['version'])
        ], limit=1)

    def _handle_sync_error(self, module_data, repository, error_msg):
        """Handle sync error by updating existing version with error status"""
        try:
            template = self.env['module.template'].search([
                ('technical_name', '=', module_data['technical_name']),
                ('github_repository_id', '=', repository.id)
            ], limit=1)
            
            if template:
                existing_version = self._find_existing_version(template, module_data, repository)
                if existing_version:
                    existing_version.write({
                        'sync_status': 'error',
                        'sync_error': error_msg,
                        'last_sync': fields.Datetime.now()
                    })
        except Exception as inner_e:
            _logger.error(f"Error updating error status: {str(inner_e)}")

    def _handle_sync_error_safe(self, module_data, repository, error_msg):
        """Handle sync error safely using a new transaction"""
        try:
            # Use a new cursor to avoid transaction abort issues
            with self.pool.cursor() as new_cr:
                new_env = api.Environment(new_cr, self.env.uid, self.env.context)
                
                template = new_env['module.template'].search([
                    ('technical_name', '=', module_data['technical_name']),
                    ('github_repository_id', '=', repository.id)
                ], limit=1)
                
                if template:
                    existing_version = new_env['module.registry'].search([
                        ('template_id', '=', template.id),
                        ('github_branch', '=', module_data.get('github_branch', repository.default_branch)),
                        ('version', '=', module_data['version'])
                    ], limit=1)
                    
                    if existing_version:
                        existing_version.write({
                            'sync_status': 'error',
                            'sync_error': error_msg,
                            'last_sync': fields.Datetime.now()
                        })
                        new_cr.commit()
                        _logger.info(f"Updated error status for {module_data['technical_name']}")
                    else:
                        # Create a minimal error record if no existing version found
                        try:
                            odoo_version = new_env['odoo.version'].search([
                                ('name', '=', self._extract_odoo_version(module_data.get('version', '')))
                            ], limit=1)
                            if not odoo_version:
                                odoo_version = new_env['odoo.version'].find_version(
                                    self._extract_odoo_version(module_data.get('version', ''))
                                )
                            
                            new_env['module.registry'].create({
                                'template_id': template.id,
                                'version': module_data['version'],
                                'odoo_version_id': odoo_version.id,
                                'github_branch': module_data.get('github_branch', repository.default_branch),
                                'sync_status': 'error',
                                'sync_error': error_msg,
                                'last_sync': fields.Datetime.now(),
                                'installable': False,
                            })
                            new_cr.commit()
                            _logger.info(f"Created error record for {module_data['technical_name']}")
                        except Exception as create_e:
                            _logger.error(f"Could not create error record for {module_data['technical_name']}: {str(create_e)}")
                            new_cr.rollback()
                            
        except Exception as outer_e:
            _logger.error(f"Error in safe error handling for {module_data.get('technical_name', 'unknown')}: {str(outer_e)}")

    def action_sync_from_github(self):
        """Action to sync module from GitHub"""
        for module in self:
            if module.github_repository_id:
                self.sync_modules_from_repository(module.github_repository_id.id)

    def action_open_github(self):
        """Open module on GitHub"""
        return {
            'type': 'ir.actions.act_url',
            'url': self.github_url,
            'target': 'new',
        }

    def action_open_manifest(self):
        """Open manifest file on GitHub"""
        return {
            'type': 'ir.actions.act_url',
            'url': self.manifest_url,
            'target': 'new',
        }

    def action_view_all_versions(self):
        """View all versions of this module template"""
        return {
            'name': _('All Versions of %s') % self.template_id.name,
            'type': 'ir.actions.act_window',
            'res_model': 'module.registry',
            'view_mode': 'list,form',
            'domain': [('template_id', '=', self.template_id.id)],
            'context': {'default_template_id': self.template_id.id}
        }

    def action_view_template(self):
        """View the module template"""
        return {
            'name': _('Template: %s') % self.template_id.name,
            'type': 'ir.actions.act_window',
            'res_model': 'module.template',
            'view_mode': 'form',
            'res_id': self.template_id.id,
        }



    def action_mark_deprecated(self):
        """Mark this version as deprecated"""
        self.write({
            'version_status': 'deprecated',
            'deprecation_date': fields.Date.today()
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Version marked as deprecated'),
                'type': 'success',
            }
        }

    def action_mark_obsolete(self):
        """Mark this version as obsolete"""
        self.write({
            'version_status': 'obsolete',
            'end_of_life_date': fields.Date.today()
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Version marked as obsolete'),
                'type': 'warning',
            }
        }

    @api.model
    def sync_all_repositories(self):
        """Sync modules from all marked GitHub repositories"""
        repositories = self.env['github.repository'].search([('odoo_module_repo', '=', True)])
        _logger.info(f"Syncing modules from {len(repositories)} marked repositories")
        
        for repository in repositories:
            self.sync_modules_from_repository(repository.id)

    @api.model
    def cleanup_local_repositories(self):
        """Clean up local repository clones for repositories that are no longer marked as module repos"""
        repos_path = self._get_module_repos_path()
        if not os.path.exists(repos_path):
            return
            
        # Get all marked repositories
        marked_repos = self.env['github.repository'].search([('odoo_module_repo', '=', True)])
        marked_repo_names = {repo.full_name.replace('/', '_') for repo in marked_repos}
        
        # Clean up directories for unmarked repositories
        try:
            for item in os.listdir(repos_path):
                item_path = os.path.join(repos_path, item)
                if os.path.isdir(item_path) and item not in marked_repo_names:
                    _logger.info(f"Cleaning up local repository clone: {item}")
                    shutil.rmtree(item_path, ignore_errors=True)
        except Exception as e:
            _logger.error(f"Error during repository cleanup: {str(e)}")

    def action_force_reclone(self):
        """Force re-clone of the repository (useful for troubleshooting)"""
        for module in self:
            if module.github_repository_id and module.github_repository_id.odoo_module_repo:
                repo_path = self._get_repository_local_path(module.github_repository_id)
                if os.path.exists(repo_path):
                    _logger.info(f"Force re-cloning repository {module.github_repository_id.full_name}")
                    shutil.rmtree(repo_path, ignore_errors=True)
                
                # Trigger sync which will re-clone
                self.sync_modules_from_repository(module.github_repository_id.id)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Repository re-cloning initiated'),
                'type': 'success',
            }
        }