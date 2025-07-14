{
    'name': 'Certificate Monitor',
    'version': '18.0.1.0.2',
    'category': 'Security',
    'summary': 'Monitor SSL certificates via HTTP requests without local storage',
    'description': """
    
Certificate Monitor
===================

This module provides SSL certificate monitoring capabilities via HTTP requests:

Features:
---------
* Monitor SSL certificates for any domain via HTTP/HTTPS
* Real-time certificate information retrieval
* Certificate expiry tracking and alerts
* Kanban view for easy domain management
* Detailed certificate information display
* HTTP to HTTPS redirect checking
* No local certificate storage required
* Automatic certificate status updates

Certificate Information:
------------------------
* Certificate validity dates
* Issuer information
* Subject Alternative Names (SAN)
* Serial numbers and signature algorithms
* Response time monitoring
* Reachability status

Requirements:
-------------
* Python requests library
* Python cryptography library
* Network access to monitored domains
    """,
    'author': 'Egeskov-group',
    'website': 'https://github.com/cert-monitor',
    'license': 'LGPL-3',
    'depends': ['base', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'views/ssl_certificate_views.xml',
        'views/menu_views.xml',
        'data/ir_cron_data.xml',
    ],
    'external_dependencies': {
        'python': ['requests', 'cryptography'],
    },
    'installable': True,
    'auto_install': False,
    'application': True,
}