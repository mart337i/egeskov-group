# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class PortfolioController(http.Controller):

    @http.route('/', type='http', auth='public')
    def portfolio_home(self, **kwargs):
        return request.render('me_portfolio_website.portfolio_landing_page')

    @http.route('/portfolio', type='http', auth='public')
    def portfolio_page(self, **kwargs):
        return request.render('me_portfolio_website.portfolio_landing_page')