# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
import logging
import os

_logger = logging.getLogger(__name__)


class GitHubRepository(models.Model):
    _inherit = 'github.repository'

    # Module registry fields
    module_ids = fields.One2many('module.registry', 'github_repository_id', 'Modules')
    odoo_module_repo = fields.Boolean('Is Odoo Module Repository', default=False)
    module_count = fields.Integer('Module Count', compute='_compute_module_count', store=True)

    @api.depends('module_ids')
    def _compute_module_count(self):
        for repo in self:
            repo.module_count = len(repo.module_ids)

    def action_sync_modules(self):
        """Action to sync modules from this repository"""
        non_module_repos = self.filtered(lambda r: not r.odoo_module_repo)
        if non_module_repos:
            return self._show_notification(
                'Warning',
                _('Repository "%s" is not marked as an Odoo module repository. Please mark it first.') % non_module_repos[0].full_name,
                'warning',
                sticky=True
            )
        
        for repo in self:
            self.env['module.registry'].sync_modules_from_repository(repo.id)
        
        return self._show_notification(
            'Success',
            _('Module sync completed for %d repositories') % len(self),
            'success'
        )

    def action_mark_as_module_repo(self):
        """Mark repository as Odoo module repository and create library"""
        for repo in self:
            repo.odoo_module_repo = True
            self.env['module.library'].create_library_for_repository(repo.id)
        
        return self._show_notification(
            'Success',
            _('%d repositories marked as Odoo module repositories') % len(self),
            'success'
        )

    def action_unmark_as_module_repo(self):
        """Unmark repository as Odoo module repository"""
        for repo in self:
            repo.odoo_module_repo = False
            repo.module_ids.unlink()
            # Remove library entry
            library = self.env['module.library'].search([('github_repository_id', '=', repo.id)], limit=1)
            if library:
                library.unlink()
        
        return self._show_notification(
            'Success',
            _('%d repositories unmarked and modules removed') % len(self),
            'success'
        )

    def _show_notification(self, title, message, notification_type, sticky=False):
        """Helper method to show notifications"""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _(title),
                'message': message,
                'type': notification_type,
                'sticky': sticky,
            }
        }

    def action_view_modules(self):
        """Action to view modules in this repository"""
        return {
            'name': _('Modules'),
            'type': 'ir.actions.act_window',
            'res_model': 'module.registry',
            'view_mode': 'list,form',
            'domain': [('github_repository_id', '=', self.id)],
            'context': {'default_github_repository_id': self.id}
        }

    def action_force_reclone(self):
        """Force re-clone of this repository"""
        if not self.odoo_module_repo:
            return self._show_notification(
                'Warning',
                _('Repository "%s" is not marked as an Odoo module repository.') % self.full_name,
                'warning'
            )
        
        # Get the local path and remove it
        module_registry = self.env['module.registry']
        repo_path = module_registry._get_repository_local_path(self)
        
        if os.path.exists(repo_path):
            import shutil
            shutil.rmtree(repo_path, ignore_errors=True)
        
        # Trigger sync which will re-clone
        module_registry.sync_modules_from_repository(self.id)
        
        return self._show_notification(
            'Success',
            _('Repository "%s" re-cloning initiated') % self.full_name,
            'success'
        )

    def action_cleanup_local_clone(self):
        """Clean up local clone of this repository"""
        module_registry = self.env['module.registry']
        repo_path = module_registry._get_repository_local_path(self)
        
        if os.path.exists(repo_path):
            import shutil
            shutil.rmtree(repo_path, ignore_errors=True)
            return self._show_notification(
                'Success',
                _('Local clone of "%s" has been removed') % self.full_name,
                'success'
            )
        else:
            return self._show_notification(
                'Info',
                _('No local clone found for "%s"') % self.full_name,
                'info'
            )

    def get_local_clone_info(self):
        """Get information about the local clone of this repository"""
        if not self.odoo_module_repo:
            return {'exists': False, 'reason': 'Not marked as module repository'}
            
        module_registry = self.env['module.registry']
        repo_path = module_registry._get_repository_local_path(self)
        
        if not os.path.exists(repo_path):
            return {'exists': False, 'path': repo_path}
            
        try:
            # Get some basic git info
            import subprocess
            
            # Get last commit info
            result = subprocess.run([
                'git', 'log', '-1', '--format=%H|%s|%an|%ad'
            ], cwd=repo_path, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                commit_info = result.stdout.strip().split('|')
                return {
                    'exists': True,
                    'path': repo_path,
                    'last_commit_hash': commit_info[0][:8] if len(commit_info) > 0 else 'Unknown',
                    'last_commit_message': commit_info[1] if len(commit_info) > 1 else 'Unknown',
                    'last_commit_author': commit_info[2] if len(commit_info) > 2 else 'Unknown',
                    'last_commit_date': commit_info[3] if len(commit_info) > 3 else 'Unknown',
                }
            else:
                return {'exists': True, 'path': repo_path, 'error': 'Could not get git info'}
                
        except Exception as e:
            return {'exists': True, 'path': repo_path, 'error': str(e)}
