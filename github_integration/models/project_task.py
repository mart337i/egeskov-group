from odoo import models, fields, api

class ProjectTask(models.Model):
    _inherit = 'project.task'
    
    github_branch_id = fields.Many2one(
        'github.branch',
        string='GitHub Branch',
        help='Branch associated with this task'
    )
    
    available_branches = fields.One2many(
        'github.branch', 
        compute='_compute_available_branches',
        string='Available Branches'
    )
    
    @api.depends('project_id', 'project_id.github_repository_id')
    def _compute_available_branches(self):
        """Compute available branches for the project"""
        for task in self:
            if task.project_id and task.project_id.github_repository_id:
                task.available_branches = self.env['github.branch'].search([
                    ('repository_id', '=', task.project_id.github_repository_id.id)
                ])
            else:
                task.available_branches = self.env['github.branch']

    @api.onchange('project_id')
    def _onchange_project_id(self):
        if self.project_id and self.github_branch_id:
            if not self.project_id.github_repository_id or \
               self.github_branch_id.repository_id != self.project_id.github_repository_id:
                self.github_branch_id = False
        
        # Return domain for github_branch_id
        if self.project_id and self.project_id.github_repository_id:
            return {
                'domain': {
                    'github_branch_id': [('repository_id', '=', self.project_id.github_repository_id.id)]
                }
            }
        else:
            return {
                'domain': {
                    'github_branch_id': [('id', '=', False)]
                }
            }

    def action_open_github_repo(self):
        """Open GitHub repository in new tab"""
        if self.project_id.github_repo_url:
            return {
                'type': 'ir.actions.act_url',
                'url': self.project_id.github_repo_url,
                'target': 'new',
            }
    
    def action_open_github_branch(self):
        """Open GitHub branch in new tab"""
        if self.project_id.github_repo_url and self.github_branch_id:
            branch_url = f"{self.project_id.github_repo_url}/tree/{self.github_branch_id.name}"
            return {
                'type': 'ir.actions.act_url',
                'url': branch_url,
                'target': 'new',
            }
    
    def action_refresh_project_branches(self):
        """Refresh branches for the current project"""
        if self.project_id and self.project_id.github_repository_id:
            self.env['github.branch'].fetch_branches_for_repository(self.project_id.github_repository_id.id)
            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
            }