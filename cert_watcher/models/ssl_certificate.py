import ssl
import socket
import requests
import json
import subprocess
import re
from datetime import datetime, timedelta
from urllib.parse import urlparse

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging



_logger = logging.getLogger(__name__)

class SSLCertificate(models.Model):
    _name = 'ssl.certificate'
    _description = 'SSL Certificate Monitor'
    _order = 'domain'
    _rec_name = 'domain'

    # Basic Information
    domain = fields.Char(
        string='Domain',
        required=True,
        help='Domain name to monitor (e.g., example.com)'
    )
    port = fields.Integer(
        string='Port',
        default=443,
        help='Port to check SSL certificate on'
    )
    

    
    # Certificate Status
    state = fields.Selection([
        ('valid', 'Valid'),
        ('expired', 'Expired'),
        ('expiring_soon', 'Expiring Soon'),
        ('invalid', 'Invalid'),
        ('unreachable', 'Unreachable'),
        ('error', 'Error')
    ], string='Status', default='error', compute='_compute_certificate_status', store=True)
    
    # Certificate Information
    issuer = fields.Char(
        string='Issuer',
        compute='_compute_certificate_info',
        store=True
    )
    subject = fields.Char(
        string='Subject',
        compute='_compute_certificate_info',
        store=True
    )
    serial_number = fields.Char(
        string='Serial Number',
        compute='_compute_certificate_info',
        store=True
    )
    signature_algorithm = fields.Char(
        string='Signature Algorithm',
        compute='_compute_certificate_info',
        store=True
    )
    
    # Validity Information
    valid_from = fields.Datetime(
        string='Valid From',
        compute='_compute_certificate_info',
        store=True
    )
    valid_until = fields.Datetime(
        string='Valid Until',
        compute='_compute_certificate_info',
        store=True
    )
    days_until_expiry = fields.Integer(
        string='Days Until Expiry',
        compute='_compute_certificate_info',
        store=True
    )
    
    # Domain Information
    san_domains = fields.Text(
        string='Subject Alternative Names',
        compute='_compute_certificate_info',
        store=True,
        help='All domains covered by this certificate'
    )
    
    # Connection Information
    is_reachable = fields.Boolean(
        string='Reachable',
        compute='_compute_certificate_info',
        store=True
    )
    response_time = fields.Float(
        string='Response Time (ms)',
        compute='_compute_certificate_info',
        store=True
    )
    
    # Last Check Information
    last_check = fields.Datetime(
        string='Last Check',
        compute='_compute_certificate_info',
        store=True
    )
    error_message = fields.Text(
        string='Error Message',
        compute='_compute_certificate_info',
        store=True
    )
    
    # Raw Certificate Data
    certificate_data = fields.Text(
        string='Certificate Data',
        compute='_compute_certificate_info',
        store=True,
        help='Raw certificate information as JSON'
    )

    @api.depends('domain', 'port')
    def _compute_certificate_info(self):
        """Fetch certificate information via HTTP/SSL"""
        for record in self:
            if not record.domain:
                record._reset_certificate_fields()
                continue
                
            try:
                cert_info = record._fetch_certificate_info()
                record._update_certificate_fields(cert_info)
            except Exception as e:
                _logger.error(f"Error fetching certificate info for {record.domain}: {e}")
                record._reset_certificate_fields()
                record.error_message = str(e)
                record.last_check = fields.Datetime.now()

    @api.depends('valid_until', 'is_reachable', 'error_message')
    def _compute_certificate_status(self):
        """Compute certificate status based on validity and reachability"""
        for record in self:
            if not record.is_reachable:
                record.state = 'unreachable'
            elif record.error_message:
                record.state = 'error'
            elif not record.valid_until:
                record.state = 'invalid'
            elif record.valid_until < fields.Datetime.now():
                record.state = 'expired'
            elif record.days_until_expiry <= 30:
                record.state = 'expiring_soon'
            else:
                record.state = 'valid'

    def _reset_certificate_fields(self):
        """Reset all certificate fields to default values"""
        self.update({
            'issuer': False,
            'subject': False,
            'serial_number': False,
            'signature_algorithm': False,
            'valid_from': False,
            'valid_until': False,
            'days_until_expiry': 0,
            'san_domains': False,
            'is_reachable': False,
            'response_time': 0.0,
            'certificate_data': False,
            'error_message': False,
        })

    def _update_certificate_fields(self, cert_info):
        """Update certificate fields with fetched information"""
        self.update({
            'issuer': cert_info.get('issuer'),
            'subject': cert_info.get('subject'),
            'serial_number': cert_info.get('serial_number'),
            'signature_algorithm': cert_info.get('signature_algorithm'),
            'valid_from': cert_info.get('valid_from'),
            'valid_until': cert_info.get('valid_until'),
            'days_until_expiry': cert_info.get('days_until_expiry', 0),
            'san_domains': cert_info.get('san_domains'),
            'is_reachable': cert_info.get('is_reachable', False),
            'response_time': cert_info.get('response_time', 0.0),
            'certificate_data': json.dumps(cert_info, indent=2, default=str),
            'error_message': cert_info.get('error_message'),
            'last_check': fields.Datetime.now(),
        })

    def _fetch_certificate_info(self):
        """Fetch certificate information using SSL connection"""
        start_time = datetime.now()
        
        try:
            # Create SSL context
            context = ssl.create_default_context()
            
            # Connect to the domain
            with socket.create_connection((self.domain, self.port), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=self.domain) as ssock:
                    # Calculate response time
                    response_time = (datetime.now() - start_time).total_seconds() * 1000
                    
                    # Get certificate
                    cert_der = ssock.getpeercert(binary_form=True)
                    cert_dict = ssock.getpeercert()
                    
                    # Parse certificate using cryptography library
                    from cryptography import x509
                    from cryptography.hazmat.backends import default_backend
                    
                    cert = x509.load_der_x509_certificate(cert_der, default_backend())
                    
                    # Convert timezone-aware datetimes to naive datetimes for Odoo
                    valid_from_naive = cert.not_valid_before_utc.replace(tzinfo=None) if cert.not_valid_before_utc else None
                    valid_until_naive = cert.not_valid_after_utc.replace(tzinfo=None) if cert.not_valid_after_utc else None
                    
                    # Extract certificate information
                    cert_info = {
                        'is_reachable': True,
                        'response_time': response_time,
                        'issuer': cert.issuer.rfc4514_string(),
                        'subject': cert.subject.rfc4514_string(),
                        'serial_number': str(cert.serial_number),
                        'signature_algorithm': cert.signature_algorithm_oid._name,
                        'valid_from': valid_from_naive,
                        'valid_until': valid_until_naive,
                        'version': cert.version.name,
                    }
                    
                    # Calculate days until expiry
                    if valid_until_naive:
                        days_left = (valid_until_naive - datetime.now()).days
                        cert_info['days_until_expiry'] = days_left
                    
                    # Extract Subject Alternative Names
                    try:
                        san_extension = cert.extensions.get_extension_for_oid(x509.oid.ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
                        san_names = [name.value for name in san_extension.value]
                        cert_info['san_domains'] = '\n'.join(san_names)
                        cert_info['san_list'] = san_names
                    except x509.ExtensionNotFound:
                        cert_info['san_domains'] = ''
                        cert_info['san_list'] = []
                    
                    # Extract additional extensions
                    cert_info['extensions'] = {}
                    for extension in cert.extensions:
                        try:
                            cert_info['extensions'][extension.oid._name] = str(extension.value)
                        except:
                            cert_info['extensions'][extension.oid._name] = 'Unable to parse'
                    
                    # Add raw certificate data
                    cert_info['raw_cert'] = cert_dict
                    
                    return cert_info
                    
        except socket.timeout:
            return {
                'is_reachable': False,
                'error_message': 'Connection timeout',
                'response_time': (datetime.now() - start_time).total_seconds() * 1000
            }
        except socket.gaierror as e:
            return {
                'is_reachable': False,
                'error_message': f'DNS resolution failed: {str(e)}',
                'response_time': (datetime.now() - start_time).total_seconds() * 1000
            }
        except ssl.SSLError as e:
            return {
                'is_reachable': True,
                'error_message': f'SSL Error: {str(e)}',
                'response_time': (datetime.now() - start_time).total_seconds() * 1000
            }
        except Exception as e:
            return {
                'is_reachable': False,
                'error_message': f'Unexpected error: {str(e)}',
                'response_time': (datetime.now() - start_time).total_seconds() * 1000
            }

    def action_refresh_certificate(self):
        """Manually refresh certificate information"""
        self.ensure_one()
        
        # Trigger recomputation
        self._compute_certificate_info()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Certificate Refreshed'),
                'message': _('Certificate information for %s has been updated.') % self.domain,
                'type': 'success',
                'sticky': False,
            }
        }

    def action_check_http_redirect(self):
        """Check if HTTP redirects to HTTPS"""
        self.ensure_one()
        
        try:
            # Check HTTP redirect
            http_url = f"http://{self.domain}"
            response = requests.get(http_url, allow_redirects=False, timeout=10)
            
            redirect_info = {
                'status_code': response.status_code,
                'redirects_to_https': False,
                'location': response.headers.get('Location', ''),
            }
            
            if response.status_code in [301, 302, 303, 307, 308]:
                location = response.headers.get('Location', '')
                if location.startswith('https://'):
                    redirect_info['redirects_to_https'] = True
            
            message = _('HTTP Status: %s') % response.status_code
            if redirect_info['redirects_to_https']:
                message += _('\nRedirects to HTTPS: Yes')
                notification_type = 'success'
            else:
                message += _('\nRedirects to HTTPS: No')
                notification_type = 'warning'
                
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('HTTP Redirect Check'),
                    'message': message,
                    'type': notification_type,
                    'sticky': False,
                }
            }
            
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('HTTP Check Failed'),
                    'message': _('Failed to check HTTP redirect: %s') % str(e),
                    'type': 'danger',
                    'sticky': False,
                }
            }

    @api.model
    def cron_refresh_certificates(self):
        """Cron job to refresh all certificate information"""
        certificates = self.search([])
        _logger.info(f"Starting cron job to refresh {len(certificates)} certificates")
        
        success_count = 0
        error_count = 0
        
        for cert in certificates:
            try:
                cert._compute_certificate_info()
                _logger.info(f"Refreshed certificate info for: {cert.domain}")
                success_count += 1
            except Exception as e:
                _logger.error(f"Failed to refresh certificate for {cert.domain}: {e}")
                error_count += 1
        
        _logger.info(f"Cron job completed: {success_count} successful, {error_count} failed")

    @api.constrains('domain')
    def _check_domain_format(self):
        """Validate domain format"""
        import re
        for record in self:
            if record.domain:
                # Basic domain validation
                domain_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$'
                if not re.match(domain_pattern, record.domain.strip().lower()):
                    raise ValidationError(_("Invalid domain format"))

    @api.constrains('port')
    def _check_port_range(self):
        """Validate port range"""
        for record in self:
            if record.port and (record.port < 1 or record.port > 65535):
                raise ValidationError(_("Port must be between 1 and 65535"))


