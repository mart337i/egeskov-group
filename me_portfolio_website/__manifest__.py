# -*- coding: utf-8 -*-
{
    'name': "me_portfolio_website",
    'version': '18.0.1.1.0',
    'license': "OPL-1",

    'summary': """
        """,

    'description': """
        
    """,

    'author': "egeskov-group.dk",# Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/16.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',

    # any module necessary for this one to work correctly
    'depends': ['web'],

    # always loaded
    'data': [
        'views/portfolio_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'me_portfolio_website/static/src/internal_lib/fonts/inter-local.css',
            'me_portfolio_website/static/src/internal_lib/bootstrap/bootstrap.min.css',
            'me_portfolio_website/static/src/internal_lib/fontawesome/all-local.min.css',
            'me_portfolio_website/static/src/css/portfolio.css',
            'me_portfolio_website/static/src/js/portfolio.js',
        ],
    },
    # only loaded in demonstration mode
    'demo': [],

    'installable': True,
    'auto_install': False,
    'application': False,
}
