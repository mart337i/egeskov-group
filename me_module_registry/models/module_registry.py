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

    # Basic module information (from GitHub API - readonly)
    sequence = fields.Integer('sequence')
    name = fields.Char(string='Module Name', required=True, index=True, readonly=True, help='From GitHub manifest')
    technical_name = fields.Char(string='Technical Name', required=True, index=True, readonly=True, help='From GitHub repository structure')
    version = fields.Char(string='Module Version', readonly=True, help='Version from GitHub manifest')
    odoo_version_id = fields.Many2one('odoo.version', string='Odoo Version', readonly=True, help='Extracted from version in GitHub manifest')
    
    # Version tracking
    major_version = fields.Char(string='Major Version', compute='_compute_version_parts', store=True, index=True)
    minor_version = fields.Char(string='Minor Version', compute='_compute_version_parts', store=True)
    patch_version = fields.Char(string='Patch Version', compute='_compute_version_parts', store=True)
    version_status = fields.Selection([
        ('active', 'Active'),
        ('deprecated', 'Deprecated'),
        ('obsolete', 'Obsolete'),
        ('migration_needed', 'Migration Needed'),
        ('beta', 'Beta'),
        ('alpha', 'Alpha')
    ], string='Version Status', default='active', help='Status of this module version')
    deprecation_date = fields.Date(string='Deprecation Date', help='Date when this version was deprecated')
    end_of_life_date = fields.Date(string='End of Life Date', help='Date when support ends for this version')
    summary = fields.Text(string='Summary', readonly=True, help='From GitHub manifest')
    description = fields.Html(string='Description', readonly=True, help='From GitHub manifest')
    author = fields.Char(string='Author', readonly=True, help='From GitHub manifest')
    website = fields.Char(string='Website', readonly=True, help='From GitHub manifest')
    license = fields.Char(string='License', readonly=True, help='From GitHub manifest')
    category = fields.Char(string='Category', default='Uncategorized', readonly=True, help='From GitHub manifest')
    manifest_data = fields.Json(string='Full Manifest Data', readonly=True, help='Complete manifest from GitHub')
    
    # Module status and compatibility (from GitHub manifest - readonly)
    installable = fields.Boolean(string='Installable', default=True, readonly=True, help='From GitHub manifest')
    auto_install = fields.Boolean(string='Auto Install', default=False, readonly=True, help='From GitHub manifest')
    application = fields.Boolean(string='Application', default=False, readonly=True, help='From GitHub manifest')
    
    # GitHub integration (readonly - managed by system)
    github_repository_id = fields.Many2one('github.repository', string='GitHub Repository', ondelete='cascade', required=True, readonly=True)
    library_id = fields.Many2one('module.library', string='Module Library', ondelete='cascade', readonly=True)
    github_path = fields.Char(string='Path in Repository', readonly=True, help='Path to module directory in repository')
    manifest_url = fields.Char(string='Manifest URL', readonly=True, help='Direct URL to __manifest__.py file')
    readme_url = fields.Char(string='README URL', readonly=True, help='Direct URL to README file')
    
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
    full_name = fields.Char(string='Full Name', compute='_compute_full_name', store=True)
    github_url = fields.Char(string='GitHub URL', compute='_compute_github_url', store=True)
    
    # Version analysis computed fields
    is_latest_version = fields.Boolean(string='Is Latest Version', compute='_compute_version_analysis', store=True)
    has_newer_version = fields.Boolean(string='Has Newer Version', compute='_compute_version_analysis', store=True)
    newer_versions_count = fields.Integer(string='Newer Versions Count', compute='_compute_version_analysis', store=True)
    all_versions_ids = fields.Many2many('module.registry', compute='_compute_all_versions', string='All Versions')
    version_family_count = fields.Integer(string='Version Family Count', compute='_compute_version_analysis', store=True)
    
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

    @api.depends('version')
    def _compute_version_parts(self):
        for module in self:
            if module.version:
                # Parse version string (e.g., "18.0.1.2.3" -> major: "18.0", minor: "1", patch: "2.3")
                version_parts = module.version.split('.')
                if len(version_parts) >= 2:
                    module.major_version = f"{version_parts[0]}.{version_parts[1]}"
                    module.minor_version = version_parts[2] if len(version_parts) > 2 else '0'
                    module.patch_version = '.'.join(version_parts[3:]) if len(version_parts) > 3 else '0'
                else:
                    module.major_version = module.version
                    module.minor_version = '0'
                    module.patch_version = '0'
            else:
                module.major_version = '0.0'
                module.minor_version = '0'
                module.patch_version = '0'

    @api.depends('technical_name', 'github_repository_id', 'version', 'major_version')
    def _compute_version_analysis(self):
        for module in self:
            if not module.technical_name or not module.github_repository_id:
                module.is_latest_version = False
                module.has_newer_version = False
                module.newer_versions_count = 0
                module.version_family_count = 0
                continue
                
            # Find all versions of this module in the same repository
            all_versions = self.search([
                ('technical_name', '=', module.technical_name),
                ('github_repository_id', '=', module.github_repository_id.id)
            ])
            
            module.version_family_count = len(all_versions)
            
            if not module.version:
                module.is_latest_version = False
                module.has_newer_version = False
                module.newer_versions_count = 0
                continue
            
            # Compare versions to find if this is the latest
            current_version_tuple = module._parse_version_for_comparison(module.version)
            newer_versions = []
            
            for other_version in all_versions:
                if other_version.id != module.id and other_version.version:
                    other_version_tuple = module._parse_version_for_comparison(other_version.version)
                    if other_version_tuple > current_version_tuple:
                        newer_versions.append(other_version)
            
            module.newer_versions_count = len(newer_versions)
            module.has_newer_version = len(newer_versions) > 0
            module.is_latest_version = len(newer_versions) == 0

    def _compute_all_versions(self):
        for module in self:
            if module.technical_name and module.github_repository_id:
                all_versions = self.search([
                    ('technical_name', '=', module.technical_name),
                    ('github_repository_id', '=', module.github_repository_id.id)
                ])
                module.all_versions_ids = all_versions
            else:
                module.all_versions_ids = self.browse()

    def _parse_version_for_comparison(self, version_str):
        """Parse version string into tuple for comparison"""
        if not version_str:
            return (0, 0, 0, 0)
        
        parts = version_str.split('.')
        # Pad with zeros to ensure consistent comparison
        while len(parts) < 4:
            parts.append('0')
        
        try:
            return tuple(int(part) for part in parts[:4])
        except ValueError:
            # If conversion fails, treat as 0
            return (0, 0, 0, 0)

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

    def action_view_all_versions(self):
        """View all versions of this module"""
        return {
            'name': _('All Versions of %s') % self.technical_name,
            'type': 'ir.actions.act_window',
            'res_model': 'module.registry',
            'view_mode': 'list,form',
            'domain': [
                ('technical_name', '=', self.technical_name),
                ('github_repository_id', '=', self.github_repository_id.id)
            ],
            'context': {'default_technical_name': self.technical_name}
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