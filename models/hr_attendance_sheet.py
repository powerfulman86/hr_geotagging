# -*- coding: utf-8 -*-

##############################################################################
#
#
#    Copyright (C) 2020-TODAY .
#    Author: Eng.Ramadan Khalil (<rkhalil1990@gmail.com>)
#
#    It is forbidden to publish, distribute, sublicense, or sell copies
#    of the Software or modified copies of the Software.
#
##############################################################################

import pytz
from datetime import datetime, date, timedelta, time
from dateutil.relativedelta import relativedelta
from odoo import models, fields, tools, api, exceptions, _
from odoo.exceptions import UserError, ValidationError
import babel

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
TIME_FORMAT = "%H:%M:%S"


class AttendanceSheet(models.Model):
    _name = 'attendance.sheet'
    _description = 'Hr Attendance Sheet'

    name = fields.Char("name")
    employee_id = fields.Many2one(comodel_name='hr.employee', string='Employee',
                                  required=True)
    department_id = fields.Many2one(related='employee_id.department_id',
                                    string='Department', store=True)
    date_from = fields.Date(string='Date From', readonly=True, required=True,
                            default=lambda self: fields.Date.to_string(
                                date.today().replace(day=1)), )
    date_to = fields.Date(string='Date To', readonly=True, required=True,
                          default=lambda self: fields.Date.to_string(
                              (datetime.now() + relativedelta(months=+1, day=1, days=-1)).date()))
    att_sheet_line_ids = fields.One2many(comodel_name='attendance.sheet.line',
                                         string='Attendances', readonly=True,
                                         inverse_name='att_sheet_id')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirm', 'Confirmed'),
        ('done', 'Approved')], default='draft', track_visibility='onchange',
        string='Status', required=True, readonly=True, index=True,
        help=' * The \'Draft\' status is used when a HR user is creating a new  attendance sheet. '
             '\n* The \'Confirmed\' status is used when  attendance sheet is confirmed by HR user.'
             '\n* The \'Approved\' status is used when  attendance sheet is accepted by the HR Manager.')
    no_overtime = fields.Integer(compute="calculate_att_data", string="No of overtimes", readonly=True, store=True)
    tot_overtime = fields.Float(compute="calculate_att_data", string="Total Over Time", readonly=True, store=True)
    tot_difftime = fields.Float(compute="calculate_att_data", string="Total Diff time Hours", readonly=True, store=True)
    no_difftime = fields.Integer(compute="calculate_att_data", string="No of Diff Times", readonly=True, store=True)
    tot_late = fields.Float(compute="calculate_att_data", string="Total Late In", readonly=True, store=True)
    no_late = fields.Integer(compute="calculate_att_data", string="No of Lates", readonly=True, store=True)
    no_absence = fields.Integer(compute="calculate_att_data", string="No of Absence Days", readonly=True, store=True)
    tot_absence = fields.Float(compute="calculate_att_data", string="Total absence Hours", readonly=True, store=True)
    att_policy_id = fields.Many2one(comodel_name='hr.attendance.policy',
                                    string="Attendance Policy ", required=True)
    payslip_id = fields.Many2one(comodel_name='hr.payslip', string='PaySlip')
    batch_id = fields.Many2one(comodel_name='attendance.sheet.batch', string='Attendance Sheet Batch')
    contract_id = fields.Many2one('hr.contract', string='Contract', readonly=True,
                                  states={'draft': [('readonly', False)]})

    def unlink(self):
        if any(self.filtered(
                lambda att: att.state not in ('draft', 'confirm'))):
            raise UserError(_('You cannot delete an attendance sheet which is not draft or confirmed!'))
        return super(AttendanceSheet, self).unlink()

    @api.constrains('date_from', 'date_to')
    def check_date(self):
        for sheet in self:
            emp_sheets = self.env['attendance.sheet'].search(
                [('employee_id', '=', sheet.employee_id.id)])
            for emp_sheet in emp_sheets:
                if sheet.id == emp_sheet.id:
                    continue
                if max(sheet.date_from, emp_sheet.date_from) < min(
                        sheet.date_to, emp_sheet.date_to):
                    raise UserError(_(
                        'You Have Already Attendance Sheet For That Period  Please pick another date !'))

    def action_attsheet_confirm(self):
        self.calculate_att_data()
        self.write({'state': 'confirm'})

    def action_attsheet_approve(self):
        self.create_payslip()
        self.write({'state': 'done'})

    def action_attsheet_draft(self):
        self.write({'state': 'draft'})

    @api.onchange('employee_id', 'date_from', 'date_to')
    def onchange_employee(self):
        if (not self.employee_id) or (not self.date_from) or (not self.date_to):
            return
        employee = self.employee_id
        date_from = self.date_from
        date_to = self.date_to
        ttyme = datetime.combine(fields.Date.from_string(date_from), time.min)
        locale = self.env.context.get('lang', 'en_US')
        if locale == "ar_SY":
            locale = "ar"
        self.name = _('Attendance Sheet of %s for %s') % (employee.name,
                                                          tools.ustr(
                                                              babel.dates.format_date(
                                                                  date=ttyme,
                                                                  format='MMMM-y',
                                                                  locale=locale)))
        self.company_id = employee.company_id
        company_attendance_policy = float(self.env['ir.config_parameter'].sudo().get_param(
            'base_setup.attendance_policy'))
        if company_attendance_policy == 'byemployee':
            contract_ids = self.env['hr.payslip'].get_contract(employee, date_from, date_to)
            if not contract_ids:
                return
            self.contract_id = self.env['hr.contract'].browse(contract_ids[0])
            if not self.contract_id.att_policy_id:
                raise ValidationError(_("Employee %s does not have attendance policy" % employee.name))
            self.att_policy_id = self.contract_id.att_policy_id
        elif company_attendance_policy =='bydepartment':
            if not self.employee_id.department_id.att_policy_id:
                raise ValidationError(_("Department %s does not have attendance policy" % employee.department_id.name))
            self.att_policy_id = self.employee_id.department_id.att_policy_id

    def calculate_att_data(self):
        overtime = 0
        no_overtime = 0
        late = 0
        no_late = 0
        diff = 0
        no_diff = 0
        tot_wh = 0
        no_wd = 0
        absence_hours = 0
        no_absence = 0
        for att_sheet in self:

            for line in att_sheet.att_sheet_line_ids:
                # print line.date
                if line.overtime > 0:
                    overtime += line.overtime
                    no_overtime = no_overtime + 1
                if line.diff_time > 0:
                    if line.status == "ab":
                        no_absence += 1
                        absence_hours += line.diff_time
                    else:
                        diff += line.diff_time
                        no_diff += 1
                if line.late_in > 0:
                    late += line.late_in
                    no_late += 1
                if line.worked_hours > 0:
                    tot_wh += line.worked_hours
                    no_wd += 1
            values = {
                'tot_overtime': overtime,
                'no_overtime': no_overtime,
                'tot_difftime': diff,
                'no_difftime': no_diff,
                'no_absence': no_absence,
                'tot_absence': absence_hours,
                'tot_late': late,
                'no_late': no_late,
                # 'tot_wh': tot_wh,
                # 'no_wd': no_wd

            }
            att_sheet.write(values)

    def _get_time_from_float(self, float_type):
        str_off_time = str(float_type)
        official_hour = str_off_time.split('.')[0]
        official_minute = ("%2d" % int(
            str(float("0." + str_off_time.split('.')[1]) * 60).split('.')[
                0])).replace(' ', '0')
        str_off_time = official_hour + ":" + official_minute
        str_off_time = datetime.strptime(str_off_time, "%H:%M").time()
        return str_off_time

    def _get_float_from_time(self, time):
        time_type = datetime.strftime(time, "%H:%M")
        signOnP = [int(n) for n in time_type.split(":")]
        signOnH = signOnP[0] + signOnP[1] / 60.0
        return signOnH

    def get_attendance_intervals(self, emp, day_start, day_end):
        tz_info = fields.Datetime.context_timestamp(self, day_start).tzinfo
        day_st_utc = day_start.replace(tzinfo=tz_info).astimezone(pytz.utc).replace(tzinfo=None)
        str_day_st_utc = datetime.strftime(day_st_utc, DATETIME_FORMAT)
        day_end_utc = day_end.replace(tzinfo=tz_info).astimezone(pytz.utc).replace(tzinfo=None)
        str_day_end_utc = datetime.strftime(day_end_utc, DATETIME_FORMAT)
        res = []
        attendances = self.env['hr.attendance'].sudo().search(
            [('employee_id.id', '=', emp.id),
             ('check_in', '>=', str_day_st_utc),
             ('check_in', '<=', str_day_end_utc)],
            order="check_in")
        for att in attendances:
            check_in = att.check_in
            check_out = att.check_out
            if not check_out:
                continue
            res.append((check_in, check_out))
        return res

    def _get_emp_leave_intervals(self, emp, start_datetime=None, end_datetime=None):
        leaves = []
        leave_obj = self.env['hr.leave']
        leave_ids = leave_obj.search([
            ('employee_id', '=', emp.id),
            ('state', '=', 'validate')])

        for leave in leave_ids:
            date_from = leave.date_from
            if end_datetime and date_from > end_datetime:
                continue
            date_to = leave.date_to
            if start_datetime and date_to < start_datetime:
                continue
            leaves.append((date_from, date_to))
        return leaves

    def get_public_holiday(self, date, emp):
        public_holiday = []
        public_holidays = self.env['hr.public.holiday'].sudo().search(
            [('date_from', '<=', date), ('date_to', '>=', date),
             ('state', '=', 'active')])
        for ph in public_holidays:
            print('ph is', ph.name, [e.name for e in ph.emp_ids])
            if not ph.emp_ids:
                return public_holidays
            if emp.id in ph.emp_ids.ids:
                public_holiday.append(ph.id)
        # print str(public_holiday)
        return public_holiday

    def get_attendances(self):
        for att_sheet in self:
            att_sheet.att_sheet_line_ids.unlink()
            att_line = self.env["attendance.sheet.line"]
            from_date = att_sheet.date_from
            to_date = att_sheet.date_to
            emp = att_sheet.employee_id
            tz = pytz.timezone(self.env.user.tz)
            if not tz:
                raise exceptions.Warning("Please add time zone for the current user %s" % self.env.user.name)
            calendar_id = emp.contract_id.resource_calendar_id
            if not calendar_id:
                raise ValidationError(_('Please add working hours to the %s `s contract ' % emp.name))

            policy_id = att_sheet.att_policy_id
            if not policy_id:
                raise ValidationError(_('Please add Attendance Policy to the %s `s contract ' % emp.name))

            all_dates = [(from_date + timedelta(days=x)) for x in
                         range((to_date - from_date).days + 1)]
            abs_cnt = 0
            for day in all_dates:
                day_start = datetime(day.year, day.month, day.day)
                tz_info = fields.Datetime.context_timestamp(self, fields.Datetime.from_string(day_start)).tzinfo
                print('day is', day, type(day))
                day_end = day_start.replace(hour=23, minute=59, second=59)
                day_str = str(day.weekday())
                date = day.strftime('%Y-%m-%d')
                work_intervals = calendar_id.att_get_work_intervals(day_start, day_end)
                attendance_intervals = self.get_attendance_intervals(emp, day_start, day_end)
                leaves = self._get_emp_leave_intervals(emp, day_start, day_end)
                public_holiday = self.get_public_holiday(date, emp)
                reserved_intervals = []
                overtime_policy = policy_id.get_overtime()
                abs_flag = False
                if work_intervals:
                    if public_holiday:
                        if attendance_intervals:
                            for attendance_interval in attendance_intervals:
                                overtime = attendance_interval[1] - attendance_interval[0]
                                float_overtime = overtime.total_seconds() / 3600
                                if float_overtime <= overtime_policy['ph_after']:
                                    act_float_overtime = float_overtime = 0
                                else:
                                    act_float_overtime = (float_overtime - overtime_policy['ph_after'])
                                    float_overtime = (float_overtime -
                                                      overtime_policy[
                                                          'ph_after']) * \
                                                     overtime_policy['ph_rate']
                                ac_sign_in = pytz.utc.localize(attendance_interval[0]).astimezone(tz)
                                float_ac_sign_in = self._get_float_from_time(ac_sign_in)
                                ac_sign_out = pytz.utc.localize(attendance_interval[1]).astimezone(tz)
                                worked_hours = attendance_interval[1] - attendance_interval[0]
                                float_worked_hours = worked_hours.total_seconds() / 3600
                                float_ac_sign_out = float_ac_sign_in + float_worked_hours
                                values = {
                                    'date': date,
                                    'day': day_str,
                                    'ac_sign_in': float_ac_sign_in,
                                    'ac_sign_out': float_ac_sign_out,
                                    'worked_hours': float_worked_hours,
                                    'o_worked_hours': float_worked_hours,
                                    'overtime': float_overtime,
                                    'act_overtime': float_overtime,
                                    'att_sheet_id': self.id,
                                    'status': 'ph',
                                    'note': _("working on Public Holiday")
                                }
                                att_line.create(values)
                        else:
                            values = {
                                'date': date,
                                'day': day_str,
                                'att_sheet_id': self.id,
                                'status': 'ph',
                            }
                            att_line.create(values)
                    else:
                        for i, work_interval in enumerate(work_intervals):
                            float_worked_hours = 0
                            att_work_intervals = []
                            diff_intervals = []
                            late_in_interval = []
                            diff_time = timedelta(hours=00, minutes=00, seconds=00)
                            late_in = timedelta(hours=00, minutes=00, seconds=00)
                            overtime = timedelta(hours=00, minutes=00, seconds=00)
                            for j, att_interval in enumerate(attendance_intervals):
                                if max(work_interval[0], att_interval[0]) < min(work_interval[1], att_interval[1]):
                                    current_att_interval = att_interval
                                    if i + 1 < len(work_intervals):
                                        next_work_interval = work_intervals[i + 1]
                                        if max(next_work_interval[0], current_att_interval[0]) < min(
                                                next_work_interval[1], current_att_interval[1]):
                                            split_att_interval = (next_work_interval[0], current_att_interval[1])
                                            current_att_interval = (current_att_interval[0], next_work_interval[0])
                                            attendance_intervals[j] = current_att_interval
                                            attendance_intervals.insert(j + 1, split_att_interval)
                                    att_work_intervals.append(current_att_interval)
                            reserved_intervals += att_work_intervals
                            pl_sign_in = self._get_float_from_time(pytz.utc.localize(work_interval[0]).astimezone(tz))
                            pl_sign_out = self._get_float_from_time(pytz.utc.localize(work_interval[1]).astimezone(tz))
                            pl_sign_in_time = pytz.utc.localize(work_interval[0]).astimezone(tz)
                            pl_sign_out_time = pytz.utc.localize(work_interval[1]).astimezone(tz)
                            ac_sign_in = 0
                            ac_sign_out = 0
                            status = ""
                            note = ""
                            if att_work_intervals:
                                if len(att_work_intervals) > 1:
                                    # print("there is more than one interval for that work interval")
                                    late_in_interval = (work_interval[0], att_work_intervals[0][0])
                                    overtime_interval = (work_interval[1], att_work_intervals[-1][1])
                                    if overtime_interval[1] < overtime_interval[0]:
                                        overtime = timedelta(hours=0, minutes=0, seconds=0)
                                    else:
                                        overtime = overtime_interval[1] - overtime_interval[0]
                                    remain_interval = (att_work_intervals[0][1], work_interval[1])
                                    # print'first remain intervals is',remain_interval
                                    for att_work_interval in att_work_intervals:
                                        float_worked_hours += (att_work_interval[1] - att_work_interval[
                                            0]).total_seconds() / 3600
                                        # print'float worked hors is', float_worked_hours
                                        if att_work_interval[1] <= \
                                                remain_interval[0]:
                                            continue
                                        if att_work_interval[0] >= \
                                                remain_interval[1]:
                                            break
                                        if remain_interval[0] < att_work_interval[0] < remain_interval[1]:
                                            diff_intervals.append((remain_interval[0], att_work_interval[0]))
                                            remain_interval = (att_work_interval[1], remain_interval[1])
                                    if remain_interval and remain_interval[0] <= work_interval[1]:
                                        diff_intervals.append((remain_interval[0], work_interval[1]))
                                    ac_sign_in = self._get_float_from_time(
                                        pytz.utc.localize(att_work_intervals[0][0]).astimezone(tz))
                                    ac_sign_out = self._get_float_from_time(
                                        pytz.utc.localize(att_work_intervals[-1][1]).astimezone(tz))
                                    ac_sign_out = ac_sign_in + ((att_work_intervals[-1][1] -
                                                                 att_work_intervals[0][0]).total_seconds() / 3600)
                                else:
                                    late_in_interval = (work_interval[0], att_work_intervals[0][0])
                                    overtime_interval = (work_interval[1], att_work_intervals[-1][1])
                                    if overtime_interval[1] < overtime_interval[0]:
                                        overtime = timedelta(hours=0, minutes=0, seconds=0)
                                        diff_intervals.append((overtime_interval[1], overtime_interval[0]))
                                    else:
                                        overtime = overtime_interval[1] - overtime_interval[0]
                                    ac_sign_in = self._get_float_from_time(
                                        pytz.utc.localize(att_work_intervals[0][0]).astimezone(tz))
                                    ac_sign_out = self._get_float_from_time(
                                        pytz.utc.localize(att_work_intervals[0][1]).astimezone(tz))
                                    worked_hours = att_work_intervals[0][1] - att_work_intervals[0][0]
                                    float_worked_hours = worked_hours.total_seconds() / 3600
                                    ac_sign_out = ac_sign_in + float_worked_hours
                            else:
                                late_in_interval = []
                                diff_intervals.append((work_interval[0], work_interval[1]))

                                status = "ab"
                            if diff_intervals:
                                for diff_in in diff_intervals:
                                    if leaves:
                                        status = "leave"
                                        diff_clean_intervals = calendar_id.att_interval_without_leaves(diff_in, leaves)
                                        for diff_clean in diff_clean_intervals:
                                            diff_time += diff_clean[1] - diff_clean[0]
                                    else:
                                        diff_time += diff_in[1] - diff_in[0]
                            if late_in_interval:
                                if late_in_interval[1] < late_in_interval[0]:
                                    late_in = timedelta(hours=0, minutes=0, seconds=0)
                                else:
                                    if leaves:
                                        late_clean_intervals = calendar_id.att_interval_without_leaves(late_in_interval,
                                                                                                       leaves)
                                        for late_clean in late_clean_intervals:
                                            late_in += late_clean[1] - late_clean[0]
                                    else:
                                        late_in = late_in_interval[1] - late_in_interval[0]
                            float_overtime = overtime.total_seconds() / 3600
                            if float_overtime <= overtime_policy['wd_after']:
                                act_float_overtime = float_overtime = 0
                            else:
                                float_overtime = float_overtime * overtime_policy['wd_rate']
                                act_float_overtime = (float_overtime - overtime_policy['wd_after'])
                                float_overtime = float_overtime * overtime_policy['wd_rate']
                            float_late = late_in.total_seconds() / 3600
                            act_float_late = late_in.total_seconds() / 3600
                            policy_late = policy_id.get_late(float_late)
                            float_diff = diff_time.total_seconds() / 3600
                            if status == 'ab':
                                if not abs_flag:
                                    abs_cnt += 1
                                abs_flag = True

                                act_float_diff = float_diff
                                float_diff = policy_id.get_absence(float_diff, abs_cnt)
                            else:
                                act_float_diff = float_diff
                                float_diff = policy_id.get_diff(float_diff)
                            values = {
                                'date': date,
                                'day': day_str,
                                'pl_sign_in': pl_sign_in,
                                'pl_sign_out': pl_sign_out,
                                'ac_sign_in': ac_sign_in,
                                'ac_sign_out': ac_sign_out,
                                'late_in': policy_late,
                                'act_late_in': act_float_late,
                                'overtime': float_overtime,
                                'act_overtime': act_float_overtime,
                                'diff_time': float_diff,
                                'act_diff_time': act_float_diff,
                                'status': status,
                                'att_sheet_id': self.id
                            }
                            att_line.create(values)
                        out_work_intervals = [x for x in attendance_intervals if
                                              x not in reserved_intervals]
                        if out_work_intervals:
                            for att_out in out_work_intervals:
                                overtime = att_out[1] - att_out[0]
                                ac_sign_in = self._get_float_from_time(pytz.utc.localize(att_out[0]).astimezone(tz))
                                ac_sign_out = self._get_float_from_time(pytz.utc.localize(att_out[1]).astimezone(tz))
                                float_worked_hours = overtime.total_seconds() / 3600
                                ac_sign_out = ac_sign_in + float_worked_hours
                                float_overtime = overtime.total_seconds() / 3600
                                if float_overtime <= overtime_policy['wd_after']:
                                    float_overtime = act_float_overtime = 0
                                else:
                                    act_float_overtime = (float_overtime - overtime_policy['ph_after'])
                                    float_overtime = float_overtime * overtime_policy['wd_rate']
                                values = {
                                    'date': date,
                                    'day': day_str,
                                    'pl_sign_in': 0,
                                    'pl_sign_out': 0,
                                    'ac_sign_in': ac_sign_in,
                                    'ac_sign_out': ac_sign_out,
                                    'overtime': float_overtime,
                                    'worked_hours': float_worked_hours,
                                    'act_overtime': act_float_overtime,
                                    'note': _("overtime out of work intervals"),
                                    'att_sheet_id': self.id
                                }
                                att_line.create(values)
                else:
                    if attendance_intervals:
                        # print "thats weekend be over time "
                        for attendance_interval in attendance_intervals:
                            overtime = attendance_interval[1] - attendance_interval[0]
                            ac_sign_in = pytz.utc.localize(attendance_interval[0]).astimezone(tz)
                            ac_sign_out = pytz.utc.localize(attendance_interval[1]).astimezone(tz)
                            float_overtime = overtime.total_seconds() / 3600
                            if float_overtime <= overtime_policy['we_after']:
                                float_overtime = 0
                            else:
                                act_float_overtime = (float_overtime - overtime_policy['we_after'])
                                float_overtime = float_overtime * overtime_policy['we_rate']
                            ac_sign_in = pytz.utc.localize(attendance_interval[0]).astimezone(tz)
                            ac_sign_out = pytz.utc.localize(attendance_interval[1]).astimezone(tz)
                            worked_hours = attendance_interval[1] - attendance_interval[0]
                            float_worked_hours = worked_hours.total_seconds() / 3600
                            values = {
                                'date': date,
                                'day': day_str,
                                'ac_sign_in': self._get_float_from_time(ac_sign_in),
                                'ac_sign_out': self._get_float_from_time(ac_sign_out),
                                'overtime': float_overtime,
                                'act_overtime': float_overtime,
                                'worked_hours': float_worked_hours,
                                'att_sheet_id': self.id,
                                'status': 'weekend',
                                'note': _("working in weekend")
                            }
                            att_line.create(values)
                    else:
                        values = {
                            'date': date,
                            'day': day_str,
                            'att_sheet_id': self.id,
                            'status': 'weekend',
                            'note': ""
                        }
                        att_line.create(values)

    def action_payslip(self):
        self.ensure_one()
        payslip_id = self.payslip_id
        if not payslip_id:
            payslip_id = self.create_payslip()[0]
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payslip',
            'view_mode': 'form',
            'view_type': 'form',
            'res_id': payslip_id.id,
            'views': [(False, 'form')],
        }

    def create_payslip(self):
        payslips = self.env['hr.payslip']
        for att_sheet in self:
            if att_sheet.payslip_id:
                continue
            from_date = att_sheet.date_from
            to_date = att_sheet.date_to
            employee = att_sheet.employee_id
            slip_data = self.env['hr.payslip'].onchange_employee_id(from_date,
                                                                    to_date,
                                                                    employee.id,
                                                                    contract_id=False)
            contract_id = slip_data['value'].get('contract_id')
            if not contract_id:
                raise exceptions.Warning(
                    'There is No Contracts for %s That covers the period of the Attendance sheet' % employee.name)
            worked_days_line_ids = slip_data['value'].get('worked_days_line_ids')

            overtime = [{
                'name': "Overtime",
                'code': 'OVT',
                'contract_id': contract_id,
                'sequence': 30,
                'number_of_days': att_sheet.no_overtime,
                'number_of_hours': att_sheet.tot_overtime,
            }]
            absence = [{
                'name': "Absence",
                'code': 'ABS',
                'contract_id': contract_id,
                'sequence': 35,
                'number_of_days': att_sheet.no_absence,
                'number_of_hours': att_sheet.tot_absence,
            }]
            late = [{
                'name': "Late In",
                'code': 'LATE',
                'contract_id': contract_id,
                'sequence': 40,
                'number_of_days': att_sheet.no_late,
                'number_of_hours': att_sheet.tot_late,
            }]
            difftime = [{
                'name': "Difference time",
                'code': 'DIFFT',
                'contract_id': contract_id,
                'sequence': 45,
                'number_of_days': att_sheet.no_difftime,
                'number_of_hours': att_sheet.tot_difftime,
            }]
            worked_days_line_ids += overtime + late + absence + difftime

            res = {
                'employee_id': employee.id,
                'name': slip_data['value'].get('name'),
                'struct_id': slip_data['value'].get('struct_id'),
                'contract_id': contract_id,
                'input_line_ids': [(0, 0, x) for x in
                                   slip_data['value'].get('input_line_ids')],
                'worked_days_line_ids': [(0, 0, x) for x in
                                         worked_days_line_ids],
                'date_from': from_date,
                'date_to': to_date,
            }
            print(res)
            new_payslip = self.env['hr.payslip'].create(res)
            att_sheet.payslip_id = new_payslip
            payslips += new_payslip
        return payslips


