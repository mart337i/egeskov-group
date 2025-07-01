import json
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class DNSAccount(models.Model):
    _name = 'dns.account'
    _description = 'DNS Provider Account'
    _order = 'provider_id, name'

    name = fields.Char(
        string='Account Name',
        required=True,
        help='Descriptive name for this DNS account'
    )
    provider_id = fields.Many2one(
        'dns.provider',
        string='DNS Provider',
        required=True,
        ondelete='cascade'
    )
    description = fields.Text(
        string='Description',
        help='Description of this DNS account'
    )
    is_default = fields.Boolean(
        string='Default Account',
        help='Use this account as default for the provider'
    )
    active = fields.Boolean(
        string='Active',
        default=True
    )
    
    # Configuration fields (JSON storage for flexibility)
    config_data = fields.Text(
        string='Configuration Data',
        help='JSON configuration data for this account'
    )
    
    # Cloudflare specific
    api_token = fields.Char(
        string='API Token',
        help='Cloudflare API Token'
    )
    
    # AWS Route53 specific
    access_key_id = fields.Char(
        string='Access Key ID',
        help='AWS Access Key ID'
    )
    secret_access_key = fields.Char(
        string='Secret Access Key',
        help='AWS Secret Access Key'
    )
    region = fields.Char(
        string='AWS Region',
        default='us-east-1',
        help='AWS Region'
    )
    
    # Azure specific
    subscription_id = fields.Char(
        string='Subscription ID',
        help='Azure Subscription ID'
    )
    resource_group = fields.Char(
        string='Resource Group',
        help='Azure Resource Group'
    )
    tenant_id = fields.Char(
        string='Tenant ID',
        help='Azure Tenant ID'
    )
    client_id = fields.Char(
        string='Client ID',
        help='Azure Client ID'
    )
    client_secret = fields.Char(
        string='Client Secret',
        help='Azure Client Secret'
    )
    
    # Google Cloud specific
    project_id = fields.Char(
        string='Project ID',
        help='Google Cloud Project ID'
    )
    service_account_key = fields.Text(
        string='Service Account Key',
        help='Google Cloud Service Account JSON Key'
    )
    
    # PowerDNS specific
    api_url = fields.Char(
        string='API URL',
        help='PowerDNS API URL'
    )
    api_key = fields.Char(
        string='API Key',
        help='PowerDNS API Key'
    )
    
    # Generic fields for other providers
    username = fields.Char(
        string='Username',
        help='Username for authentication'
    )
    password = fields.Char(
        string='Password',
        help='Password for authentication'
    )
    endpoint = fields.Char(
        string='Endpoint',
        help='API Endpoint URL'
    )
    
    # Certificates using this account
    certificate_ids = fields.One2many(
        'ssl.certificate',
        'dns_account_id',
        string='Certificates'
    )
    certificate_count = fields.Integer(
        string='Certificate Count',
        compute='_compute_certificate_count'
    )

    @api.depends('certificate_ids')
    def _compute_certificate_count(self):
        for account in self:
            account.certificate_count = len(account.certificate_ids)

    @api.constrains('is_default')
    def _check_single_default(self):
        """Ensure only one default account per provider"""
        for account in self:
            if account.is_default:
                other_defaults = self.search([
                    ('provider_id', '=', account.provider_id.id),
                    ('is_default', '=', True),
                    ('id', '!=', account.id)
                ])
                if other_defaults:
                    raise ValidationError(_("Only one default account is allowed per provider"))

    def _get_config_dict(self):
        """Get configuration as dictionary"""
        self.ensure_one()
        
        provider_code = self.provider_id.code
        config = {}
        
        if provider_code == 'cloudflare':
            config = {
                'api_token': self.api_token
            }
        elif provider_code == 'route53':
            config = {
                'access_key_id': self.access_key_id,
                'secret_access_key': self.secret_access_key,
                'region': self.region or 'us-east-1'
            }
        elif provider_code == 'azure':
            config = {
                'subscription_id': self.subscription_id,
                'resource_group': self.resource_group,
                'tenant_id': self.tenant_id,
                'client_id': self.client_id,
                'client_secret': self.client_secret
            }
        elif provider_code == 'google':
            config = {
                'project_id': self.project_id,
                'service_account_key': self.service_account_key
            }
        elif provider_code == 'powerdns':
            config = {
                'api_url': self.api_url,
                'api_key': self.api_key
            }
        elif provider_code in ['digitalocean', 'linode', 'gandi']:
            config = {
                'api_token': self.api_token or self.api_key
            }
        elif provider_code == 'ovh':
            config = {
                'endpoint': self.endpoint,
                'application_key': self.api_key,
                'application_secret': self.client_secret,
                'consumer_key': self.password
            }
        elif provider_code == 'namecheap':
            config = {
                'username': self.username,
                'api_key': self.api_key
            }
        
        # Add custom config data if available
        if self.config_data:
            try:
                custom_config = json.loads(self.config_data)
                config.update(custom_config)
            except (json.JSONDecodeError, TypeError):
                pass
        
        return config

    def action_test_connection(self):
        """Test DNS provider connection"""
        self.ensure_one()
        
        # This would implement actual connection testing
        # For now, just validate configuration
        config = self._get_config_dict()
        
        if not config:
            raise ValidationError(_("No configuration found for this account"))
        
        # Basic validation based on provider
        provider_code = self.provider_id.code
        
        if provider_code == 'cloudflare' and not config.get('api_token'):
            raise ValidationError(_("Cloudflare API token is required"))
        elif provider_code == 'route53' and not (config.get('access_key_id') and config.get('secret_access_key')):
            raise ValidationError(_("AWS credentials are required"))
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Connection Test'),
                'message': _('Configuration appears valid'),
                'type': 'success',
                'sticky': False,
            }
        }