"""Fail closed on an unsupported host, before creating site data."""

import inspect

import frappe

MINIMUMS = {"frappe": (16, 33, 1), "erpnext": (16, 34, 2), "hrms": (16, 18, 1)}
REQUIRED_FIELDS = {
    "Employee": "company salary_currency default_shift date_of_joining relieving_date",
    "Employee Checkin": "employee time log_type shift shift_start shift_end skip_auto_attendance offshift attendance",
    "Attendance": "employee attendance_date status late_entry early_exit shift docstatus",
    "Shift Type": "start_time end_time enable_auto_attendance auto_update_last_sync process_attendance_after last_sync_of_checkin enable_late_entry_marking late_entry_grace_period enable_early_exit_marking early_exit_grace_period",
    "Shift Assignment": "employee company shift_type start_date end_date status",
    "Holiday List Assignment": "applicable_for assigned_to holiday_list from_date",
    "Salary Component": "salary_component salary_component_abbr type depends_on_payment_days accounts",
    "Salary Structure": "company currency earnings deductions salary_slip_based_on_timesheet salary_component hour_rate",
    "Salary Structure Assignment": "employee from_date base salary_structure currency",
    "Salary Slip": "employee company currency start_date end_date total_working_days payment_days earnings deductions timesheets",
    "Payroll Entry": "employees salary_slip_based_on_timesheet payroll_payable_account",
    "Timesheet": "employee total_hours start_date end_date salary_slip",
}


def check():
    from importlib import import_module

    versions = {}
    for app, minimum in MINIMUMS.items():
        module = import_module(app)
        versions[app] = module.__version__
        parts = tuple(int(p) for p in module.__version__.split("-")[0].split(".")[:3])
        if parts[0] != 16 or parts < minimum:
            frappe.throw(
                f"Reckon HR Policy needs {app} >= {'.'.join(map(str, minimum))}, <17; found {module.__version__}"
            )
    from frappe.model.base_document import _get_extended_class
    from hrms.payroll.doctype.salary_slip.salary_slip import SalarySlip
    from hrms.payroll.doctype.salary_structure_assignment.salary_structure_assignment import (
        SalaryStructureAssignment,
    )

    assert callable(_get_extended_class)
    for cls, method, parameters in (
        (SalarySlip, "calculate_net_pay", {"self", "skip_tax_breakup_computation"}),
        (SalarySlip, "calculate_component_amounts", {"self", "component_type"}),
        (
            SalarySlip,
            "update_component_row",
            {"self", "component_data", "amount", "component_type", "default_amount"},
        ),
        (SalaryStructureAssignment, "get_timesheet_config", {"self"}),
        (SalarySlip, "_get_ssa_doc", {"self"}),
        (SalarySlip, "add_timesheet_earning_component", {"self", "timesheet_config"}),
    ):
        if not hasattr(cls, method) or not parameters <= set(
            inspect.signature(getattr(cls, method)).parameters
        ):
            frappe.throw(
                f"Unsupported core API: {cls.__name__}.{method}. Review integration before upgrading."
            )
    for dt, names in REQUIRED_FIELDS.items():
        meta = frappe.get_meta(dt)
        missing = [n for n in names.split() if n != "docstatus" and not meta.has_field(n)]
        if missing:
            frappe.throw(f"Unsupported {dt} schema: missing {', '.join(missing)}")
    return versions
