app_name = "reckon_hr_policy"
app_title = "Reckon HR Policy"
app_publisher = "Reckon"
app_description = "Configurable attendance and payroll policies"
app_email = ""
app_license = "GPL-3.0-or-later"
required_apps = ["frappe", "erpnext", "hrms"]

before_install = "reckon_hr_policy.setup.compatibility.check"
before_migrate = "reckon_hr_policy.setup.compatibility.check"
after_install = "reckon_hr_policy.setup.install.setup"
after_migrate = "reckon_hr_policy.setup.install.setup"
before_uninstall = "reckon_hr_policy.setup.install.before_uninstall"

extend_doctype_class = {
    "Salary Slip": ["reckon_hr_policy.payroll.salary_slip.PolicySalarySlipMixin"],
    "Salary Structure Assignment": ["reckon_hr_policy.payroll.assignment.PolicyAssignmentMixin"],
    "Employee Checkin": ["reckon_hr_policy.attendance.checkout.PolicyCheckinMixin"],
}
doc_events = {
    "Company": {"after_insert": "reckon_hr_policy.setup.native.company_created"},
    "Employee": {
        "validate": "reckon_hr_policy.setup.employees.validate_employee",
        "on_update": "reckon_hr_policy.setup.employees.on_employee_update",
    },
    "Salary Slip": {"on_submit": "reckon_hr_policy.payroll.audit.freeze"},
    "Salary Structure Assignment": {"before_validate": "reckon_hr_policy.payroll.assignment.defaults"},
    "Additional Salary": {"validate": "reckon_hr_policy.payroll.salary_slip.reject_reserved_components"},
    "Salary Structure": {"validate": "reckon_hr_policy.payroll.salary_slip.reject_structure_policy_rows"},
}
scheduler_events = {
    "hourly": ["reckon_hr_policy.attendance.checkout.run"],
    "daily": ["reckon_hr_policy.setup.employees.maintain"],
}
