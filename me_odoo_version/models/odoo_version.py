from odoo import api, fields, models, _
import logging
import re
from datetime import datetime, date

_logger = logging.getLogger(__name__)


class OdooVersion(models.Model):
    _name = 'odoo.version'
    _description = 'Odoo Version'
    _rec_name = 'display_name'
    _order = 'major_version desc, minor_version desc, sequence'

    # Basic version information
    sequence = fields.Integer('sequence')
    name = fields.Char('Version Name', required=True, help='Short version name (e.g., 18.0)')
    display_name = fields.Char('Display Name', compute='_compute_display_name', store=True)
    full_name = fields.Char('Full Name', help='Full version name (e.g., Odoo 18.0)')
    
    # Version components
    major_version = fields.Integer('Major Version', required=True, help='Major version number (e.g., 18)')
    minor_version = fields.Float('Minor Version', required=True, help='Minor version number (e.g., 0)')
    version_string = fields.Char('Version String', compute='_compute_version_string', store=True)
    
    # Release information
    release_date = fields.Date('Release Date', help='Official release date')
    end_of_support = fields.Date('End of Support', help='End of support date')
    is_lts = fields.Boolean('Long Term Support', default=False, help='Is this an LTS version?')
    is_current = fields.Boolean('Current Version', default=False, help='Is this the current stable version?')
    is_supported = fields.Boolean('Supported', compute='_compute_is_supported', store=True)
    
    # Status and lifecycle
    status = fields.Selection([
        ('development', 'Development'),
        ('beta', 'Beta'),
        ('stable', 'Stable'),
        ('maintenance', 'Maintenance Only'),
        ('deprecated', 'Deprecated'),
        ('end_of_life', 'End of Life')
    ], string='Status', default='stable', required=True)
    
    # Technical information
    python_version = fields.Char('Python Version', help='Required Python version (e.g., 3.10+)')
    postgresql_version = fields.Char('PostgreSQL Version', help='Supported PostgreSQL version (e.g., 12+)')
    
    # Description and notes
    description = fields.Text('Description', help='Version description and key features')
    release_notes_url = fields.Char('Release Notes URL', help='URL to official release notes')
    
    # Computed fields for easier integration
    version_code = fields.Char('Version Code', compute='_compute_version_code', store=True, help='Sortable version code')
    is_enterprise = fields.Boolean('Enterprise Available', default=True, help='Is Enterprise edition available?')
    is_community = fields.Boolean('Community Available', default=True, help='Is Community edition available?')
    
    # Statistics (for module registry integration)
    module_count = fields.Integer('Module Count', compute='_compute_module_count', help='Number of modules for this version')
    
    _sql_constraints = [
        ('unique_name', 'unique(name)', 'Version name must be unique!'),
        ('unique_major_minor', 'unique(major_version, minor_version)', 'Major.Minor version combination must be unique!'),
    ]

    @api.depends('name', 'full_name')
    def _compute_display_name(self):
        for version in self:
            version.display_name = version.full_name or version.name

    @api.depends('major_version', 'minor_version')
    def _compute_version_string(self):
        for version in self:
            if version.minor_version == int(version.minor_version):
                version.version_string = f"{version.major_version}.{int(version.minor_version)}"
            else:
                version.version_string = f"{version.major_version}.{version.minor_version}"

    @api.depends('major_version', 'minor_version')
    def _compute_version_code(self):
        for version in self:
            # Create sortable version code (e.g., 18.0 -> "018.000")
            version.version_code = f"{version.major_version:03d}.{version.minor_version:03.0f}"

    @api.depends('end_of_support', 'status')
    def _compute_is_supported(self):
        today = date.today()
        for version in self:
            if version.status in ['end_of_life', 'deprecated']:
                version.is_supported = False
            elif version.end_of_support:
                version.is_supported = version.end_of_support >= today
            else:
                version.is_supported = version.status in ['development', 'beta', 'stable', 'maintenance']

    def _compute_module_count(self):
        for version in self:
            # Count modules from module registry if available
            if hasattr(self.env, 'module.registry'):
                version.module_count = self.env['module.registry'].search_count([
                    ('odoo_version_id', '=', version.id)
                ])
            else:
                version.module_count = 0

    @api.model
    def get_current_version(self):
        """Get the current stable version"""
        return self.search([('is_current', '=', True)], limit=1)

    @api.model
    def get_supported_versions(self):
        """Get all currently supported versions"""
        return self.search([('is_supported', '=', True)])

    @api.model
    def get_lts_versions(self):
        """Get all LTS versions"""
        return self.search([('is_lts', '=', True)])

    def compare_version(self, other_version):
        """Compare this version with another version
        Returns: -1 if self < other, 0 if equal, 1 if self > other
        """
        if not isinstance(other_version, type(self)):
            return False
            
        if self.major_version < other_version.major_version:
            return -1
        elif self.major_version > other_version.major_version:
            return 1
        else:
            if self.minor_version < other_version.minor_version:
                return -1
            elif self.minor_version > other_version.minor_version:
                return 1
            else:
                return 0

    def is_compatible_with(self, module_version_string):
        """Check if this Odoo version is compatible with a module version string
        Args:
            module_version_string: Version string from module manifest (e.g., "18.0.1.0.0")
        Returns:
            bool: True if compatible
        """
        if not module_version_string:
            return False
            
        # Extract major.minor from module version string
        match = re.match(r'^(\d+)\.(\d+)', str(module_version_string))
        if not match:
            return False
            
        module_major = int(match.group(1))
        module_minor = float(match.group(2))
        
        return (self.major_version == module_major and 
                self.minor_version == module_minor)

    @api.model
    def find_version(self, version_string):
        """Find or create a version record from a version string
        Args:
            version_string: Version string (e.g., "18.0" or "18.0.1.0.0")
        Returns:
            odoo.version record
        """
        # Extract major.minor from version string
        match = re.match(r'^(\d+)\.(\d+)', str(version_string))
        if not match:
            return False
            
        major = int(match.group(1))
        minor = float(match.group(2))

        return self.search([('major_version', '=', major), ('minor_version', '=', minor)], limit=1)
        

    def action_open_release_notes(self):
        """Open release notes URL"""
        if self.release_notes_url:
            return {
                'type': 'ir.actions.act_url',
                'url': self.release_notes_url,
                'target': 'new',
            }

    @api.model
    def update_support_status(self):
        """Update support status for all versions (can be called by cron)"""
        versions = self.search([])
        versions._compute_is_supported()
        _logger.info("Updated support status for %d Odoo versions", len(versions))
    