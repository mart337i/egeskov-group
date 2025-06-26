{
    'name': 'GitHub Integration',
    'version': '18.0.1.0.0',
    'category': 'Project',
    'summary': 'Integrate GitHub repositories with Odoo projects',
    'description': """
        GitHub Integration Module
        =========================
        
        This module extends Odoo projects with GitHub integration:
        - Link GitHub repositories to projects
        - View deployment status for software projects
        - Quick access to GitHub repo from kanban view
        - Real-time deployment status updates
    """,
    'author': 'Egeskov-group',
    'depends': ['project', 'web'],
    'data': [
        'data/system_parameters.xml',
        'data/ir_cron.xml',
        'wizard/github_repository_wizard_views.xml',
        'data/wizard_actions.xml',
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
        'views/project_project_views.xml',
        'views/project_task_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'github_integration/static/src/css/github_integration.css',
            'github_integration/static/src/js/github_widget.js',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
}