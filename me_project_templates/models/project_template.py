# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class ProjectTemplate(models.Model):
    _name = 'project.template'
    _description = 'Project Template'
    _order = 'sequence, name'

    name = fields.Char(string='Template Name', required=True, translate=True)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)
    description = fields.Html(string='Description', translate=True)
    is_custom = fields.Boolean(string='Custom Template', default=True, help='Distinguishes custom templates from system defaults')
    
    # Template configuration
    ghost_columns = fields.Char(string='Ghost Columns', help='Comma-separated list of ghost column names')
    apply_examples_text = fields.Char(string='Apply Button Text', default='Use This For My Project', translate=True)
    allowed_group_bys = fields.Char(string='Allowed Group Bys', default='stage_id', help='Comma-separated list of allowed group by fields')
    fold_field = fields.Char(string='Fold Field', default='fold')
    
    # Visual elements
    bullet_green = fields.Boolean(string='Green Bullet', default=True)
    bullet_orange = fields.Boolean(string='Orange Bullet', default=True)
    bullet_star = fields.Boolean(string='Star Bullet', default=False)
    bullet_clock = fields.Boolean(string='Clock Bullet', default=False)
    
    # Stages
    stage_ids = fields.One2many('project.template.stage', 'template_id', string='Stages')
    
    @api.model
    def get_kanban_examples_data(self):
        """Return configurable examples to be added to the existing kanban examples"""
        templates = self.search([('active', '=', True)])
        examples = []
        
        for template in templates:
            # Build bullets list
            bullets = []
            if template.bullet_green:
                bullets.append('greenBullet')
            if template.bullet_orange:
                bullets.append('orangeBullet')
            if template.bullet_star:
                bullets.append('star')
            if template.bullet_clock:
                bullets.append('clock')
            
            # Get stages
            regular_stages = template.stage_ids.filtered(lambda s: not s.folded)
            folded_stages = template.stage_ids.filtered(lambda s: s.folded)
            
            example_data = {
                'name': template.name,
                'columns': [stage.name for stage in regular_stages.sorted('sequence')],
                'foldedColumns': [stage.name for stage in folded_stages.sorted('sequence')],
                'bullets': bullets,
            }
            
            # Add description if available
            if template.description:
                example_data['description'] = template.description
            
            examples.append(example_data)
        
        return {
            'examples': examples,
        }