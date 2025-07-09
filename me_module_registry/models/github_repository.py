# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
import logging

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
