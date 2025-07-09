from odoo import models, fields, api

class ProjectTask(models.Model):
    _inherit = 'project.task'
    
    github_branch_id = fields.Many2one(
        'github.branch',
        string='GitHub Branch',
        help='Branch associated with this task'
    )
    

    

    
    # Related fields for easier access in views
    github_repository_id = fields.Many2one(
        'github.repository',
        related='github_branch_id.repository_id',
        string='GitHub Repository',
        readonly=True
    )
    
    github_repository_url = fields.Char(
        related='github_branch_id.repository_id.html_url',
        string='Repository URL',
        readonly=True
    )
    
    github_branch_name = fields.Char(
        related='github_branch_id.name',
        string='Branch Name',
        readonly=True
    )
    
    # Project repository related fields
    project_repository_count = fields.Integer(
        related='project_id.repository_count',
        string='Project Repository Count',
        readonly=True
    )
    
    project_repository_names = fields.Char(
        related='project_id.all_repository_names',
        string='Project Repository Names',
        readonly=True
    )
    
    project_has_repositories = fields.Boolean(
        compute='_compute_project_has_repositories',
        string='Project Has Repositories'
    )
    
    # Field to store repository IDs for domain filtering
    project_repository_ids = fields.Many2many(
        'github.repository',
        related='project_id.github_repository_ids',
        string='Project Repository IDs',
        readonly=True
    )
    

    

    
    @api.depends('project_id', 'project_id.github_repository_ids')
    def _compute_project_has_repositories(self):
        """Compute if project has repositories"""
        for task in self:
            task.project_has_repositories = bool(task.project_id and task.project_id.github_repository_ids)

    @api.onchange('project_id')
    def _onchange_project_id(self):
        if self.project_id and self.github_branch_id:
            # Check if the selected branch belongs to any of the project's repositories
            project_repos = self.project_id.github_repository_ids
            if not project_repos or self.github_branch_id.repository_id not in project_repos:
                self.github_branch_id = False
        
        # Return domain for github_branch_id (all repositories in the project)
        if self.project_id and self.project_id.github_repository_ids:
            project_repos = self.project_id.github_repository_ids
            repo_ids = project_repos.ids
            if repo_ids:
                return {
                    'domain': {
                        'github_branch_id': [('repository_id', 'in', repo_ids)]
                    }
                }
        
        return {
            'domain': {
                'github_branch_id': [('id', '=', False)]
            }
        }


    def action_open_github_repo(self):
        """Open GitHub repository in new tab"""
        # If there's a selected branch, open its repository
        if self.github_branch_id and self.github_branch_id.repository_id:
            return {
                'type': 'ir.actions.act_url',
                'url': self.github_branch_id.repository_id.html_url,
                'target': 'new',
            }
        # If project has repositories, show selection or open single repo
        elif self.project_id and self.project_id.github_repository_ids:
            project_repos = self.project_id.github_repository_ids
            if len(project_repos) == 1:
                return {
                    'type': 'ir.actions.act_url',
                    'url': project_repos[0].html_url,
                    'target': 'new',
                }
            else:
                return self.project_id.action_view_all_repositories()
    
    def action_open_github_branch(self):
        """Open GitHub branch in new tab"""
        if self.github_branch_id and self.github_branch_id.repository_id:
            branch_url = f"{self.github_branch_id.repository_id.html_url}/tree/{self.github_branch_id.name}"
            return {
                'type': 'ir.actions.act_url',
                'url': branch_url,
                'target': 'new',
            }
    
    def action_refresh_project_branches(self):
        """Refresh branches for all repositories in the current project"""
        if self.project_id and self.project_id.github_repository_ids:
            for repo in self.project_id.github_repository_ids:
                self.env['github.branch'].fetch_branches_for_repository(repo.id)
            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
            }
    
    def action_view_project_repositories(self):
        """View all repositories for the current project"""
        if self.project_id:
            return self.project_id.action_view_all_repositories()
        return False