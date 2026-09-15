"""Create native assignments from explicit salary inputs; preserve unrelated assignments."""

import math
from datetime import timedelta

import frappe
from frappe.utils import getdate

from reckon_hr_policy.utils.settings import policy_types, settings

POLICY_FIELDS = (
    "grade",
    "rhp_payroll_type",
    "rhp_attendance_policy",
    "rhp_hourly_rate",
    "rhp_monthly_salary",
    "rhp_salary_effective_from",
)


def validate_employee(doc, method=None):
    if frappe.flags.in_install or not frappe.get_meta("Employee").has_field("rhp_payroll_type"):
        return
    before = doc.get_doc_before_save()
    changed = any(doc.has_value_changed(f) if before else bool(doc.get(f)) for f in POLICY_FIELDS)
    if (
        changed
        and frappe.session.user != "Administrator"
        and not set(frappe.get_roles()) & {"HR Manager", "System Manager"}
    ):
        frappe.throw(
            "Only HR Manager or System Manager may change employee payroll policy", frappe.PermissionError
        )
    for field in ("rhp_hourly_rate", "rhp_monthly_salary"):
        amount = float(doc.get(field) or 0)
        if amount < 0 or not math.isfinite(amount):
            frappe.throw("Salary and hourly rate must be finite, nonnegative amounts")
    if doc.get("rhp_salary_effective_from") and getdate(doc.rhp_salary_effective_from) < getdate(
        doc.date_of_joining
    ):
        frappe.throw("Salary effective date cannot precede joining date")


def on_employee_update(doc, method=None):
    if frappe.flags.in_install or frappe.flags.rhp_setup:
        return
    s = settings()
    if s.enabled and doc.status == "Active":
        provision(doc, s)


def provision(employee, s):
    from reckon_hr_policy.grade_policy import change_date, same_compensation
    from reckon_hr_policy.setup.grades import hydrate
    from reckon_hr_policy.setup.install import ensure_structure

    employee, grade_profile = hydrate(employee, s)
    payroll_type, policy = policy_types(employee, s)
    # Employee row lock serializes scheduler, salary setup and Employee save.
    frappe.db.get_value("Employee", employee.name, "name", for_update=True)
    if s.auto_assign_shifts and not employee.default_shift:
        frappe.db.set_value("Employee", employee.name, "default_shift", "RHP Regular")
        employee.default_shift = "RHP Regular"
    if s.auto_assign_shifts and employee.default_shift == "RHP Regular":
        schedule_saturdays(employee, s)
    effective = employee.get("rhp_salary_effective_from")
    amount = employee.get("rhp_hourly_rate" if payroll_type == "Hourly" else "rhp_monthly_salary") or 0
    if not effective or amount <= 0:
        return
    effective = getdate(effective)
    currency = employee.salary_currency or frappe.get_cached_value(
        "Company", employee.company, "default_currency"
    )
    existing = frappe.get_all(
        "Salary Structure Assignment",
        filters={
            "employee": employee.name,
            "docstatus": 1,
            **({} if grade_profile else {"from_date": ["<=", effective]}),
        },
        fields=[
            "name",
            "from_date",
            "rhp_managed",
            "base",
            "rhp_hourly_rate",
            "rhp_payroll_type",
            "rhp_attendance_policy",
            "rhp_grade",
            "currency",
        ],
        order_by="from_date desc",
        limit_page_length=1,
    )
    if existing:
        previous = existing[0]
        if not previous.rhp_managed:
            return  # Existing native payroll is explicitly preserved.
        if grade_profile:
            if same_compensation(
                previous,
                grade=employee.grade,
                amount=amount,
                payroll_type=payroll_type,
                attendance_policy=policy,
                currency=currency,
            ):
                return
            slips = frappe.get_all(
                "Salary Slip",
                filters={"employee": employee.name, "docstatus": 1},
                fields=["end_date"],
                order_by="end_date desc",
                limit_page_length=1,
            )
            effective = change_date(
                effective, getdate(), s.grade_change_timing, getdate(slips[0].end_date) if slips else None
            )
            if (
                previous.from_date == effective
                and effective > getdate()
                and not frappe.db.exists(
                    "Salary Slip",
                    {"employee": employee.name, "docstatus": ["<", 2], "end_date": [">=", effective]},
                )
            ):
                pending = frappe.get_doc("Salary Structure Assignment", previous.name)
                pending.flags.ignore_permissions = True
                pending.cancel()
                previous = None
        if previous and previous.from_date == effective:
            old_amount = previous.rhp_hourly_rate if payroll_type == "Hourly" else previous.base
            if (
                float(old_amount or 0) != float(amount)
                or previous.rhp_payroll_type != payroll_type
                or previous.rhp_attendance_policy != policy
            ):
                frappe.throw(
                    "A salary assignment exists on this effective date. Enter a new effective date for a salary or policy change."
                )
            return
    if frappe.db.exists(
        "Salary Slip", {"employee": employee.name, "docstatus": 1, "end_date": [">=", effective]}
    ):
        frappe.throw(
            "Salary effective date overlaps submitted payroll. Use a future effective date or the native payroll correction process."
        )
    structure = ensure_structure(employee.company, currency, payroll_type)
    override = next((r for r in s.company_accounts if r.company == employee.company), None)
    assignment = frappe.get_doc(
        dict(
            doctype="Salary Structure Assignment",
            employee=employee.name,
            company=employee.company,
            salary_structure=structure.name,
            from_date=effective,
            base=amount if payroll_type == "Monthly" else 0,
            currency=currency,
            rhp_managed=1,
            rhp_grade=employee.grade if grade_profile else None,
            rhp_hourly_rate=employee.get("rhp_hourly_rate") or 0,
            rhp_payroll_type=payroll_type,
            rhp_attendance_policy=policy,
            payroll_payable_account=override.payroll_payable_account if override else None,
        )
    )
    assignment.flags.ignore_permissions = True
    assignment.insert()
    assignment.submit()


