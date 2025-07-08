# -*- coding: utf-8 -*-
{
    'name': "me_module_registry",
    'version': '18.0.1.0.0',
    'license': "OPL-1",

    'summary': """
        Simple module registry for Odoo with GitHub integration
        """,

    'description': """
        Module Registry for Odoo
        ===========================
        

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
        'views/module_registry_views.xml',
        'views/module_library_views.xml',
        'views/github_repository_views.xml',
        'views/menu_views.xml',
    ],
    # only loaded in demonstration mode
    'demo': [],

    'installable': True,
    'auto_install': False,
    'application': False,
}
