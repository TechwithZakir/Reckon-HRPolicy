"""Permission-scoped, read-only employee policy effectiveness dashboard."""

from collections import defaultdict

import frappe
from frappe.utils import getdate

from reckon_hr_policy.attendance.summary import collect
from reckon_hr_policy.policy import strict_pairs
from reckon_hr_policy.reporting.effectiveness import explain
from reckon_hr_policy.utils.settings import require_manager, rules, settings


def execute(filters=None):
    require_manager()
    filters = frappe._dict(filters or {})
    if not filters.from_date or not filters.to_date:
        frappe.throw("From Date and To Date are required")
    start, end = getdate(filters.from_date), getdate(filters.to_date)
    if end < start or (end - start).days > 366:
        frappe.throw("Select a valid date range of at most 367 days")
    s = settings()
    r = rules(s)
    payroll = frappe.get_cached_doc("Payroll Settings")
    employee_filters = {key: filters[key] for key in ("company", "department", "branch") if filters.get(key)}
    if filters.employee:
        employee_filters["name"] = filters.employee
    data, offset = [], 0
    while True:
        employees = frappe.get_list(
            "Employee",
            filters=employee_filters,
            fields=[
                "name",
                "employee_name",
                "company",
                "grade",
                "department",
                "branch",
                "status",
                "date_of_joining",
                "default_shift",
                "salary_currency",
                "rhp_payroll_type",
                "rhp_attendance_policy",
            ],
            order_by="name",
            limit_start=offset,
            limit_page_length=200,
        )
        if not employees:
            break
        offset += len(employees)
        assignments = defaultdict(list)
        for assignment in frappe.get_all(
            "Salary Structure Assignment",
            filters={
                "employee": ["in", [e.name for e in employees]],
                "docstatus": 1,
                "from_date": ["<=", end],
            },
            fields=[
                "name",
                "employee",
                "from_date",
                "salary_structure",
                "currency",
                "rhp_payroll_type",
                "rhp_attendance_policy",
            ],
            order_by="from_date desc,name",
        ):
            assignments[assignment.employee].append(assignment)
        selected = {}
        for employee in employees:
            boundary = max(start, getdate(employee.date_of_joining))
            selected[employee.name] = next(
                (a for a in assignments[employee.name] if a.from_date <= boundary), None
            )
            current = selected[employee.name]
            if current:
                for key in ("rhp_payroll_type", "rhp_attendance_policy"):
                    if current.get(key):
                        employee[key] = current[key]
                employee._rhp_assignment_policy = True
        results = collect(employees, start, end, s)
        for employee in employees:
            summary = results[employee.name]
            if filters.payroll_type and summary["payroll_type"] != filters.payroll_type:
                continue
            if filters.attendance_policy and summary["attendance_policy"] != filters.attendance_policy:
                continue
            boundary = max(start, getdate(employee.date_of_joining))
            invalid = sum(
                1
                for evidence in summary["evidence"]
                if "checkins" in evidence and not strict_pairs(evidence["checkins"])
            )
            row = explain(
                summary,
                r,
                start,
                end,
                getdate(s.policy_effective_from),
                assignment=selected[employee.name],
                assignment_changes=sum(boundary < a.from_date <= end for a in assignments[employee.name]),
                payroll_based_on=payroll.payroll_based_on,
                unmarked_as=payroll.consider_unmarked_attendance_as,
                today=getdate(),
                punch_issues=invalid,
                default_shift=employee.default_shift,
                employee_status=employee.status,
            )
            row.update(
                grade=employee.grade,
                company=employee.company,
                department=employee.department,
                branch=employee.branch,
                currency=(
                    selected[employee.name].currency if selected[employee.name] else employee.salary_currency
                )
                or frappe.get_cached_value("Company", employee.company, "default_currency"),
                invalid_shifts=invalid,
                excluded_shift_count=len(summary["excluded_shifts"]),
                help_action="Smart Help",
            )
            from reckon_hr_policy.setup.grades import mapping

            profile = mapping(employee, s)
            if s.auto_setup_from_grade and not employee.grade:
                row["readiness"] = "Action required"
                row["smart_help"] = (
                    "Assign an Employee Grade from the configured Grade Setup table and save Employee. "
                    + row["smart_help"]
                )
            elif s.auto_setup_from_grade and not profile:
                row["readiness"] = "Action required"
                row["smart_help"] = (
                    "This grade is not mapped for this company. Configure it in Policy Settings → Grade Setup; setup creates missing native masters. "
                    + row["smart_help"]
                )
            elif profile and not (
                profile.hourly_rate if profile.payroll_type == "Hourly" else profile.monthly_salary
            ):
                row["readiness"] = "Action required"
                row["smart_help"] = (
                    "Enter this grade's actual salary/rate once in Policy Settings → Grade Setup, save Settings, and refresh this report. "
                    + row["smart_help"]
                )
            # Do not ship source logs or salary evidence in a grid response unnecessarily.
            row.pop("evidence", None)
            row.pop("excluded_shifts", None)
            if not filters.readiness or row["readiness"] == filters.readiness:
                data.append(row)
    counts = {
        state: sum(row["readiness"] == state for row in data)
        for state in ("Action required", "Review", "Preview available")
    }
    cards = [
        dict(label=state, value=count, indicator=color, datatype="Int")
        for (state, count), color in zip(counts.items(), ("Red", "Orange", "Blue"), strict=True)
    ]
    return (
        columns(),
        data,
        "Read-only preview with current rules and the starting dated salary assignment. Absence/half-day counts are submitted dates, not payroll deduction days. Smart Help explains each row. Final payment days and amounts come from a draft Salary Slip.",
        None,
        cards,
    )


