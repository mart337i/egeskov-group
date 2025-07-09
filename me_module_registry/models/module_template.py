# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
import logging
import json

_logger = logging.getLogger(__name__)


class ModuleTemplate(models.Model):
    _name = 'module.template'
    _description = 'Module Template (Static Information)'
    _rec_name = 'name'
    _order = 'name'

    # Basic module information (static across versions)
    sequence = fields.Integer('Sequence')
    name = fields.Char(string='Module Name', required=True, index=True, readonly=True, help='From GitHub manifest')
    technical_name = fields.Char(string='Technical Name', required=True, index=True, readonly=True, help='From GitHub repository structure')
    summary = fields.Text(string='Summary', readonly=True, help='From GitHub manifest')
    description = fields.Html(string='Description', readonly=True, help='From GitHub manifest')
    author = fields.Char(string='Author', readonly=True, help='From GitHub manifest')
    website = fields.Char(string='Website', readonly=True, help='From GitHub manifest')
    license = fields.Char(string='License', readonly=True, help='From GitHub manifest')
    category = fields.Char(string='Category', default='Uncategorized', readonly=True, help='From GitHub manifest')
    
    # Module type and characteristics (static)
    application = fields.Boolean(string='Application', default=False, readonly=True, help='From GitHub manifest')
    
    # GitHub integration (readonly - managed by system)
    github_repository_id = fields.Many2one('github.repository', string='GitHub Repository', ondelete='cascade', required=True, readonly=True)
    library_id = fields.Many2one('module.library', string='Module Library', ondelete='cascade', readonly=True)
    github_path = fields.Char(string='Path in Repository', readonly=True, help='Path to module directory in repository')
    
    # Relationships
    version_ids = fields.One2many('module.registry', 'template_id', string='Versions')
    
    # Computed fields
    full_name = fields.Char(string='Full Name', compute='_compute_full_name', store=True)
    github_url = fields.Char(string='GitHub URL', compute='_compute_github_url', store=True)
    version_count = fields.Integer(string='Version Count', compute='_compute_version_stats', store=True)
    latest_version_id = fields.Many2one('module.registry', string='Latest Version', compute='_compute_version_stats', store=True)
    active_versions_count = fields.Integer(string='Active Versions', compute='_compute_version_stats', store=True)
    supported_odoo_versions = fields.Char(string='Supported Odoo Versions', compute='_compute_version_stats', store=True)
    
    # Metadata (system managed - readonly)
    last_sync = fields.Datetime(string='Last Sync', default=fields.Datetime.now, readonly=True)
    sync_status = fields.Selection([
        ('success', 'Success'),
        ('error', 'Error'),
        ('pending', 'Pending')
    ], string='Sync Status', default='pending', readonly=True)
    sync_error = fields.Text(string='Sync Error', readonly=True)
    
    _sql_constraints = [
        ('unique_technical_name_repo', 'unique(technical_name, github_repository_id)', 
         'Technical name must be unique per repository!'),
    ]

    @api.depends('github_repository_id', 'github_path')
    def _compute_github_url(self):
        for template in self:
            if template.github_repository_id and template.github_path:
                template.github_url = f"{template.github_repository_id.html_url}/tree/{template.github_repository_id.default_branch}/{template.github_path}"
            else:
                template.github_url = False

    @api.depends('name', 'technical_name', 'github_repository_id')
    def _compute_full_name(self):
        for template in self:
            if template.github_repository_id:
                template.full_name = f"{template.github_repository_id.full_name}/{template.technical_name}"
            else:
                template.full_name = template.technical_name or template.name

    @api.depends('version_ids', 'version_ids.version_status', 'version_ids.version', 'version_ids.odoo_version_id')
    def _compute_version_stats(self):
        for template in self:
            versions = template.version_ids
            template.version_count = len(versions)
            
            # Count active versions
            active_versions = versions.filtered(lambda v: v.version_status == 'active')
            template.active_versions_count = len(active_versions)
            
            # Find latest version (by version number)
            if versions:
                latest = versions.sorted(key=lambda v: template._parse_version_for_comparison(v.version or '0.0.0.0'), reverse=True)[0]
                template.latest_version_id = latest.id
            else:
                template.latest_version_id = False
            
            # Get supported Odoo versions
            odoo_versions = versions.mapped('odoo_version_id.name')
            template.supported_odoo_versions = ', '.join(sorted(set(odoo_versions))) if odoo_versions else ''

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
        
        if not template:
            # Find or create library for this repository
            library = self.env['module.library'].search([('github_repository_id', '=', repository.id)], limit=1)
            if not library:
                library = self.env['module.library'].create_library_for_repository(repository.id)
            
            template_data = {
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
            
            template = self.create(template_data)
            _logger.info(f"Created template for module {module_data['technical_name']} from {repository.full_name}")
        else:
            # Update template with latest information (in case static info changed)
            template_data = {
                'name': module_data['name'],
                'summary': module_data.get('summary', ''),
                'description': module_data.get('description', ''),
                'author': module_data.get('author', ''),
                'website': module_data.get('website', ''),
                'license': module_data.get('license', ''),
                'category': module_data.get('category', 'Uncategorized'),
                'application': module_data.get('application', False),
                'github_path': module_data['github_path'],
                'last_sync': fields.Datetime.now(),
                'sync_status': 'success',
                'sync_error': False,
            }
            template.write(template_data)
            _logger.info(f"Updated template for module {module_data['technical_name']} from {repository.full_name}")
        
        return template