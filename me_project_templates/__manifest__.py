# -*- coding: utf-8 -*-
{
    'name': "me_project_templates",
    'version': '18.0.1.0.0',
    'license': "OPL-1",

    'summary': """
        Configurable Project Templates
        """,

    'description': """
        This module allows administrators to configure project templates that users can apply when creating new projects.
        
        Features:
        - Create and manage project templates with custom stages
        - Configure visual elements (bullets, colors)
        - Set up folded and regular columns
        - Translatable template names and descriptions
        - Integration with existing project kanban examples
    """,

    'author': "egeskov-group.dk",# Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/16.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',

    # any module necessary for this one to work correctly
    'depends': ['project'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/project_template_views.xml',
        'views/templates/project_examples.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'data/project_template_demo.xml',
    ],
    
    'assets': {
        'web.assets_backend': [
            'me_project_templates/static/src/js/project_kanban_examples.js',
            'me_project_templates/static/src/js/project_kanban_patch.js',
        ],
    },

    'installable': True,
    'auto_install': False,
    'application': False,}