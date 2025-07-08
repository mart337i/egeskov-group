# -*- coding: utf-8 -*-
{
    'name': "Odoo Version Management",
    'version': '18.0.1.0.0',
    'license': "OPL-1",

    'summary': """
        Comprehensive Odoo version management with support tracking and integration helpers
        """,

    'description': """
        Odoo Version Management
        ======================
        
        This module provides comprehensive management of Odoo versions including:
        
        * Complete version database with all major Odoo releases
        * Support status tracking and lifecycle management
        * LTS (Long Term Support) version identification
        * Technical requirements (Python, PostgreSQL versions)
        * Release date and end-of-support tracking
        * Helper methods for version comparison and compatibility
        * Integration-friendly fields for other modules
        * Automatic support status updates via cron jobs
        
        Features:
        ---------
        * Pre-loaded with all Odoo versions from 8.0 to 18.0
        * Support status computation based on end-of-support dates
        * Version comparison methods for compatibility checking
        * Find-or-create helpers for dynamic version management
        * Module count tracking for registry integration
        * Release notes links and technical specifications
        
        Perfect for module registries, compatibility checking, and version management systems.
    """,

    'author': "egeskov-group.dk",
    'category': 'Technical',

    # any module necessary for this one to work correctly
    'depends': ['base'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'data/odoo_version_data.xml',
        'data/ir_cron.xml',
        'views/odoo_version_views.xml',
    ],
    # only loaded in demonstration mode
    'demo': [],

    'installable': True,
    'auto_install': False,
    'application': False,
}