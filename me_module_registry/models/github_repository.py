# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)


class GitHubRepository(models.Model):
    _inherit = 'github.repository'

    # Module registry fields
    module_ids = fields.One2many('module.registry', 'github_repository_id', string='Modules')
    odoo_module_repo = fields.Boolean(string='Is Odoo Module Repository', default=False, help='Mark this repository as containing Odoo modules to enable module scanning')
    module_count = fields.Integer(string='Module Count', compute='_compute_module_count', store=True)

    @api.depends('module_ids')
    def _compute_module_count(self):
        for repo in self:
            repo.module_count = len(repo.module_ids)

    def action_sync_modules(self):
        """Action to sync modules from this repository"""
        synced_count = 0
        for repo in self:
            if repo.odoo_module_repo:
                self.env['module.registry'].sync_modules_from_repository(repo.id)
                synced_count += 1
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Warning'),
                        'message': _('Repository "%s" is not marked as an Odoo module repository. Please mark it first.') % repo.full_name,
                        'type': 'warning',
                        'sticky': True,
                    }
                }
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Module sync completed for %d repositories') % synced_count,
                'type': 'success',
                'sticky': False,
            }
        }

    def action_mark_as_module_repo(self):
        """Mark repository as Odoo module repository and create library"""
        for repo in self:
            repo.odoo_module_repo = True
            # Create library entry for this repository
            self.env['module.library'].create_library_for_repository(repo.id)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('%d repositories marked as Odoo module repositories') % len(self),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_unmark_as_module_repo(self):
        """Unmark repository as Odoo module repository"""
        for repo in self:
            repo.odoo_module_repo = False
            # Remove modules from registry
            repo.module_ids.unlink()
            # Remove library entry
            library = self.env['module.library'].search([('github_repository_id', '=', repo.id)], limit=1)
            if library:
                library.unlink()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('%d repositories unmarked and modules removed') % len(self),
                'type': 'success',
                'sticky': False,
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