def columns():
    specs = [
        ("employee", "Employee", "Link", "Employee", 150),
        ("employee_name", "Employee Name", "Data", None, 170),
        ("grade", "Employee Grade", "Link", "Employee Grade", 200),
        ("readiness", "Readiness", "Data", None, 140),
        ("policy_status", "Policy Effectiveness", "Data", None, 220),
        ("help_action", "Help", "Data", None, 110),
        ("company", "Company", "Link", "Company", 160),
        ("department", "Department", "Link", "Department", 150),
        ("branch", "Branch", "Link", "Branch", 120),
        ("payroll_type", "Payroll Type", "Data", None, 110),
        ("attendance_policy", "Attendance Policy", "Data", None, 190),
        ("salary_assignment", "Salary Assignment", "Link", "Salary Structure Assignment", 170),
        ("currency", "Currency", "Link", "Currency", 90),
    ]
    result = [
        dict(fieldname=key, label=label, fieldtype=kind, options=options, width=width)
        for key, label, kind, options, width in specs
    ]
    result += [
        dict(fieldname=key, label=label, fieldtype="Float", width=125)
        for key, label in (
            ("submitted_attendance_dates", "Submitted Dates"),
            ("draft_attendance_records", "Draft Records"),
            ("absent_dates", "Absent Dates"),
            ("half_day_dates", "Half-Day Dates"),
            ("on_leave_dates", "On-Leave Dates"),
            ("late_entries", "Late Dates"),
            ("late_deduction_days", "Late Deduction Days"),
            ("early_exits", "Early Dates"),
            ("early_deduction_days", "Early Deduction Days"),
            ("break_violations", "Break Violations"),
            ("break_deduction_days", "Break Deduction Days"),
            ("total_deduction_days", "Total Policy Days"),
            ("early_entry_ot_minutes", "Early OT Minutes"),
            ("ot_blocks", "OT Blocks"),
            ("invalid_shifts", "Invalid Shifts"),
            ("excluded_shift_count", "Excluded Shifts"),
        )
    ]
    result.append(
        dict(
            fieldname="ot_amount",
            label="Policy OT Preview",
            fieldtype="Currency",
            options="currency",
            width=140,
        )
    )
    result += [
        dict(fieldname=key, label=label, fieldtype="Data", width=280)
        for key, label in (
            ("late_rule", "Late Breakdown"),
            ("early_rule", "Early Breakdown"),
            ("break_rule", "Break Breakdown"),
            ("allowance_rule", "Allowance Rule"),
            ("smart_help", "Smart Help / Next Steps"),
        )
    ]
    return result
