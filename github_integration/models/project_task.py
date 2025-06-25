from odoo import models, fields

class ProjectTask(models.Model):
    _inherit = 'project.task'
    
    def action_open_github_repo(self):
        """Open GitHub repository in new tab"""
        if self.project_id.github_repo_url:
            return {
                'type': 'ir.actions.act_url',
                'url': self.project_id.github_repo_url,
                'target': 'new',
            }