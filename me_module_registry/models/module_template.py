# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
import logging
import json
import re

_logger = logging.getLogger(__name__)


class ModuleTemplate(models.Model):
    _name = 'module.template'
    _description = 'Module Template (Static Information)'
    _rec_name = 'name'
    _order = 'name'

    # Basic module information (static across versions)
    sequence = fields.Integer('Sequence')
    name = fields.Char('Module Name', required=True, index=True, readonly=True)
    technical_name = fields.Char('Technical Name', required=True, index=True, readonly=True)
    summary = fields.Text('Summary', readonly=True)
    description = fields.Html('Description', readonly=True)
    author = fields.Char('Author', readonly=True)
    website = fields.Char('Website', readonly=True)
    license = fields.Char('License', readonly=True)
    category = fields.Char('Category', default='Uncategorized', readonly=True)
    application = fields.Boolean('Application', default=False, readonly=True)
    
    # GitHub integration
    github_repository_id = fields.Many2one('github.repository', 'GitHub Repository', 
                                         ondelete='cascade', required=True, readonly=True)
    library_id = fields.Many2one('module.library', 'Module Library', 
                               ondelete='cascade', readonly=True)
    github_path = fields.Char('Path in Repository', readonly=True)
    
    # Relationships
    version_ids = fields.One2many('module.registry', 'template_id', 'Versions')
    
    # Computed fields
    full_name = fields.Char('Full Name', compute='_compute_full_name', store=True)
    github_url = fields.Char('GitHub URL', compute='_compute_github_url', store=True)
    version_count = fields.Integer('Version Count', compute='_compute_version_stats', store=True)
    latest_version_id = fields.Many2one('module.registry', 'Latest Version', 
                                      compute='_compute_version_stats', store=True)
    active_versions_count = fields.Integer('Active Versions', compute='_compute_version_stats', store=True)
    supported_odoo_versions = fields.Char('Supported Odoo Versions', 
                                        compute='_compute_version_stats', store=True)
    odoo_version_ids = fields.Many2many('odoo.version', compute='_compute_odoo_versions', 
                                       string='Odoo Versions', store=True)
    
    # Sync metadata
    last_sync = fields.Datetime('Last Sync', default=fields.Datetime.now, readonly=True)
    sync_status = fields.Selection([
        ('success', 'Success'),
        ('error', 'Error'),
        ('pending', 'Pending')
    ], 'Sync Status', default='pending', readonly=True)
    sync_error = fields.Text('Sync Error', readonly=True)
    
    _sql_constraints = [
        ('unique_technical_name_repo', 'unique(technical_name, github_repository_id)', 
         'Technical name must be unique per repository!'),
    ]

    @api.depends('github_repository_id', 'github_path')
    def _compute_github_url(self):
        for template in self:
            repo = template.github_repository_id
            template.github_url = (f"{repo.html_url}/tree/{repo.default_branch}/{template.github_path}" 
                                 if repo and template.github_path else False)

    @api.depends('name', 'technical_name', 'github_repository_id')
    def _compute_full_name(self):
        for template in self:
            repo = template.github_repository_id
            template.full_name = (f"{repo.full_name}/{template.technical_name}" if repo 
                                else template.technical_name or template.name)

    @api.depends('version_ids.version_status', 'version_ids.version', 'version_ids.odoo_version_id')
    def _compute_version_stats(self):
        """
        Compute and update statistics for module versions, including total count, active count, latest version, and supported Odoo versions.
        
        Updates the following fields for each module template:
        - `version_count`: Total number of related versions.
        - `active_versions_count`: Number of versions with status 'active'.
        - `latest_version_id`: The most recent version, determined by parsed version string.
        - `supported_odoo_versions`: Comma-separated list of unique Odoo version names supported by the module.
        """
        for template in self:
            versions = template.version_ids
            template.version_count = len(versions)
            
            # Count active versions
            active_versions = versions.filtered(lambda v: v.version_status == 'active')
            template.active_versions_count = len(active_versions)
            
            # Find latest version
            template.latest_version_id = (versions.sorted(
                key=lambda v: self._parse_version(v.version), 
                reverse=True)[0].id if versions else False)
            
            # Get supported Odoo versions
            odoo_versions = versions.mapped('odoo_version_id.name')
            template.supported_odoo_versions = ', '.join(sorted(set(filter(None, odoo_versions))))

    @api.depends('version_ids.odoo_version_id')
    def _compute_odoo_versions(self):
        """
        Compute and assign the set of Odoo versions associated with each module template based on its related versions.
        """
        for template in self:
            template.odoo_version_ids = template.version_ids.mapped('odoo_version_id')

    def _parse_version(self, version_str):
        """
        Parses a version string into a tuple of integers for reliable version comparison.
        
        The returned tuple consists of up to four numeric components, padded with zeros if necessary, and a fifth element indicating pre-release status (-1 for pre-release, 0 for final release). Non-numeric or missing version strings result in a tuple of zeros.
        
        Returns:
            tuple: A 5-element tuple representing the parsed version for comparison.
        """
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

    def action_open_github(self):
        """Open module on GitHub"""
        return {
            'type': 'ir.actions.act_url',
            'url': self.github_url,
            'target': 'new',
        }

    def action_view_versions(self):
        """View all versions of this module template"""
        return {
            'name': _('Versions of %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'module.registry',
            'view_mode': 'list,form',
            'domain': [('template_id', '=', self.id)],
            'context': {'default_template_id': self.id}
        }

    @api.model
    def find_or_create_template(self, module_data, repository):
        """Find or create a module template"""
        template = self.search([
            ('technical_name', '=', module_data['technical_name']),
            ('github_repository_id', '=', repository.id)
        ], limit=1)
        
        # Prepare template data
        template_data = self._prepare_template_data(module_data, repository)
        
        if template:
            template.write(template_data)
            _logger.info(f"Updated template for module {module_data['technical_name']} from {repository.full_name}")
        else:
            template = self.create(template_data)
            _logger.info(f"Created template for module {module_data['technical_name']} from {repository.full_name}")
        
        return template

    def _prepare_template_data(self, module_data, repository):
        """Prepare template data from module data"""
        # Find or create library for this repository
        library = self.env['module.library'].search([('github_repository_id', '=', repository.id)], limit=1)
        if not library:
            library = self.env['module.library'].create_library_for_repository(repository.id)
        
        return {
            'technical_name': module_data['technical_name'],
            'name': module_data['name'],
            'summary': module_data.get('summary', ''),
            'description': module_data.get('description', ''),
            'author': module_data.get('author', ''),
            'website': module_data.get('website', ''),
            'license': module_data.get('license', ''),
            'category': module_data.get('category', 'Uncategorized'),
            'application': module_data.get('application', False),
            'github_repository_id': repository.id,
            'library_id': library.id,
            'github_path': module_data['github_path'],
            'last_sync': fields.Datetime.now(),
            'sync_status': 'success',
            'sync_error': False,
        }