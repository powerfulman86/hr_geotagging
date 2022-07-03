# -*- coding: utf-8 -*-

from dateutil.relativedelta import relativedelta
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
import re
from datetime import datetime


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    attendance_policy = fields.Selection(string="Attendance Policy",
                                         selection=[('byemployee', 'By Employee'), ('bydepartment', 'By Department'), ],
                                         default='byemployee', required=False,
                                         config_parameter='base_setup.attendance_policy')


class HrDepartment(models.Model):
    _inherit = 'hr.department'

    att_policy_id = fields.Many2one('hr.attendance.policy', string='Attendance Policy')


class HrContract(models.Model):
    _inherit = 'hr.contract'

    att_policy_id = fields.Many2one('hr.attendance.policy', string='Attendance Policy')


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    age = fields.Integer(string="Age", compute="_calculate_age", readonly=True, store='True')

    @api.depends("birthday")
    def _calculate_age(self):
        for emp in self:
            if emp.birthday:
                dob = emp.birthday
                emp.age = int((datetime.today().date() - dob).days / 365)
            else:
                emp.age = 0

    @api.onchange('emergency_phone', 'phone', 'work_phone', 'mobile_phone')
    def check_phone_format(self):
        pattern = r"^[0-9]{11}"
        if self.emergency_phone:
            if not re.match(pattern, self.emergency_phone):
                raise ValidationError(_("emergency Phone Format isn't correct"))
        if self.phone:
            if not re.match(pattern, self.phone):
                raise ValidationError(_("Phone Format isn't correct"))
        if self.work_phone:
            if not re.match(pattern, self.work_phone):
                raise ValidationError(_("Work Phone Format isn't correct"))
        if self.mobile_phone:
            if not re.match(pattern, self.mobile_phone):
                raise ValidationError(_("Mobile Phone Format isn't correct"))

    @api.constrains('work_email', 'private_email')
    def constraints_email(self):
        pattern = r"\"?([-a-zA-Z0-9.`?{}]+@\w+\.\w+)\"?"
        if self.work_email:
            if not re.match(pattern, self.work_email):
                raise ValidationError(_("Enter Valid Working E-mail"))
        if self.private_email:
            if not re.match(pattern, self.private_email):
                raise ValidationError(_("Enter Valid Private E-mail"))

    @api.constrains('identification_id')
    def constrains_identification_id(self):
        for rec in self:
            if rec.identification_id:
                if not rec.identification_id.isdecimal():
                    raise ValidationError(_("National ID Accept Only Digit"))
                employee_ids = self.env['hr.employee'].search([('identification_id', '=', rec.identification_id)])
                if len(employee_ids.ids) > 1:
                    raise ValidationError(_("Can not Duplicate National ID"))
                if len(rec.identification_id) != 14:
                    raise ValidationError(_("National ID Must be 14 Digit"))

    @api.model
    def _cron_employee_age(self):
        self._calculate_age()
