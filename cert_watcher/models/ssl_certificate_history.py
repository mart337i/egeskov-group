from odoo import models, fields, api

class SSLCertificateHistory(models.Model):
    _name = 'ssl.certificate.history'
    _description = 'SSL Certificate History'
    _order = 'timestamp desc'
    _rec_name = 'action'

    certificate_id = fields.Many2one(
        'ssl.certificate',
        string='Certificate',
        required=True,
        ondelete='cascade'
    )
    action = fields.Selection([
        ('created', 'Created'),
        ('renewed', 'Renewed'),
        ('error', 'Error'),
        ('downloaded', 'Downloaded'),
        ('deployment_checked', 'Deployment Checked')
    ], string='Action', required=True)
    message = fields.Text(
        string='Message',
        help='Details about the action'
    )
    timestamp = fields.Datetime(
        string='Timestamp',
        required=True,
        default=fields.Datetime.now
    )
    user_id = fields.Many2one(
        'res.users',
        string='User',
        default=lambda self: self.env.user
    )
