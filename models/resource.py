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
from datetime import timedelta
from operator import itemgetter
from odoo import api, fields, models, _
from odoo.addons.resource.models.resource import float_to_time


class ResourceCalendar(models.Model):
    _inherit = "resource.calendar"

    def _get_day_attendances(self, day_date, start_time, end_time):
        self.ensure_one()
        weekday = day_date.weekday()
        attendances = self.env['resource.calendar.attendance']

        for attendance in self.attendance_ids.filtered(
                lambda att:
                int(att.dayofweek) == weekday and
                not (att.date_from and fields.Date.from_string(
                    att.date_from) > day_date) and
                not (att.date_to and fields.Date.from_string(
                    att.date_to) < day_date)):
            if start_time and float_to_time(attendance.hour_to) < start_time:
                continue
            if end_time and float_to_time(attendance.hour_from) > end_time:
                continue
            attendances |= attendance
        return attendances

    def att_get_work_intervals(self, day_start, day_end):
        tz_info = fields.Datetime.context_timestamp(self, day_start).tzinfo
        day_start_utc = day_start.replace(tzinfo=tz_info)
        day_end_utc = day_end.replace(tzinfo=tz_info)
        att_work_intervals = self._attendance_intervals(day_start_utc,
                                                        day_end_utc)
        day_wrok_att = self._get_day_attendances(day_start.date(),
                                                 day_start.replace(hour=0,
                                                                   minute=0,
                                                                   second=0).time(),
                                                 day_end.time())
        working_intervals = []

        for att in self._get_day_attendances(day_start.date(),
                                             day_start.replace(hour=0, minute=0,
                                                               second=0).time(),
                                             day_end.time()):
            dt_f = day_start.replace(hour=0, minute=0, second=0) + timedelta(
                seconds=(att.hour_from * 3600))
            if dt_f < day_start:
                dt_f = day_start
            dt_t = day_start.replace(hour=0, minute=0, second=0) + timedelta(
                seconds=(att.hour_to * 3600))
            if dt_t > day_end:
                dt_t = day_end
            working_interval = (dt_f, dt_t)
            working_interval_tz = (
                dt_f.replace(tzinfo=tz_info).astimezone(pytz.UTC).replace(
                    tzinfo=None),
                dt_t.replace(tzinfo=tz_info).astimezone(pytz.UTC).replace(
                    tzinfo=None))
            working_intervals.append(working_interval_tz)
        clean_work_intervals = self.att_interval_clean(working_intervals)

        return clean_work_intervals

    def att_interval_clean(self, intervals):
        intervals = sorted(intervals,
                           key=itemgetter(0))  # sort on first datetime
        cleaned = []
        working_interval = None
        while intervals:
            current_interval = intervals.pop(0)
            if not working_interval:  # init
                working_interval = [current_interval[0], current_interval[1]]
            elif working_interval[1] < current_interval[
                0]:  # interval is disjoint
                cleaned.append(tuple(working_interval))
                working_interval = [current_interval[0], current_interval[1]]
            elif working_interval[1] < current_interval[
                1]:  # union of greater intervals
                working_interval[1] = current_interval[1]
        if working_interval:  # handle void lists
            cleaned.append(tuple(working_interval))
        return cleaned

    def att_interval_without_leaves(self, interval, leave_intervals):
        if not interval:
            return interval
        if leave_intervals is None:
            leave_intervals = []
        intervals = []
        leave_intervals = self.att_interval_clean(leave_intervals)
        current_interval = [interval[0], interval[1]]
        for leave in leave_intervals:
            if leave[1] <= current_interval[0]:
                continue
            if leave[0] >= current_interval[1]:
                break
            if current_interval[0] < leave[0] < current_interval[1]:
                current_interval[1] = leave[0]
                intervals.append((current_interval[0], current_interval[1]))
                current_interval = [leave[1], interval[1]]
            if current_interval[0] <= leave[1]:
                current_interval[0] = leave[1]
        if current_interval and current_interval[0] < interval[
            1]:  # remove intervals moved outside base interval due to leaves
            intervals.append((current_interval[0], current_interval[1]))
        return intervals
