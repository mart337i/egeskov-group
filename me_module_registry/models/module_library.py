# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)


class ModuleLibrary(models.Model):
    _name = 'module.library'
    _description = 'Module Library'
    _rec_name = 'name'
    _order = 'name'

    # Library information
    sequence = fields.Integer('Sequence')
    name = fields.Char('Library Name', required=True, index=True)
    description = fields.Text('Description')
    
    # GitHub repository reference
    github_repository_id = fields.Many2one('github.repository', 'GitHub Repository', 
                                         required=True, ondelete='cascade')
    
    # Library settings
    auto_sync = fields.Boolean('Auto Sync', default=False)
    sync_frequency = fields.Selection([
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('manual', 'Manual Only')
    ], 'Sync Frequency', default='manual')
    
    # Templates and versions in this library
    template_ids = fields.One2many('module.template', 'library_id', 'Module Templates')
    version_ids = fields.One2many('module.registry', 'library_id', 'Module Versions')
    module_ids = fields.One2many('module.registry', 'library_id', 'Module Versions')  # Alias for views
    
    # Computed fields
    template_count = fields.Integer('Template Count', compute='_compute_counts', store=True)
    version_count = fields.Integer('Version Count', compute='_compute_counts', store=True)
    module_count = fields.Integer('Module Count', compute='_compute_counts', store=True)
    active_version_count = fields.Integer('Active Versions', compute='_compute_counts', store=True)
    supported_odoo_versions = fields.Char('Supported Odoo Versions', compute='_compute_counts', store=True)
    
    # Sync info
    last_sync = fields.Datetime('Last Sync', compute='_compute_sync_info', store=True)
    sync_status = fields.Selection([
        ('success', 'Success'),
        ('error', 'Error'),
        ('pending', 'Pending'),
        ('never', 'Never Synced')
    ], 'Sync Status', compute='_compute_sync_info', store=True)
    
    # Repository info (related fields)
    repository_name = fields.Char('Repository', related='github_repository_id.full_name', store=True)
    repository_url = fields.Char('Repository URL', related='github_repository_id.html_url', store=True)
    
    _sql_constraints = [
        ('unique_repository', 'unique(github_repository_id)', 
         'Each repository can only have one library entry!'),
    ]

    @api.depends('template_ids', 'version_ids.version_status', 'version_ids.odoo_version_id')
    def _compute_counts(self):
        for library in self:
            versions = library.version_ids
            library.template_count = len(library.template_ids)
            library.version_count = len(versions)
            library.module_count = library.template_count  # Module count = template count (unique modules)
            library.active_version_count = len(versions.filtered(lambda v: v.version_status == 'active'))
            
            # Get supported Odoo versions
            odoo_versions = versions.mapped('odoo_version_id.name')
            library.supported_odoo_versions = ', '.join(sorted(set(filter(None, odoo_versions))))

    @api.depends('template_ids.last_sync', 'version_ids.last_sync')
    def _compute_sync_info(self):
        for library in self:
            # Get all sync dates
            sync_dates = (library.template_ids.mapped('last_sync') + 
                         library.version_ids.mapped('last_sync'))
            library.last_sync = max(filter(None, sync_dates)) if sync_dates else False
            
            # Compute sync status
            if not library.template_ids and not library.version_ids:
                library.sync_status = 'never'
            else:
                all_statuses = (library.template_ids.mapped('sync_status') + 
                              library.version_ids.mapped('sync_status'))
                library.sync_status = self._determine_sync_status(all_statuses)

    def _determine_sync_status(self, statuses):
        """Determine overall sync status from individual statuses"""
        if 'error' in statuses:
            return 'error'
        elif 'pending' in statuses:
            return 'pending'
        elif all(status == 'success' for status in statuses):
            return 'success'
        else:
            return 'pending'

    @api.model
    def create_library_for_repository(self, repository_id):
        """Create a library entry for a repository"""
        repository = self.env['github.repository'].browse(repository_id)
        if not repository.exists():
            return False
            
        existing_library = self.search([('github_repository_id', '=', repository_id)], limit=1)
        if existing_library:
            return existing_library
            
        library_data = {
            'name': f"{repository.full_name} Library",
            'description': f"Module library for {repository.full_name}",
            'github_repository_id': repository_id,
            'auto_sync': False,
            'sync_frequency': 'manual',
        }
        
        return self.create(library_data)

    @api.model
    def update_libraries_from_marked_repositories(self):
        """Create/update library entries for all marked repositories"""
        marked_repos = self.env['github.repository'].search([('odoo_module_repo', '=', True)])
        
        for repo in marked_repos:
            existing_library = self.search([('github_repository_id', '=', repo.id)], limit=1)
            if not existing_library:
                self.create_library_for_repository(repo.id)
        
        # Remove libraries for unmarked repositories
        unmarked_libraries = self.search([('github_repository_id.odoo_module_repo', '=', False)])
        unmarked_libraries.unlink()

    def action_sync_repository(self):
        """Sync modules from the repository"""
        for library in self:
            if library.github_repository_id.odoo_module_repo:
                self.env['module.registry'].sync_modules_from_repository(library.github_repository_id.id)
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Warning'),
                        'message': _('Repository "%s" is not marked as an Odoo module repository.') % library.repository_name,
                        'type': 'warning',
                        'sticky': True,
                    }
                }
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Repository sync completed for %d libraries') % len(self),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_view_templates(self):
        """View module templates in this library"""
        return {
            'name': _('Module Templates in %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'module.template',
            'view_mode': 'list,form',
            'domain': [('library_id', '=', self.id)],
            'context': {'default_library_id': self.id}
        }

    def action_view_versions(self):
        """View module versions in this library"""
        return {
            'name': _('Module Versions in %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'module.registry',
            'view_mode': 'list,form',
            'domain': [('library_id', '=', self.id)],
            'context': {'default_library_id': self.id}
        }

    def action_view_modules(self):
        """View modules in this library (backward compatibility)"""
        return self.action_view_templates()

    def action_open_repository(self):
        """Open repository on GitHub"""
        return {
            'type': 'ir.actions.act_url',
            'url': self.repository_url,
            'target': 'new',
        }

    @api.model
    def sync_auto_libraries(self):
        """Sync libraries that have auto_sync enabled (called by cron)"""
        auto_libraries = self.search([
            ('auto_sync', '=', True),
            ('github_repository_id.odoo_module_repo', '=', True)
        ])
        
        for library in auto_libraries:
            try:
                self.env['module.registry'].sync_modules_from_repository(library.github_repository_id.id)
                _logger.info(f"Auto-synced library: {library.name}")
            except Exception as e:
                _logger.error(f"Error auto-syncing library {library.name}: {str(e)}")

    def toggle_auto_sync(self):
        """Toggle auto sync setting"""
        for library in self:
            library.auto_sync = not library.auto_sync
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Auto sync toggled for %d libraries') % len(self),
                'type': 'success',
                'sticky': False,
            }
        }