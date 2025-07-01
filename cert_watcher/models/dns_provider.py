from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class DNSProvider(models.Model):
    _name = 'dns.provider'
    _description = 'DNS Provider'
    _order = 'name'

    name = fields.Char(
        string='Provider Name',
        required=True,
        help='Display name of the DNS provider'
    )
    code = fields.Char(
        string='Provider Code',
        required=True,
        help='Technical code for the DNS provider (e.g., cloudflare, route53)'
    )
    description = fields.Text(
        string='Description',
        help='Description of the DNS provider'
    )
    active = fields.Boolean(
        string='Active',
        default=True
    )
    
    # Configuration fields
    required_fields = fields.Text(
        string='Required Fields',
        help='JSON list of required configuration fields'
    )
    optional_fields = fields.Text(
        string='Optional Fields',
        help='JSON list of optional configuration fields'
    )
    
    # Accounts
    account_ids = fields.One2many(
        'dns.account',
        'provider_id',
        string='Accounts'
    )
    account_count = fields.Integer(
        string='Account Count',
        compute='_compute_account_count'
    )
    
    # Certificates using this provider
    certificate_ids = fields.One2many(
        'ssl.certificate',
        'dns_provider_id',
        string='Certificates'
    )
    certificate_count = fields.Integer(
        string='Certificate Count',
        compute='_compute_certificate_count'
    )

    @api.depends('account_ids')
    def _compute_account_count(self):
        for provider in self:
            provider.account_count = len(provider.account_ids)

    @api.depends('certificate_ids')
    def _compute_certificate_count(self):
        for provider in self:
            provider.certificate_count = len(provider.certificate_ids)

    @api.constrains('code')
    def _check_unique_code(self):
        for provider in self:
            if self.search_count([('code', '=', provider.code), ('id', '!=', provider.id)]) > 0:
                raise ValidationError(_("Provider code must be unique"))

    def get_default_account(self):
        """Get the default account for this provider"""
        self.ensure_one()
        default_account = self.account_ids.filtered('is_default')
        if default_account:
            return default_account[0]
        elif self.account_ids:
            return self.account_ids[0]
        return None
