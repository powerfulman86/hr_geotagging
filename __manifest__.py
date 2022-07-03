# -*- coding: utf-8 -*-
{
    'name': "hr Geo-Tagging Attendance",

    'summary': """
           """,

    'description': """
       """,

    'author': "",
    'website': "",

    'category': 'Human Resources',
    'version': '13.0.0',

    # any module necessary for this one to work correctly
    'depends': ['base', 'hr', 'om_hr_payroll', 'hr_holidays', 'hr_attendance'],
    # always loaded
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/data.xml',
        'wizard/change_att_data_view.xml',
        'views/hr_attendance_sheet_view.xml',
        'views/att_sheet_batch_view.xml',
        'views/hr_attendance_policy_view.xml',
        'views/hr_public_holiday_view.xml',
        'views/hr_employee.xml',
        'views/views.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
