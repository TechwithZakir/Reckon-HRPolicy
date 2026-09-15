"""Explicit central Grade-to-policy mapping; no inference from grade names."""

import hashlib

import frappe
from frappe.utils import getdate


def seed_profiles(s):
    """Two blank compensation templates per new company; actual amounts remain administrator inputs."""
    existing = {row.company for row in s.grade_policies}
    for company in frappe.get_all("Company", fields=["name", "default_currency"]):
        if company.name in existing:
            continue
        for label, payroll_type, policy in (
            ("Desk", "Monthly", "Standard"),
            ("Production Hourly", "Hourly", "No Attendance Deduction"),
        ):
            digest = hashlib.sha256(company.name.encode()).hexdigest()[:6]
            name = f"RHP {label} - {company.name[:70]} {digest}"
            s.append(
                "grade_policies",
                dict(
                    grade_name=name,
                    company=company.name,
                    currency=company.default_currency,
                    payroll_type=payroll_type,
                    attendance_policy=policy,
                    effective_from=s.policy_effective_from,
                    monthly_salary=0,
                    hourly_rate=0,
                ),
            )


def mapping(employee, s):
    if not s.auto_setup_from_grade or not employee.get("grade"):
        return None
    return next(
        (
            row
            for row in s.grade_policies
            if row.company == employee.company and row.grade_name == employee.grade
        ),
        None,
    )


def configure_grades(s):
    from reckon_hr_policy.setup.install import ensure_structure, owned

    for row in s.grade_policies:
        structure = ensure_structure(row.company, row.currency, row.payroll_type)
        if not frappe.db.exists("Employee Grade", row.grade_name):
            owned(
                "Employee Grade",
                row.grade_name,
                dict(
                    default_salary_structure=structure.name,
                    default_base_pay=row.monthly_salary if row.payroll_type == "Monthly" else 0,
                ),
            )
        # Explicitly mapped native grades are usable but are never overwritten/adopted.
        elif frappe.db.get_value("Employee Grade", row.grade_name, "rhp_managed"):
            owned(
                "Employee Grade",
                row.grade_name,
                dict(
                    default_salary_structure=structure.name,
                    default_base_pay=row.monthly_salary if row.payroll_type == "Monthly" else 0,
                ),
                update=True,
            )
        row.employee_grade = row.grade_name
        row.salary_structure = structure.name
        if row.name:
            frappe.db.set_value(
                "Reckon HR Grade Policy",
                row.name,
                {"employee_grade": row.grade_name, "salary_structure": structure.name},
                update_modified=False,
            )


def hydrate(employee, s):
    """Resolve grade settings for server-side provisioning, without changing Employee payroll history."""
    profile = mapping(employee, s)
    if not profile:
        return employee, None
    values = frappe._dict(employee.as_dict())
    values.update(
        rhp_payroll_type=profile.payroll_type,
        rhp_attendance_policy=profile.attendance_policy,
        rhp_monthly_salary=profile.monthly_salary,
        rhp_hourly_rate=profile.hourly_rate,
        salary_currency=profile.currency,
        rhp_salary_effective_from=max(
            getdate(s.policy_effective_from),
            getdate(profile.effective_from),
            getdate(employee.date_of_joining),
        ),
    )
    return values, profile
