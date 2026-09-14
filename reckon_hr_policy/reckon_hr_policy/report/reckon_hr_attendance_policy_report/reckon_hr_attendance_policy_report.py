import frappe
from frappe.utils import getdate

from reckon_hr_policy.attendance.summary import collect
from reckon_hr_policy.utils.settings import require_manager, settings


def execute(filters=None):
    require_manager()
    filters = frappe._dict(filters or {})
    if filters.payroll_period:
        period = frappe.get_doc("Payroll Period", filters.payroll_period)
        period.check_permission("read")
        filters.from_date = filters.from_date or period.start_date
        filters.to_date = filters.to_date or period.end_date
    if not filters.from_date or not filters.to_date:
        frappe.throw("From Date and To Date are required")
    if getdate(filters.from_date) > getdate(filters.to_date):
        frappe.throw("From Date must precede To Date")
    employee_filters = {}
    for name in ("department", "branch", "company"):
        if filters.get(name):
            employee_filters[name] = filters[name]
    if filters.employee:
        employee_filters["name"] = filters.employee
    columns = [
        dict(fieldname="employee", label="Employee", fieldtype="Link", options="Employee", width=150),
        dict(fieldname="employee_name", label="Employee Name", fieldtype="Data", width=160),
    ]
    columns += [
        dict(fieldname=k, label=k.replace("_", " ").title(), fieldtype="Float", width=130)
        for k in (
            "late_entries",
            "early_exits",
            "break_violations",
            "late_deduction_days",
            "early_deduction_days",
            "break_deduction_days",
            "total_deduction_days",
            "early_entry_ot_minutes",
            "ot_amount",
        )
    ]
    data, offset = [], 0
    s = settings()
    while True:
        # get_list enforces User Permissions/company/employee restrictions.
        employees = frappe.get_list(
            "Employee",
            filters=employee_filters,
            fields=["name", "employee_name", "company", "rhp_payroll_type", "rhp_attendance_policy"],
            order_by="name",
            limit_start=offset,
            limit_page_length=200,
        )
        if not employees:
            break
        results = collect(employees, filters.from_date, filters.to_date, s)
        data.extend(
            row
            for row in results.values()
            if (not filters.payroll_type or row["payroll_type"] == filters.payroll_type)
            and (not filters.attendance_policy or row["attendance_policy"] == filters.attendance_policy)
        )
        offset += len(employees)
    return (
        columns,
        data,
        "Live attendance preview using current policy and employee categories. Submitted Salary Slip snapshots are authoritative. OT amounts are in each employee's Salary Slip currency; do not sum across currencies.",
    )
