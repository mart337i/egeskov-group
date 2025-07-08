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
    sequence = fields.Integer('sequence')
    name = fields.Char(string='Library Name', required=True, index=True, help='Name for this module library/collection')
    description = fields.Text(string='Description', help='Description of this module library')
    
    # GitHub repository reference
    github_repository_id = fields.Many2one('github.repository', string='GitHub Repository', required=True, ondelete='cascade')
    
    # Library settings
    auto_sync = fields.Boolean(string='Auto Sync', default=False, help='Automatically sync modules from repository during cron jobs')
    sync_frequency = fields.Selection([
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('manual', 'Manual Only')
    ], string='Sync Frequency', default='manual', help='How often to sync this library')
    
    # Modules in this library
    module_ids = fields.One2many('module.registry', 'library_id', string='Modules')
    
    # Computed fields
    module_count = fields.Integer(string='Module Count', compute='_compute_module_count', store=True)
    last_sync = fields.Datetime(string='Last Sync', compute='_compute_last_sync', store=True)
    sync_status = fields.Selection([
        ('success', 'Success'),
        ('error', 'Error'),
        ('pending', 'Pending'),
        ('never', 'Never Synced')
    ], string='Sync Status', compute='_compute_sync_status', store=True)
    
    # Repository info (related fields for convenience)
    repository_name = fields.Char(string='Repository', related='github_repository_id.full_name', store=True)
    repository_url = fields.Char(string='Repository URL', related='github_repository_id.html_url', store=True)
    
    _sql_constraints = [
        ('unique_repository', 'unique(github_repository_id)', 
         'Each repository can only have one library entry!'),
    ]

    @api.depends('module_ids')
    def _compute_module_count(self):
        for library in self:
            library.module_count = len(library.module_ids)

    @api.depends('module_ids.last_sync')
    def _compute_last_sync(self):
        for library in self:
            if library.module_ids:
                library.last_sync = max(library.module_ids.mapped('last_sync') or [fields.Datetime.now()])
            else:
                library.last_sync = False

    @api.depends('module_ids.sync_status')
    def _compute_sync_status(self):
        for library in self:
            if not library.module_ids:
                library.sync_status = 'never'
            else:
                statuses = library.module_ids.mapped('sync_status')
                if 'error' in statuses:
                    library.sync_status = 'error'
                elif 'pending' in statuses:
                    library.sync_status = 'pending'
                elif all(status == 'success' for status in statuses):
                    library.sync_status = 'success'
                else:
                    library.sync_status = 'pending'

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

    def action_view_modules(self):
        """View modules in this library"""
        return {
            'name': _('Modules in %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'module.registry',
            'view_mode': 'tree,form',
            'domain': [('library_id', '=', self.id)],
            'context': {'default_library_id': self.id}
        }

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