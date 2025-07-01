
A comprehensive SSL certificate management module for Odoo that provides automated certificate creation, renewal, and monitoring using Let's Encrypt and multiple DNS providers.

## Features

### Core Functionality
- **Automated SSL Certificate Creation**: Generate SSL certificates using Let's Encrypt with DNS challenge validation
- **Multi-DNS Provider Support**: Support for 20+ DNS providers including Cloudflare, AWS Route53, Azure DNS, Google Cloud DNS, and more
- **Multi-Account Management**: Configure multiple accounts per DNS provider for different domains or environments
- **Automatic Renewal**: Background renewal of certificates before expiration
- **Certificate Monitoring**: Track certificate status, expiration dates, and deployment status
- **Certificate Download**: Export certificates as ZIP files for deployment

### Supported DNS Providers
- **Tier 1 Providers**: Cloudflare, AWS Route53, Azure DNS, Google Cloud DNS
- **Tier 2 Providers**: PowerDNS, DigitalOcean, Linode, Gandi, OVH, Namecheap
- **Additional Providers**: Vultr, DNS Made Easy, NS1, RFC2136, Hetzner, Porkbun, GoDaddy, Hurricane Electric, Dynu

### Security Features
- **Secure Credential Storage**: Encrypted storage of API keys and secrets
- **Access Control**: Role-based access with SSL Certificate Manager and Administrator groups
- **Audit Trail**: Complete history of certificate operations
- **Domain Validation**: Input validation and security checks

### Management Interface
- **Intuitive UI**: Easy-to-use interface for certificate management
- **Status Dashboard**: Visual indicators for certificate status and health
- **Deployment Monitoring**: Check if certificates are properly deployed
- **Bulk Operations**: Manage multiple certificates efficiently

## Installation

### Prerequisites
- Odoo 16.0 or higher
- certbot installed on the server
- Required certbot DNS plugins for your providers
- Python cryptography library

### Install Required Packages
```bash
# Install certbot and common DNS plugins
sudo apt-get install certbot

# Install DNS provider plugins
sudo apt-get install python3-certbot-dns-cloudflare
sudo apt-get install python3-certbot-dns-route53
sudo apt-get install python3-certbot-dns-google
# Add other provider plugins as needed

# Install Python dependencies
pip install cryptography requests
```

### Module Installation
1. Copy the module to your Odoo addons directory
2. Update the app list in Odoo
3. Install the "SSL Certificate Manager" module
4. Configure DNS providers and accounts

## Configuration

### 1. DNS Provider Setup
Navigate to **SSL Certificates > Configuration > DNS Providers** to configure your DNS providers.

### 2. DNS Account Configuration
Go to **SSL Certificates > Configuration > DNS Accounts** to add your DNS provider accounts:

#### Cloudflare Example:
- **Name**: Production Cloudflare
- **Provider**: Cloudflare
- **API Token**: Your Cloudflare API token with Zone:Edit permissions

#### AWS Route53 Example:
- **Name**: Production AWS
- **Provider**: AWS Route53
- **Access Key ID**: Your AWS access key
- **Secret Access Key**: Your AWS secret key
- **Region**: us-east-1 (or your preferred region)

### 3. Certificate Creation
1. Go to **SSL Certificates > Certificates**
2. Click **Create**
3. Fill in the domain name and contact email
4. Select your DNS provider and account
5. Click **Create Certificate**

## Usage

### Creating Certificates
```python
# Example: Create a certificate programmatically
certificate = env['ssl.certificate'].create({
    'domain': 'example.com',
    'email': 'admin@example.com',
    'dns_provider_id': cloudflare_provider.id,
    'dns_account_id': cloudflare_account.id,
    'auto_renew': True
})
certificate.action_create_certificate()
```

### Managing Multiple Accounts
The module supports multiple accounts per DNS provider, allowing you to:
- Use different API keys for different domains
- Separate production and staging environments
- Distribute load across multiple accounts

### Automatic Renewal
Certificates are automatically renewed when:
- Auto-renewal is enabled
- Certificate expires within 30 days
- Daily cron job runs (configurable)

### Monitoring and Alerts
- **Certificate Status**: Track active, expired, and error states
- **Expiration Monitoring**: Visual warnings for certificates nearing expiration
- **Deployment Checks**: Verify certificates are properly deployed
- **History Tracking**: Complete audit trail of all operations

## API Integration

### REST API Endpoints
The module provides REST API endpoints for external integration:

```bash
# Get certificate status
GET /api/ssl/certificates

# Create new certificate
POST /api/ssl/certificates
{
    "domain": "example.com",
    "email": "admin@example.com",
    "dns_provider": "cloudflare",
    "dns_account": "production"
}

# Renew certificate
POST /api/ssl/certificates/{id}/renew

# Download certificate
GET /api/ssl/certificates/{id}/download
```

## Security Considerations

### Access Control
- **SSL Certificate Manager**: Can view and manage certificates
- **SSL Certificate Administrator**: Can configure DNS providers and accounts

### Data Protection
- API keys and secrets are stored encrypted
- Certificate private keys are securely stored
- File permissions are properly set (600)
- Input validation prevents injection attacks

### Best Practices
- Use dedicated API tokens with minimal required permissions
- Regularly rotate API credentials
- Monitor certificate expiration dates
- Test deployment after certificate renewal

## Troubleshooting

### Common Issues

#### Certificate Creation Fails
1. Check DNS provider credentials
2. Verify API token permissions
3. Check certbot logs in the module
4. Ensure DNS propagation time is sufficient

#### Auto-Renewal Not Working
1. Verify cron job is active
2. Check certificate auto_renew setting
3. Review certificate history for errors
4. Validate DNS provider account status

#### Deployment Status Unknown
1. Ensure domain is accessible
2. Check firewall and DNS settings
3. Verify certificate is properly installed on web server
4. Test with external SSL checkers

### Log Analysis
Check Odoo logs for detailed error messages:
```bash
tail -f /var/log/odoo/odoo.log | grep ssl_certificate
```

## Development

### Extending DNS Providers
To add support for new DNS providers:

1. Add provider data in `data/dns_provider_data.xml`
2. Extend `_prepare_dns_config()` method in `ssl_certificate.py`
3. Add provider-specific fields to `dns_account.py`
4. Update the form view for the new provider

### Custom Validation
Override validation methods for specific requirements:
```python
@api.constrains('domain')
def _check_domain_custom(self):
    # Add custom domain validation logic
    pass
```

## License

This module is licensed under LGPL-3. See LICENSE file for details.

## Support

For support and bug reports, please create an issue in the project repository.