class AttendanceSheetLine(models.Model):
    _name = 'attendance.sheet.line'
    _description = 'Attendance Sheet Line'

    state = fields.Selection([
        ('draft', 'Draft'),
        ('sum', 'Summary'),
        ('confirm', 'Confirmed'),
        ('done', 'Approved')], related='att_sheet_id.state', store=True, )

    date = fields.Date("Date")
    day = fields.Selection([
        ('0', 'Monday'),
        ('1', 'Tuesday'),
        ('2', 'Wednesday'),
        ('3', 'Thursday'),
        ('4', 'Friday'),
        ('5', 'Saturday'),
        ('6', 'Sunday')
    ], 'Day of Week', required=True, index=True, )
    att_sheet_id = fields.Many2one(comodel_name='attendance.sheet',
                                   ondelete="cascade",
                                   string='Attendance Sheet', readonly=True)
    employee_id = fields.Many2one(related='att_sheet_id.employee_id', string='Employee')
    pl_sign_in = fields.Float("Planned sign in", readonly=True)
    pl_sign_out = fields.Float("Planned sign out", readonly=True)
    worked_hours = fields.Float("Worked Hours", readonly=True)
    ac_sign_in = fields.Float("Actual sign in", readonly=True)
    ac_sign_out = fields.Float("Actual sign out", readonly=True)
    overtime = fields.Float("Overtime", readonly=True)
    act_overtime = fields.Float("Actual Overtime", readonly=True)
    late_in = fields.Float("Late In", readonly=True)
    diff_time = fields.Float("Diff Time", help="Diffrence between the working time and attendance time(s) ",
                             readonly=True)
    act_late_in = fields.Float("Actual Late In", readonly=True)
    act_diff_time = fields.Float("Actual Diff Time", help="Diffrence between the working time and attendance time(s) ",
                                 readonly=True)
    status = fields.Selection(string="Status",
                              selection=[('ab', 'Absence'),
                                         ('weekend', 'Week End'),
                                         ('ph', 'Public Holiday'),
                                         ('leave', 'Leave'), ],
                              required=False, readonly=True)
    note = fields.Text("Note", readonly=True)
