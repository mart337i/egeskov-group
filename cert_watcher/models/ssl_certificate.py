import os
import re
import json
import tempfile
import zipfile
import subprocess
import threading
import secrets
from datetime import datetime, timedelta
from pathlib import Path

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import config
import logging

_logger = logging.getLogger(__name__)

class SSLCertificate(models.Model):
    _name = 'ssl.certificate'
    _description = 'SSL Certificate'
    _order = 'domain'
    _rec_name = 'domain'

    # Basic Information
    domain = fields.Char(
        string='Domain',
        required=True,
        help='Domain name for the SSL certificate'
    )
    email = fields.Char(
        string='Contact Email',
        required=True,
        help='Email address for Let\'s Encrypt notifications'
    )
    
    # Certificate Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('creating', 'Creating'),
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('error', 'Error'),
        ('renewing', 'Renewing')
    ], string='Status', default='draft', tracking=True)
    
    # Certificate Details
    exists = fields.Boolean(
        string='Certificate Exists',
        compute='_compute_certificate_info',
        store=True
    )
    expiry_date = fields.Datetime(
        string='Expiry Date',
        compute='_compute_certificate_info',
        store=True
    )
    days_until_expiry = fields.Integer(
        string='Days Until Expiry',
        compute='_compute_certificate_info',
        store=True
    )
    needs_renewal = fields.Boolean(
        string='Needs Renewal',
        compute='_compute_certificate_info',
        store=True
    )
    
    # DNS Provider Configuration
    dns_provider_id = fields.Many2one(
        'dns.provider',
        string='DNS Provider',
        required=True,
        help='DNS provider to use for certificate validation'
    )
    dns_account_id = fields.Many2one(
        'dns.account',
        string='DNS Account',
        domain="[('provider_id', '=', dns_provider_id)]",
        help='Specific DNS account to use'
    )
    
    # Auto-renewal
    auto_renew = fields.Boolean(
        string='Auto Renew',
        default=True,
        help='Automatically renew certificate before expiration'
    )
    
    # Certificate Files
    cert_file = fields.Binary(
        string='Certificate File',
        attachment=True
    )
    key_file = fields.Binary(
        string='Private Key File',
        attachment=True
    )
    chain_file = fields.Binary(
        string='Certificate Chain',
        attachment=True
    )
    fullchain_file = fields.Binary(
        string='Full Chain Certificate',
        attachment=True
    )
    
    # Deployment Status
    deployment_status = fields.Text(
        string='Deployment Status',
        help='JSON data about certificate deployment status'
    )
    last_deployment_check = fields.Datetime(
        string='Last Deployment Check'
    )
    
    # History and Logs
    creation_log = fields.Text(
        string='Creation Log',
        help='Log output from certificate creation'
    )
    last_renewal_date = fields.Datetime(
        string='Last Renewal Date'
    )
    renewal_count = fields.Integer(
        string='Renewal Count',
        default=0
    )
    
    # Certificate History
    history_ids = fields.One2many(
        'ssl.certificate.history',
        'certificate_id',
        string='Certificate History'
    )
    
    @api.depends('domain')
    def _compute_certificate_info(self):
        """Compute certificate information from files"""
        for record in self:
            if not record.domain:
                record.update({
                    'exists': False,
                    'expiry_date': False,
                    'days_until_expiry': 0,
                    'needs_renewal': False
                })
                continue
                
            try:
                cert_info = self._get_certificate_info(record.domain)
                record.update({
                    'exists': cert_info.get('exists', False),
                    'expiry_date': cert_info.get('expiry_date'),
                    'days_until_expiry': cert_info.get('days_until_expiry', 0),
                    'needs_renewal': cert_info.get('needs_renewal', False)
                })
            except Exception as e:
                _logger.error(f"Error computing certificate info for {record.domain}: {e}")
                record.update({
                    'exists': False,
                    'expiry_date': False,
                    'days_until_expiry': 0,
                    'needs_renewal': False
                })

    @api.constrains('domain')
    def _check_domain_format(self):
        """Validate domain format"""
        for record in self:
            if record.domain:
                is_valid, error_msg = self._validate_domain(record.domain)
                if not is_valid:
                    raise ValidationError(f"Invalid domain format: {error_msg}")

    @api.constrains('email')
    def _check_email_format(self):
        """Validate email format"""
        for record in self:
            if record.email:
                is_valid, error_msg = self._validate_email(record.email)
                if not is_valid:
                    raise ValidationError(f"Invalid email format: {error_msg}")

    def _validate_domain(self, domain):
        """Validate domain name format"""
        if not domain or not isinstance(domain, str):
            return False, "Domain must be a non-empty string"
        
        domain = domain.strip().lower()
        
        # Basic format validation
        domain_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$'
        if not re.match(domain_pattern, domain):
            return False, "Invalid domain format"
        
        if len(domain) > 253:
            return False, "Domain name too long"
        
        return True, domain

    def _validate_email(self, email):
        """Validate email format"""
        if not email or not isinstance(email, str):
            return False, "Email must be a non-empty string"
        
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email.strip()):
            return False, "Invalid email format"
        
        return True, email.strip().lower()

    def _get_cert_directory(self):
        """Get certificate storage directory"""
        cert_dir = Path(config.get('data_dir', '/tmp')) / 'ssl_certificates'
        cert_dir.mkdir(exist_ok=True)
        return cert_dir

    def _get_certificate_info(self, domain):
        """Get certificate information for a domain"""
        cert_dir = self._get_cert_directory() / domain
        if not cert_dir.exists():
            return {
                'exists': False,
                'expiry_date': None,
                'days_until_expiry': 0,
                'needs_renewal': False
            }
        
        cert_file = cert_dir / "cert.pem"
        if not cert_file.exists():
            return {
                'exists': False,
                'expiry_date': None,
                'days_until_expiry': 0,
                'needs_renewal': False
            }
        
        try:
            # Get certificate expiry using openssl
            result = subprocess.run([
                'openssl', 'x509', '-in', str(cert_file), '-noout', '-dates'
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                not_after = None
                for line in lines:
                    if line.startswith('notAfter='):
                        not_after = line.split('=', 1)[1]
                        break
                
                if not_after:
                    # Parse the date
                    try:
                        expiry_date = datetime.strptime(not_after, '%b %d %H:%M:%S %Y %Z')
                        days_left = (expiry_date - datetime.now()).days
                        
                        return {
                            'exists': True,
                            'expiry_date': expiry_date,
                            'days_until_expiry': days_left,
                            'needs_renewal': days_left < 30
                        }
                    except Exception as e:
                        _logger.error(f"Error parsing certificate date: {e}")
        except Exception as e:
            _logger.error(f"Error getting certificate info: {e}")
        
        return {
            'exists': False,
            'expiry_date': None,
            'days_until_expiry': 0,
            'needs_renewal': False
        }

    def action_create_certificate(self):
        """Create SSL certificate"""
        self.ensure_one()
        
        if self.state != 'draft':
            raise UserError(_("Certificate can only be created from draft state"))
        
        if not self.dns_provider_id:
            raise UserError(_("DNS provider is required"))
        
        self.state = 'creating'
        
        # Create certificate in background
        threading.Thread(target=self._create_certificate_async).start()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Certificate Creation Started'),
                'message': _('Certificate creation for %s has been started in the background.') % self.domain,
                'type': 'success',
                'sticky': False,
            }
        }

    def _create_certificate_async(self):
        """Create certificate asynchronously"""
        try:
            with self.env.registry.cursor() as new_cr:
                new_env = api.Environment(new_cr, self.env.uid, self.env.context)
                record = new_env['ssl.certificate'].browse(self.id)
                
                success, message = record._create_certificate()
                
                if success:
                    record.state = 'active'
                    record._load_certificate_files()
                    record._add_history_entry('created', 'Certificate created successfully')
                else:
                    record.state = 'error'
                    record.creation_log = message
                    record._add_history_entry('error', f'Certificate creation failed: {message}')
                
                new_cr.commit()
                
        except Exception as e:
            _logger.error(f"Error in certificate creation: {e}")
            with self.env.registry.cursor() as new_cr:
                new_env = api.Environment(new_cr, self.env.uid, self.env.context)
                record = new_env['ssl.certificate'].browse(self.id)
                record.state = 'error'
                record.creation_log = str(e)
                record._add_history_entry('error', f'Certificate creation failed: {str(e)}')
                new_cr.commit()

    def _create_certificate(self):
        """Create SSL certificate using certbot"""
        try:
            # Validate inputs
            is_valid_domain, domain_error = self._validate_domain(self.domain)
            if not is_valid_domain:
                return False, f"Domain validation failed: {domain_error}"
            
            is_valid_email, email_error = self._validate_email(self.email)
            if not is_valid_email:
                return False, f"Email validation failed: {email_error}"
            
            # Get DNS provider configuration
            dns_config = self._get_dns_config()
            if not dns_config:
                return False, "DNS provider configuration not found"
            
            # Create config file and prepare certbot command
            config_file, dns_plugin, dns_args = self._prepare_dns_config(dns_config)
            
            # Create local directories for certbot
            letsencrypt_dir = self._get_cert_directory().parent / "letsencrypt"
            config_dir = letsencrypt_dir / "config"
            work_dir = letsencrypt_dir / "work"
            logs_dir = letsencrypt_dir / "logs"
            
            # Create directories if they don't exist
            config_dir.mkdir(parents=True, exist_ok=True)
            work_dir.mkdir(parents=True, exist_ok=True)
            logs_dir.mkdir(parents=True, exist_ok=True)
            
            # Prepare certbot command
            cmd = [
                'certbot', 'certonly',
                '--config-dir', str(config_dir),
                '--work-dir', str(work_dir),
                '--logs-dir', str(logs_dir),
                f'--dns-{dns_plugin}',
                *dns_args,
                '--email', self.email,
                '--agree-tos',
                '--non-interactive',
                '--cert-name', self.domain,
                '-d', self.domain,
                '-d', f'*.{self.domain}'  # Include wildcard
            ]
            
            _logger.info(f"Creating certificate for {self.domain} using {self.dns_provider_id.name}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                # Copy certificates to our directory
                src_dir = config_dir / "live" / self.domain
                dest_dir = self._get_cert_directory() / self.domain
                dest_dir.mkdir(exist_ok=True)
                
                # Copy certificate files
                files_to_copy = ['cert.pem', 'chain.pem', 'fullchain.pem', 'privkey.pem']
                for file_name in files_to_copy:
                    src_file = src_dir / file_name
                    dest_file = dest_dir / file_name
                    if src_file.exists():
                        with open(src_file, 'rb') as src, open(dest_file, 'wb') as dest:
                            dest.write(src.read())
                
                _logger.info(f"Certificate created successfully for {self.domain}")
                return True, "Certificate created successfully"
            else:
                error_msg = result.stderr or result.stdout
                _logger.error(f"Certificate creation failed: {error_msg}")
                return False, f"Certificate creation failed: {error_msg}"
                
        except Exception as e:
            error_msg = str(e)
            _logger.error(f"Exception during certificate creation: {error_msg}")
            return False, f"Exception: {error_msg}"

    def _get_dns_config(self):
        """Get DNS configuration for the certificate"""
        if self.dns_account_id:
            return self.dns_account_id._get_config_dict()
        elif self.dns_provider_id:
            # Use default account for provider
            default_account = self.dns_provider_id.account_ids.filtered('is_default')
            if default_account:
                return default_account[0]._get_config_dict()
            elif self.dns_provider_id.account_ids:
                return self.dns_provider_id.account_ids[0]._get_config_dict()
        
        return None

    def _prepare_dns_config(self, dns_config):
        """Prepare DNS configuration file and certbot arguments"""
        provider_code = self.dns_provider_id.code
        
        # Create config directory
        config_dir = self._get_cert_directory().parent / "letsencrypt" / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        
        if provider_code == 'cloudflare':
            config_file = config_dir / "cloudflare.ini"
            with open(config_file, 'w') as f:
                f.write(f"dns_cloudflare_api_token = {dns_config['api_token']}\n")
            config_file.chmod(0o600)
            return config_file, 'cloudflare', ['--dns-cloudflare-credentials', str(config_file)]
            
        elif provider_code == 'route53':
            config_file = config_dir / "route53.ini"
            with open(config_file, 'w') as f:
                f.write(f"dns_route53_access_key_id = {dns_config['access_key_id']}\n")
                f.write(f"dns_route53_secret_access_key = {dns_config['secret_access_key']}\n")
            config_file.chmod(0o600)
            return config_file, 'route53', ['--dns-route53-credentials', str(config_file)]
            
        # Add more providers as needed...
        
        raise UserError(f"DNS provider {provider_code} not implemented yet")

    def _load_certificate_files(self):
        """Load certificate files into binary fields"""
        cert_dir = self._get_cert_directory() / self.domain
        
        file_mappings = {
            'cert.pem': 'cert_file',
            'privkey.pem': 'key_file',
            'chain.pem': 'chain_file',
            'fullchain.pem': 'fullchain_file'
        }
        
        for file_name, field_name in file_mappings.items():
            file_path = cert_dir / file_name
            if file_path.exists():
                with open(file_path, 'rb') as f:
                    setattr(self, field_name, f.read())

    def _add_history_entry(self, action, message):
        """Add entry to certificate history"""
        self.env['ssl.certificate.history'].create({
            'certificate_id': self.id,
            'action': action,
            'message': message,
            'timestamp': fields.Datetime.now()
        })

    def action_renew_certificate(self):
        """Renew SSL certificate"""
        self.ensure_one()
        
        if self.state not in ['active', 'expired']:
            raise UserError(_("Certificate can only be renewed when active or expired"))
        
        self.state = 'renewing'
        
        # Renew certificate in background
        threading.Thread(target=self._renew_certificate_async).start()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Certificate Renewal Started'),
                'message': _('Certificate renewal for %s has been started in the background.') % self.domain,
                'type': 'success',
                'sticky': False,
            }
        }

    def _renew_certificate_async(self):
        """Renew certificate asynchronously"""
        try:
            with self.env.registry.cursor() as new_cr:
                new_env = api.Environment(new_cr, self.env.uid, self.env.context)
                record = new_env['ssl.certificate'].browse(self.id)
                
                success, message = record._create_certificate()  # Same process as creation
                
                if success:
                    record.state = 'active'
                    record.last_renewal_date = fields.Datetime.now()
                    record.renewal_count += 1
                    record._load_certificate_files()
                    record._add_history_entry('renewed', 'Certificate renewed successfully')
                else:
                    record.state = 'error'
                    record.creation_log = message
                    record._add_history_entry('error', f'Certificate renewal failed: {message}')
                
                new_cr.commit()
                
        except Exception as e:
            _logger.error(f"Error in certificate renewal: {e}")
            with self.env.registry.cursor() as new_cr:
                new_env = api.Environment(new_cr, self.env.uid, self.env.context)
                record = new_env['ssl.certificate'].browse(self.id)
                record.state = 'error'
                record.creation_log = str(e)
                record._add_history_entry('error', f'Certificate renewal failed: {str(e)}')
                new_cr.commit()

    def action_download_certificate(self):
        """Download certificate files as ZIP"""
        self.ensure_one()
        
        if not self.exists:
            raise UserError(_("No certificate files found"))
        
        # Create temporary ZIP file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp_file:
            with zipfile.ZipFile(tmp_file.name, 'w') as zip_file:
                if self.cert_file:
                    zip_file.writestr('cert.pem', self.cert_file)
                if self.key_file:
                    zip_file.writestr('privkey.pem', self.key_file)
                if self.chain_file:
                    zip_file.writestr('chain.pem', self.chain_file)
                if self.fullchain_file:
                    zip_file.writestr('fullchain.pem', self.fullchain_file)
            
            # Read the file and return as attachment
            with open(tmp_file.name, 'rb') as f:
                zip_data = f.read()
            
            # Clean up temp file
            os.unlink(tmp_file.name)
            
            attachment = self.env['ir.attachment'].create({
                'name': f'{self.domain}-certificates.zip',
                'type': 'binary',
                'datas': zip_data,
                'mimetype': 'application/zip'
            })
            
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/{attachment.id}?download=true',
                'target': 'self',
            }

    def action_check_deployment(self):
        """Check certificate deployment status"""
        self.ensure_one()
        
        try:
            status = self._check_ssl_certificate()
            self.deployment_status = json.dumps(status)
            self.last_deployment_check = fields.Datetime.now()
            
            if status.get('deployed') and status.get('certificate_match'):
                message = _('Certificate is properly deployed and matches')
                notification_type = 'success'
            elif status.get('deployed'):
                message = _('Certificate is deployed but may not match')
                notification_type = 'warning'
            else:
                message = _('Certificate is not deployed or unreachable')
                notification_type = 'danger'
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Deployment Status'),
                    'message': message,
                    'type': notification_type,
                    'sticky': False,
                }
            }
            
        except Exception as e:
            _logger.error(f"Error checking deployment status: {e}")
            raise UserError(_("Failed to check deployment status: %s") % str(e))

    def _check_ssl_certificate(self, port=443, timeout=10):
        """Check SSL certificate for the domain"""
        import ssl
        import socket
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend
        
        try:
            # Create SSL context
            context = ssl.create_default_context()
            
            # Connect to the domain
            with socket.create_connection((self.domain, port), timeout=timeout) as sock:
                with context.wrap_socket(sock, server_hostname=self.domain) as ssock:
                    # Get certificate info
                    cert_der = ssock.getpeercert(binary_form=True)
                    cert = x509.load_der_x509_certificate(cert_der, default_backend())
                    
                    # Check if certificate is valid for this domain
                    san_extension = None
                    try:
                        san_extension = cert.extensions.get_extension_for_oid(x509.oid.ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
                        san_names = [name.value for name in san_extension.value]
                    except:
                        san_names = []
                    
                    # Get subject common name
                    subject_cn = None
                    for attribute in cert.subject:
                        if attribute.oid == x509.oid.NameOID.COMMON_NAME:
                            subject_cn = attribute.value
                            break
                    
                    # Check if domain matches certificate
                    certificate_domains = []
                    if subject_cn:
                        certificate_domains.append(subject_cn)
                    certificate_domains.extend(san_names)
                    
                    domain_match = any(
                        self.domain == cert_domain or 
                        (cert_domain.startswith('*.') and self.domain.endswith(cert_domain[2:]))
                        for cert_domain in certificate_domains
                    )
                    
                    return {
                        'deployed': True,
                        'reachable': True,
                        'certificate_match': domain_match,
                        'certificate_domains': certificate_domains,
                        'issuer': cert.issuer.rfc4514_string(),
                        'expires_at': cert.not_valid_after_utc.isoformat(),
                        'method': 'ssl-direct',
                        'timestamp': datetime.now().isoformat()
                    }
                    
        except socket.timeout:
            return {
                'deployed': False,
                'reachable': False,
                'certificate_match': False,
                'error': 'timeout',
                'method': 'ssl-direct',
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            return {
                'deployed': False,
                'reachable': False,
                'certificate_match': False,
                'error': str(e),
                'method': 'ssl-direct',
                'timestamp': datetime.now().isoformat()
            }

    @api.model
    def cron_auto_renew_certificates(self):
        """Cron job to automatically renew certificates"""
        certificates = self.search([
            ('auto_renew', '=', True),
            ('state', '=', 'active'),
            ('needs_renewal', '=', True)
        ])
        
        for cert in certificates:
            try:
                cert.action_renew_certificate()
                _logger.info(f"Auto-renewal started for certificate: {cert.domain}")
            except Exception as e:
                _logger.error(f"Auto-renewal failed for certificate {cert.domain}: {e}")
                cert._add_history_entry('error', f'Auto-renewal failed: {str(e)}')
