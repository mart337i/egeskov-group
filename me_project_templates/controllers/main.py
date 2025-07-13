# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
import json


class ProjectTemplateController(http.Controller):

    @http.route('/project_templates/kanban_examples', type='json', auth='user')
    def get_kanban_examples(self):
        """Return configurable project templates for kanban examples"""
        try:
            ProjectTemplate = request.env['project.template']
            return ProjectTemplate.get_kanban_examples_data()
        except Exception as e:
            return {'examples': []}