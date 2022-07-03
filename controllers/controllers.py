# -*- coding: utf-8 -*-
# from odoo import http


# class HrGeotagging(http.Controller):
#     @http.route('/hr_geotagging/hr_geotagging/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/hr_geotagging/hr_geotagging/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('hr_geotagging.listing', {
#             'root': '/hr_geotagging/hr_geotagging',
#             'objects': http.request.env['hr_geotagging.hr_geotagging'].search([]),
#         })

#     @http.route('/hr_geotagging/hr_geotagging/objects/<model("hr_geotagging.hr_geotagging"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('hr_geotagging.object', {
#             'object': obj
#         })