def schedule_saturdays(employee, s):
    start = max(getdate(), getdate(s.policy_effective_from), getdate(employee.date_of_joining))
    end = start + timedelta(days=s.assignment_horizon_days)
    if employee.relieving_date:
        end = min(end, getdate(employee.relieving_date))
    existing = frappe.get_all(
        "Shift Assignment",
        filters={"employee": employee.name, "docstatus": 1, "status": "Active", "start_date": ["<=", end]},
        fields=["start_date", "end_date"],
    )
    day = start + timedelta(days=(5 - start.weekday()) % 7)
    while day <= end:
        if not any(row.start_date <= day and (not row.end_date or row.end_date >= day) for row in existing):
            doc = frappe.get_doc(
                dict(
                    doctype="Shift Assignment",
                    employee=employee.name,
                    company=employee.company,
                    shift_type="RHP Saturday",
                    start_date=day,
                    end_date=day,
                    status="Active",
                    rhp_managed=1,
                )
            )
            doc.flags.ignore_permissions = True
            doc.insert()
            doc.submit()
        day += timedelta(days=7)


def maintain(s=None):
    s = s or settings()
    if not s.enabled:
        return
    from reckon_hr_policy.setup.install import ensure_holidays
    from reckon_hr_policy.setup.native import ensure_payroll_periods

    ensure_holidays(s)
    ensure_payroll_periods(s)
    for employee in frappe.get_all("Employee", filters={"status": "Active"}, pluck="name"):
        # Savepoints isolate invalid existing employee configurations without losing the rest.
        frappe.db.savepoint("rhp_provision")
        try:
            provision(frappe.get_doc("Employee", employee), s)
        except Exception:
            frappe.db.rollback(save_point="rhp_provision")
            frappe.log_error(title=f"RHP setup failed: {employee}", message=frappe.get_traceback())
