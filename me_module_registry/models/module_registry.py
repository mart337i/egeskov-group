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
    _description = 'Module Version (Specific Version Information)'
    _rec_name = 'display_name'
    _order = 'template_id, version desc'

    # Link to template (static information)
    template_id = fields.Many2one('module.template', string='Module Template', required=True, ondelete='cascade', index=True)
    
    # Version-specific information (from GitHub API - readonly)
    sequence = fields.Integer('Sequence')
    version = fields.Char(string='Module Version', required=True, readonly=True, help='Version from GitHub manifest', index=True)
    odoo_version_id = fields.Many2one('odoo.version', string='Odoo Version', readonly=True, help='Extracted from version in GitHub manifest')
    
    # Version tracking and lifecycle management (editable)
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
    
    # Version-specific manifest data (from GitHub manifest - readonly)
    manifest_data = fields.Json(string='Full Manifest Data', readonly=True, help='Complete manifest from GitHub')
    
    # Module status and compatibility (version-specific, from GitHub manifest - readonly)
    installable = fields.Boolean(string='Installable', default=True, readonly=True, help='From GitHub manifest')
    auto_install = fields.Boolean(string='Auto Install', default=False, readonly=True, help='From GitHub manifest')
    
    # GitHub integration (readonly - managed by system)
    github_repository_id = fields.Many2one('github.repository', string='GitHub Repository', related='template_id.github_repository_id', store=True, readonly=True)
    library_id = fields.Many2one('module.library', string='Module Library', related='template_id.library_id', store=True, readonly=True)
    github_branch = fields.Char(string='GitHub Branch', readonly=True, help='Branch where this module version is found')
    manifest_url = fields.Char(string='Manifest URL', readonly=True, help='Direct URL to __manifest__.py file')
    readme_url = fields.Char(string='README URL', readonly=True, help='Direct URL to README file')
    
    # Template-related computed fields (for easy access)
    name = fields.Char(string='Module Name', related='template_id.name', readonly=True)
    technical_name = fields.Char(string='Technical Name', related='template_id.technical_name', readonly=True)
    summary = fields.Text(string='Summary', related='template_id.summary', readonly=True)
    description = fields.Html(string='Description', related='template_id.description', readonly=True)
    author = fields.Char(string='Author', related='template_id.author', readonly=True)
    website = fields.Char(string='Website', related='template_id.website', readonly=True)
    license = fields.Char(string='License', related='template_id.license', readonly=True)
    category = fields.Char(string='Category', related='template_id.category', readonly=True)
    application = fields.Boolean(string='Application', related='template_id.application', readonly=True)
    github_path = fields.Char(string='Path in Repository', related='template_id.github_path', readonly=True)
    
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

    @api.depends('template_id', 'github_branch', 'version', 'major_version')
    def _compute_version_analysis(self):
        for version in self:
            if not version.template_id:
                version.is_latest_version = False
                version.has_newer_version = False
                version.newer_versions_count = 0
                version.version_family_count = 0
                continue
                
            # Find all versions of this template in the same branch
            branch_versions = self.search([
                ('template_id', '=', version.template_id.id),
                ('github_branch', '=', version.github_branch)
            ])
            
            # Find all versions across all branches for family count
            all_versions = self.search([
                ('template_id', '=', version.template_id.id)
            ])
            
            version.version_family_count = len(all_versions)
            
            if not version.version:
                version.is_latest_version = False
                version.has_newer_version = False
                version.newer_versions_count = 0
                continue
            
            # Compare versions within the same branch to find if this is the latest
            current_version_tuple = version._parse_version_for_comparison(version.version)
            newer_versions = []
            
            for other_version in branch_versions:
                if other_version.id != version.id and other_version.version:
                    other_version_tuple = version._parse_version_for_comparison(other_version.version)
                    if other_version_tuple > current_version_tuple:
                        newer_versions.append(other_version)
            
            version.newer_versions_count = len(newer_versions)
            version.has_newer_version = len(newer_versions) > 0
            version.is_latest_version = len(newer_versions) == 0

    def _compute_all_versions(self):
        for version in self:
            if version.template_id:
                all_versions = self.search([
                    ('template_id', '=', version.template_id.id)
                ])
                version.all_versions_ids = all_versions
            else:
                version.all_versions_ids = self.browse()

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
        """Sync all modules from a GitHub repository across multiple branches"""
        repository = self.env['github.repository'].browse(repository_id)
        if not repository.exists():
            return False
            
        if not repository.odoo_module_repo:
            _logger.warning(f"Repository {repository.full_name} is not marked as an Odoo module repository. Skipping sync.")
            return False

        github_token = self.env['ir.config_parameter'].sudo().get_param('github_integration.token')
        
        try:
            # Get all branches from the repository
            branches = self._get_repository_branches(repository, github_token)
            _logger.info(f"Found {len(branches)} branches in repository {repository.full_name}")
            
            total_modules = 0
            for branch in branches:
                modules_found = self._discover_modules_in_repository_branch(repository, branch, github_token)
                _logger.info(f"Found {len(modules_found)} modules in branch {branch} of repository {repository.full_name}")
                
                for module_data in modules_found:
                    module_data['github_branch'] = branch
                    self._create_or_update_module(module_data, repository)
                
                total_modules += len(modules_found)
            
            _logger.info(f"Total modules synced: {total_modules} across {len(branches)} branches")
            return True
        except Exception as e:
            _logger.error(f"Error syncing modules from repository {repository.full_name}: {str(e)}")
            return False

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
            odoo_version_match = re.match(r'^(\\d+\\.\\d+)', version_str)
            odoo_version = odoo_version_match.group(1) if odoo_version_match else '18.0'
            
            # Use branch or default branch for URLs
            url_branch = branch or repository.default_branch
            
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
                'readme_url': f"{repository.html_url}/blob/{url_branch}/{module_path}/README.md",
            }
            
            return module_data
            
        except Exception as e:
            _logger.error(f"Error parsing manifest for {module_path} in branch {branch}: {str(e)}")
            return None

    def _create_or_update_module(self, module_data, repository):
        """Create or update a module version record"""
        try:
            # Find or create Odoo version record
            odoo_version = self.env['odoo.version'].search([('name', '=', module_data['odoo_version'])], limit=1)
            if not odoo_version:
                odoo_version = self.env['odoo.version'].create({
                    'name': module_data['odoo_version']
                })
            
            # Find or create module template
            template = self.env['module.template'].find_or_create_template(module_data, repository)
            
            # Prepare version-specific data
            version_data = {
                'template_id': template.id,
                'version': module_data['version'],
                'odoo_version_id': odoo_version.id,
                'github_branch': module_data.get('github_branch', repository.default_branch),
                'installable': module_data.get('installable', True),
                'auto_install': module_data.get('auto_install', False),
                'manifest_data': module_data.get('manifest_data', {}),
                'manifest_url': module_data.get('manifest_url', ''),
                'readme_url': module_data.get('readme_url', ''),
                'last_sync': fields.Datetime.now(),
                'sync_status': 'success',
                'sync_error': False,
            }
            
            # Version-specific dependencies and files
            version_data.update({
                'depends': module_data.get('depends', '[]'),
                'external_dependencies': module_data.get('external_dependencies', '{}'),
                'data_files': module_data.get('data_files', '[]'),
                'demo_files': module_data.get('demo_files', '[]'),
                'assets': module_data.get('assets', '{}'),
            })
            
            existing_version = self.search([
                ('template_id', '=', template.id),
                ('github_branch', '=', module_data.get('github_branch', repository.default_branch)),
                ('version', '=', module_data['version'])
            ], limit=1)
            
            if existing_version:
                existing_version.write(version_data)
                _logger.info(f"Updated version {module_data['technical_name']} v{module_data['version']} from {repository.full_name} ({module_data.get('github_branch', 'default')})")
            else:
                self.create(version_data)
                _logger.info(f"Created version {module_data['technical_name']} v{module_data['version']} from {repository.full_name} ({module_data.get('github_branch', 'default')})")
                
        except Exception as e:
            _logger.error(f"Error creating/updating module version {module_data.get('technical_name', 'unknown')}: {str(e)}")
            # Try to create error record if template exists
            try:
                template = self.env['module.template'].search([
                    ('technical_name', '=', module_data['technical_name']),
                    ('github_repository_id', '=', repository.id)
                ], limit=1)
                
                if template:
                    existing_version = self.search([
                        ('template_id', '=', template.id),
                        ('github_branch', '=', module_data.get('github_branch', repository.default_branch)),
                        ('version', '=', module_data.get('version', ''))
                    ], limit=1)
                    
                    if existing_version:
                        existing_version.write({
                            'sync_status': 'error',
                            'sync_error': str(e),
                            'last_sync': fields.Datetime.now()
                        })
            except Exception as inner_e:
                _logger.error(f"Error updating error status: {str(inner_e)}")

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