{
    'name': 'SSL Certificate Manager',
    'version': '18.0.1.0.0',
    'category': 'Security',
    'summary': 'Manage SSL certificates with Let\'s Encrypt and multiple DNS providers',
    'description': """
    
SSL Certificate Manager
=======================

This module provides comprehensive SSL certificate management capabilities:

Features:
---------
* Create SSL certificates using Let's Encrypt
* Support for multiple DNS providers (Cloudflare, Route53, Azure, Google Cloud, etc.)
* Multi-account support for DNS providers
* Automatic certificate renewal
* Certificate deployment status monitoring
* Certificate download functionality
* Web interface for easy management

Supported DNS Providers:
------------------------
* Cloudflare
* AWS Route53
* Azure DNS
* Google Cloud DNS
* PowerDNS
* DigitalOcean
* Linode
* Gandi
* OVH
* Namecheap
* And many more...

Requirements:
-------------
* certbot
* Required certbot DNS plugins for your providers
* Python cryptography library
    """,
    'author': 'SSL Certificate Manager',
    'website': 'https://github.com/ssl-cert-manager',
    'license': 'LGPL-3',
    'depends': ['base', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'views/ssl_certificate_views.xml',
        'views/dns_provider_views.xml',
        'views/dns_account_views.xml',
        'views/menu_views.xml',
        'data/dns_provider_data.xml',
        'data/ir_cron_data.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'cert_watcher/static/src/css/ssl_cert.css',
            'cert_watcher/static/src/js/ssl_cert_widget.js',
            'cert_watcher/static/src/xml/ssl_cert_widget.xml',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': True,
}