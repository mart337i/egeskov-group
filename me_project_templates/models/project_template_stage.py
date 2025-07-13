# -*- coding: utf-8 -*-

from odoo import models, fields


class ProjectTemplateStage(models.Model):
    _name = 'project.template.stage'
    _description = 'Project Template Stage'
    _order = 'template_id, sequence, name'

    name = fields.Char(string='Stage Name', required=True, translate=True)
    sequence = fields.Integer(string='Sequence', default=10)
    template_id = fields.Many2one('project.template', string='Template', required=True, ondelete='cascade')
    folded = fields.Boolean(string='Folded', default=False, help='If checked, this stage will be in the folded columns')