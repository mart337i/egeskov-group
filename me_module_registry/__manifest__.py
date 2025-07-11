# -*- coding: utf-8 -*-
{
    'name': "me_module_registry",
    'version': '18.0.1.1.0',
    'license': "OPL-1",

    'summary': """
        Module registry with template/variant structure and GitHub integration
        """,

    'description': """
        Module Registry for Odoo
        ===========================
        
        This module provides a comprehensive registry system for Odoo modules with GitHub integration.
        
        Key Features:
        - **Module Templates**: Static information that doesn't change between versions (name, description, category, author, etc.)
        - **Module Versions**: Version-specific information for each branch/version (dependencies, manifest data, branch info)
        - **GitHub Integration**: Automatic synchronization from GitHub repositories
        - **Version Management**: Track module versions across different branches and Odoo versions
        - **Library Organization**: Group modules by repository/library
        
        Structure:
        - Module Templates contain static info shared across all versions
        - Module Registry (versions) contain version-specific data from GitHub branches
        - Each template can have multiple versions from different branches
        - Automatic sync from GitHub repositories marked as Odoo module repositories

    """,

    'author': "egeskov-group.dk",
    
    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/16.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',

    # any module necessary for this one to work correctly
    'depends': ['base','github_integration','me_odoo_version'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'views/github_repository_views.xml',
        'views/module_template_views.xml',
        'views/module_registry_views.xml',
        'views/module_library_views.xml',
        'views/menu_views.xml',
    ],
    # only loaded in demonstration mode
    'demo': [],

    'installable': True,
    'auto_install': False,
    'application': False,
}
