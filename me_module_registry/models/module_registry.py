# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
import logging
import requests
import json
import base64
import re

_logger = logging.getLogger(__name__)


class ModuleRegistry(models.Model):
    _name = 'module.registry'
    _description = 'Module Registry'
    _rec_name = 'name'
    _order = 'name'

    # Basic module information
    sequence = fields.Integer('sequence')
    name = fields.Char(string='Module Name', required=True, index=True)
    technical_name = fields.Char(string='Technical Name', required=True, index=True)
    version = fields.Char(string='Module Version', help='Version from manifest')
    odoo_version_id = fields.Many2one('odoo.version', string='Odoo Version')
    summary = fields.Text(string='Summary')
    description = fields.Html(string='Description')
    author = fields.Char(string='Author')
    website = fields.Char(string='Website')
    license = fields.Char(string='License')
    category = fields.Char(string='Category', default='Uncategorized')
    manifest_data = fields.Json(string='Full Manifest Data')
    
    # Module status and compatibility
    installable = fields.Boolean(string='Installable', default=True)
    auto_install = fields.Boolean(string='Auto Install', default=False)
    application = fields.Boolean(string='Application', default=False)
    
    # GitHub integration
    github_repository_id = fields.Many2one('github.repository', string='GitHub Repository', ondelete='cascade', required=True)
    library_id = fields.Many2one('module.library', string='Module Library', ondelete='cascade')
    github_path = fields.Char(string='Path in Repository', help='Path to module directory in repository')
    manifest_url = fields.Char(string='Manifest URL', help='Direct URL to __manifest__.py file')
    readme_url = fields.Char(string='README URL', help='Direct URL to README file')
    
    # Dependencies
    depends = fields.Text(string='Dependencies', help='JSON list of module dependencies')
    external_dependencies = fields.Text(string='External Dependencies', help='JSON list of external dependencies')
    
    # Module files and assets
    data_files = fields.Text(string='Data Files', help='JSON list of data files')
    demo_files = fields.Text(string='Demo Files', help='JSON list of demo files')
    assets = fields.Text(string='Assets', help='JSON dict of assets')
    
    # Metadata
    last_sync = fields.Datetime(string='Last Sync', default=fields.Datetime.now)
    sync_status = fields.Selection([
        ('success', 'Success'),
        ('error', 'Error'),
        ('pending', 'Pending')
    ], string='Sync Status', default='pending')
    sync_error = fields.Text(string='Sync Error')
    
    # Computed fields
    full_name = fields.Char(string='Full Name', compute='_compute_full_name', store=True)
    github_url = fields.Char(string='GitHub URL', compute='_compute_github_url', store=True)
    
    _sql_constraints = [
        ('unique_technical_name_repo_version', 'unique(technical_name, github_repository_id, version)', 
         'Technical name and version must be unique per repository!'),
    ]

    @api.depends('github_repository_id', 'github_path')
    def _compute_github_url(self):
        for module in self:
            if module.github_repository_id and module.github_path:
                module.github_url = f"{module.github_repository_id.html_url}/tree/{module.github_repository_id.default_branch}/{module.github_path}"
            else:
                module.github_url = False

    @api.depends('name', 'technical_name', 'github_repository_id')
    def _compute_full_name(self):
        for module in self:
            if module.github_repository_id:
                module.full_name = f"{module.github_repository_id.full_name}/{module.technical_name}"
            else:
                module.full_name = module.technical_name or module.name

    @api.model
    def sync_modules_from_repository(self, repository_id):
        """Sync all modules from a GitHub repository (only if marked as module repo)"""
        repository = self.env['github.repository'].browse(repository_id)
        if not repository.exists():
            return False
            
        if not repository.odoo_module_repo:
            _logger.warning(f"Repository {repository.full_name} is not marked as an Odoo module repository. Skipping sync.")
            return False

        github_token = self.env['ir.config_parameter'].sudo().get_param('github_integration.token')
        
        try:
            modules_found = self._discover_modules_in_repository(repository, github_token)
            _logger.info(f"Found {len(modules_found)} modules in repository {repository.full_name}")
            
            for module_data in modules_found:
                self._create_or_update_module(module_data, repository)
            
            return True
        except Exception as e:
            _logger.error(f"Error syncing modules from repository {repository.full_name}: {str(e)}")
            return False

    def _discover_modules_in_repository(self, repository, github_token=None):
        """Discover all Odoo modules in a GitHub repository"""
        headers = {'Accept': 'application/vnd.github.v3+json'}
        if github_token:
            headers['Authorization'] = f'token {github_token}'

        # Get repository contents
        api_url = f"https://api.github.com/repos/{repository.full_name}/contents"
        modules_found = []
        
        try:
            # First, check root directory for modules
            modules_found.extend(self._scan_directory_for_modules(api_url, repository, headers))
            
            # Also check common module directories
            common_dirs = ['addons', 'modules', 'odoo-addons', 'src']
            for dir_name in common_dirs:
                dir_url = f"{api_url}/{dir_name}"
                modules_found.extend(self._scan_directory_for_modules(dir_url, repository, headers, dir_name))
                
        except Exception as e:
            _logger.error(f"Error discovering modules in {repository.full_name}: {str(e)}")
            
        return modules_found

    def _scan_directory_for_modules(self, api_url, repository, headers, base_path=""):
        """Scan a directory for Odoo modules"""
        modules_found = []
        
        try:
            response = requests.get(api_url, headers=headers, timeout=30)
            if response.status_code != 200:
                return modules_found
                
            contents = response.json()
            
            for item in contents:
                if item['type'] == 'dir':
                    # Check if this directory contains a __manifest__.py file
                    manifest_url = f"{api_url}/{item['name']}/__manifest__.py"
                    manifest_response = requests.get(manifest_url, headers=headers, timeout=10)
                    
                    if manifest_response.status_code == 200:
                        # This is an Odoo module
                        module_path = f"{base_path}/{item['name']}" if base_path else item['name']
                        module_data = self._parse_manifest_from_github(manifest_response.json(), repository, module_path)
                        if module_data:
                            modules_found.append(module_data)
                            
        except Exception as e:
            _logger.warning(f"Error scanning directory {api_url}: {str(e)}")
            
        return modules_found

    def _parse_manifest_from_github(self, manifest_file_data, repository, module_path):
        """Parse __manifest__.py content from GitHub API response"""
        try:
            # Decode base64 content
            content = base64.b64decode(manifest_file_data['content']).decode('utf-8')
            
            # Parse the manifest file (it's a Python dict)
            # Remove comments and clean up the content
            content = re.sub(r'#.*', '', content)
            
            # Use ast.literal_eval to safely evaluate the Python dict
            import ast
            manifest_dict = ast.literal_eval(content)
            
            # Extract Odoo version from version string (e.g., "18.0.1.0.0" -> "18.0")
            version_str = manifest_dict.get('version', '')
            odoo_version_match = re.match(r'^(\d+\.\d+)', version_str)
            odoo_version = odoo_version_match.group(1) if odoo_version_match else '18.0'
            
            module_data = {
                'technical_name': module_path.split('/')[-1],
                'name': manifest_dict.get('name', module_path.split('/')[-1]),
                'version': version_str,
                'odoo_version': odoo_version,
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
                'readme_url': f"{repository.html_url}/blob/{repository.default_branch}/{module_path}/README.md",
            }
            
            return module_data
            
        except Exception as e:
            _logger.error(f"Error parsing manifest for {module_path}: {str(e)}")
            return None

    def _create_or_update_module(self, module_data, repository):
        """Create or update a module record"""
        try:
            # Find or create library for this repository
            library = self.env['module.library'].search([('github_repository_id', '=', repository.id)], limit=1)
            if not library:
                library = self.env['module.library'].create_library_for_repository(repository.id)
            
            # Find or create Odoo version record
            odoo_version = self.env['odoo.version'].search([('name', '=', module_data['odoo_version'])], limit=1)
            if not odoo_version:
                odoo_version = self.env['odoo.version'].create({
                    'name': module_data['odoo_version']
                })
            
            module_data['odoo_version_id'] = odoo_version.id
            module_data['github_repository_id'] = repository.id
            module_data['library_id'] = library.id
            module_data['last_sync'] = fields.Datetime.now()
            module_data['sync_status'] = 'success'
            module_data['sync_error'] = False
            
            # Remove odoo_version from data as we now have odoo_version_id
            module_data.pop('odoo_version', None)
            
            existing_module = self.search([
                ('technical_name', '=', module_data['technical_name']),
                ('github_repository_id', '=', repository.id),
                ('version', '=', module_data['version'])
            ], limit=1)
            
            if existing_module:
                existing_module.write(module_data)
                _logger.info(f"Updated module {module_data['technical_name']} v{module_data['version']} from {repository.full_name}")
            else:
                self.create(module_data)
                _logger.info(f"Created module {module_data['technical_name']} v{module_data['version']} from {repository.full_name}")
                
        except Exception as e:
            _logger.error(f"Error creating/updating module {module_data.get('technical_name', 'unknown')}: {str(e)}")
            # Create error record
            error_data = module_data.copy()
            error_data.update({
                'sync_status': 'error',
                'sync_error': str(e),
                'github_repository_id': repository.id,
                'last_sync': fields.Datetime.now()
            })
            
            existing_module = self.search([
                ('technical_name', '=', module_data['technical_name']),
                ('github_repository_id', '=', repository.id),
                ('version', '=', module_data.get('version', ''))
            ], limit=1)
            
            if existing_module:
                existing_module.write({
                    'sync_status': 'error',
                    'sync_error': str(e),
                    'last_sync': fields.Datetime.now()
                })

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

    @api.model
    def sync_all_repositories(self):
        """Sync modules from all marked GitHub repositories"""
        repositories = self.env['github.repository'].search([('odoo_module_repo', '=', True)])
        _logger.info(f"Syncing modules from {len(repositories)} marked repositories")
        
        for repository in repositories:
            self.sync_modules_from_repository(repository.id)