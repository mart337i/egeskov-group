# Certificate Watcher

SSL Certificate monitoring module for Odoo 18.0

## Description

This module provides SSL certificate monitoring capabilities for domains, allowing you to track certificate expiration dates, validity status, and domain management information including DNS providers and domain registrars.

## Features

- Monitor SSL certificates for multiple domains
- Track certificate expiration dates with status indicators
- **Automatically detect DNS provider and domain registrar** via DNS/WHOIS lookups
- Automated certificate checking via cron jobs
- Kanban and list views for easy management
- Manual certificate refresh functionality
- HTTP to HTTPS redirect checking

## Installation

1. Copy this module to your Odoo addons directory
2. Install required Python dependencies:
   ```bash
   pip install requests cryptography dnspython python-whois
   ```
3. Update the app list and install the module from Odoo Apps

## Usage

1. Go to Security > Certificate Monitor
2. Create new certificate records by specifying:
   - Domain name
   - Port (default: 443)
3. Certificate information, DNS provider, and domain registrar will be **automatically detected and updated**

## Certificate Status

- **Valid**: Certificate is valid and not expiring soon
- **Expiring Soon**: Certificate expires within 30 days  
- **Expired**: Certificate has expired
- **Invalid**: Certificate has issues
- **Unreachable**: Domain cannot be reached
- **Error**: Error occurred during certificate check

## Requirements

- Odoo 18.0+
- Python requests library
- Python cryptography library
- Python dnspython library (for DNS lookups)
- Python python-whois library (for registrar detection)
- Network access to monitored domains

## License

LGPL-3