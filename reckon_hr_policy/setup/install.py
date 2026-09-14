"""Idempotent bootstrap. Never adopt a pre-existing, unowned record."""

import hashlib
import json
from datetime import date, timedelta

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import getdate

from reckon_hr_policy.setup.compatibility import check

COMPONENTS = {
    "RHP Daily Allowance": ("Earning", "RHPDA"),
    "RHP Policy Overtime": ("Earning", "RHPOT"),
    "RHP Late Deduction": ("Deduction", "RHPLD"),
    "RHP Early Exit Deduction": ("Deduction", "RHPED"),
    "RHP Break Deduction": ("Deduction", "RHPBD"),
    "RHP Basic Salary": ("Earning", "RHPBS"),
    "RHP Hourly Wages": ("Earning", "RHPHW"),
}
POLICY_COMPONENTS = tuple(COMPONENTS)[:5]
MANAGED_DOCTYPES = (
    "Salary Component",
    "Salary Structure",
    "Salary Structure Assignment",
    "Shift Type",
    "Shift Assignment",
    "Holiday List",
    "Holiday List Assignment",
)


def cf(name, kind, **kwargs):
    return dict(
        fieldname=name,
        fieldtype=kind,
        label="RHP " + name.removeprefix("rhp_").replace("_", " ").title(),
        module="Reckon HR Policy",
        **kwargs,
    )


def custom_fields():
    fields = {dt: [cf("rhp_managed", "Check", read_only=1, hidden=1, no_copy=1)] for dt in MANAGED_DOCTYPES}
    fields["Employee"] = [
        cf("rhp_section", "Section Break", label_override="Reckon HR Policy"),
        cf(
            "rhp_payroll_type",
            "Select",
            options="\nMonthly\nHourly",
            permlevel=1,
            description="Blank uses central default; no grade-based behavior.",
        ),
        cf("rhp_attendance_policy", "Select", options="\nStandard\nNo Attendance Deduction", permlevel=1),
        cf("rhp_hourly_rate", "Currency", options="salary_currency", permlevel=1),
        cf(
            "rhp_monthly_salary",
            "Currency",
            options="salary_currency",
            permlevel=1,
            description="For automatic managed Salary Structure Assignment; never inferred from CTC.",
        ),
        cf(
            "rhp_salary_effective_from",
            "Date",
            permlevel=1,
            description="Required to create a dated salary assignment from salary/rate inputs.",
        ),
    ]
    fields["Employee"][0].pop("label_override")
    fields["Salary Structure Assignment"] += [
        cf("rhp_hourly_rate", "Currency", options="currency", read_only=1),
        cf("rhp_payroll_type", "Select", options="\nMonthly\nHourly", read_only=1),
        cf("rhp_attendance_policy", "Select", options="\nStandard\nNo Attendance Deduction", read_only=1),
    ]
    fields["Employee Checkin"] = [
        cf("rhp_auto_checkout_for", "Link", options="Employee Checkin", read_only=1, unique=1, no_copy=1),
        cf("rhp_auto_checkout_reason", "Small Text", read_only=1, no_copy=1),
    ]
    fields["Salary Slip"] = [
        cf("rhp_calculation", "Code", options="JSON", read_only=1, no_copy=1),
        cf("rhp_calculation_hash", "Data", read_only=1, no_copy=1),
    ]
    # Match module as well as schema before updating our fields.
    for dt, definitions in fields.items():
        for definition in definitions:
            existing = frappe.db.get_value(
                "Custom Field",
                {"dt": dt, "fieldname": definition["fieldname"]},
                ["name", "module"],
                as_dict=True,
            )
            if existing and existing.module != "Reckon HR Policy":
                frappe.throw(
                    f"Custom Field collision: {dt}.{definition['fieldname']}. Resolve ownership before installing."
                )
    create_custom_fields(fields, update=True)
    # Protect salary policy fields even on sites with a customized Employee permission table.
    from frappe.permissions import add_permission, update_permission_property

    for role in ("HR Manager", "System Manager"):
        add_permission("Employee", role, permlevel=1)
        update_permission_property("Employee", role, 1, "read", 1)
        update_permission_property("Employee", role, 1, "write", 1)


def owned(dt, name, values, *, update=False, submit=False):
    if frappe.db.exists(dt, name):
        doc = frappe.get_doc(dt, name)
        if not doc.get("rhp_managed"):
            frappe.throw(f"{dt} '{name}' already exists and is not owned by Reckon HR Policy")
        if update and any(doc.get(k) != v for k, v in values.items()):
            doc.update(values)
            doc.save(ignore_permissions=True)
        return doc
    doc = frappe.get_doc(dict(doctype=dt, **values, rhp_managed=1))
    doc.name = name
    doc.flags.ignore_permissions = True
    doc.insert(set_name=name)
    if submit:
        doc.submit()
    return doc


def structure_name(company, currency, payroll_type):
    digest = hashlib.sha256(f"{company}|{currency}".encode()).hexdigest()[:12]
    return f"RHP {payroll_type} {digest}"


def ensure_structure(company, currency, payroll_type):
    values = dict(
        company=company,
        currency=currency,
        is_active="Yes",
        payroll_frequency="Monthly",
        salary_slip_based_on_timesheet=int(payroll_type == "Hourly"),
    )
    if payroll_type == "Hourly":
        values.update(salary_component="RHP Hourly Wages", hour_rate=0)
    else:
        values["earnings"] = [
            dict(
                salary_component="RHP Basic Salary",
                abbr="RHPBS",
                amount_based_on_formula=1,
                formula="base",
                depends_on_payment_days=1,
            )
        ]
    return owned("Salary Structure", structure_name(company, currency, payroll_type), values, submit=True)


def configure(s):
    for name, (kind, abbr) in COMPONENTS.items():
        values = dict(
            salary_component=name,
            salary_component_abbr=abbr,
            type=kind,
            description="Managed by Reckon HR Policy",
            depends_on_payment_days=int(name == "RHP Basic Salary"),
            is_tax_applicable=int(
                kind == "Earning" and (name not in POLICY_COMPONENTS or s.policy_earnings_taxable)
            ),
            remove_if_zero_valued=1,
        )
        component = owned("Salary Component", name, values, update=True)
        mappings = {row.company: row for row in s.company_accounts}
        for company in frappe.get_all(
            "Company", fields=["name", "default_expense_account", "default_currency"]
        ):
            override = mappings.get(company.name)
            account = (
                override.get("deduction_account" if kind == "Deduction" else "expense_account")
                if override
                else None
            ) or company.default_expense_account
            if account:
                row = next((r for r in component.accounts if r.company == company.name), None)
                if row:
                    if row.account == account:
                        continue
                    row.account = account
                else:
                    component.append("accounts", dict(company=company.name, account=account))
                component.save(ignore_permissions=True)
    for label, prefix in (("RHP Regular", "regular"), ("RHP Saturday", "saturday")):
        owned(
            "Shift Type",
            label,
            dict(
                start_time=s.get(prefix + "_shift_start"),
                end_time=s.get(prefix + "_shift_end"),
                enable_auto_attendance=1,
                determine_check_in_and_check_out="Strictly based on Log Type in Employee Checkin",
                working_hours_calculation_based_on="Every Valid Check-in and Check-out",
                enable_late_entry_marking=1,
                late_entry_grace_period=s.late_grace_minutes,
                enable_early_exit_marking=1,
                early_exit_grace_period=s.early_exit_grace_minutes,
                begin_check_in_before_shift_start_time=s.checkin_buffer_minutes,
                allow_check_out_after_shift_end_time=s.checkout_buffer_minutes,
                working_hours_threshold_for_half_day=s.half_day_hours,
                working_hours_threshold_for_absent=s.absent_hours,
                process_attendance_after=s.policy_effective_from,
                auto_update_last_sync=s.auto_update_last_sync,
            ),
            update=True,
        )
    ensure_holidays(s)
    for company in frappe.get_all("Company", fields=["name", "default_currency"]):
        for category in ("Monthly", "Hourly"):
            ensure_structure(company.name, company.default_currency, category)
    refresh_status(s)


def ensure_holidays(s):
    from hrms.utils.holiday_list import get_assigned_holiday_list

    for year in (getdate().year, getdate().year + 1):
        start, end = date(year, 1, 1), date(year, 12, 31)
        holidays = []
        day = start
        while day <= end:
            if s.sunday_weekly_holiday and day.weekday() == 6:
                holidays.append(dict(holiday_date=day, weekly_off=1, description="Sunday"))
            day += timedelta(days=1)
        name = f"RHP Weekly Holidays {year}"
        # Keep historical holiday dates, but apply new weekly-off policy prospectively.
        if frappe.db.exists("Holiday List", name):
            calendar = frappe.get_doc("Holiday List", name)
            if not calendar.get("rhp_managed"):
                frappe.throw(f"Unowned Holiday List collision: {name}")
            boundary = max(getdate(), getdate(s.policy_effective_from))
            preserved = [
                row.as_dict()
                for row in calendar.holidays
                if getdate(row.holiday_date) < boundary or not row.weekly_off
            ]
            existing_dates = {getdate(row["holiday_date"]) for row in preserved}
            revised = preserved + [
                row
                for row in holidays
                if row["holiday_date"] >= boundary and row["holiday_date"] not in existing_dates
            ]
            if {getdate(row.holiday_date) for row in calendar.holidays} != {
                getdate(row["holiday_date"]) for row in revised
            }:
                calendar.set("holidays", revised)
                calendar.save(ignore_permissions=True)
        else:
            owned(
                "Holiday List",
                name,
                dict(holiday_list_name=name, from_date=start, to_date=end, holidays=holidays),
            )
        for company in frappe.get_all("Company", pluck="name"):
            current = get_assigned_holiday_list(company, start)
            if current and (
                not frappe.db.get_value("Holiday List", current, "rhp_managed")
                or getdate(frappe.db.get_value("Holiday List", current, "to_date")) >= start
            ):
                continue
            assignment = frappe.get_doc(
                dict(
                    doctype="Holiday List Assignment",
                    applicable_for="Company",
                    assigned_to=company,
                    holiday_list=name,
                    from_date=start,
                    rhp_managed=1,
                )
            )
            assignment.flags.ignore_permissions = True
            assignment.insert()
            assignment.submit()


def refresh_status(s):
    warnings = []
    for company in frappe.get_all(
        "Company", fields=["name", "default_expense_account", "default_payroll_payable_account"]
    ):
        override = next((r for r in s.company_accounts if r.company == company.name), None)
        for setting, standard in (
            ("expense_account", "default_expense_account"),
            ("payroll_payable_account", "default_payroll_payable_account"),
        ):
            if not ((override and override.get(setting)) or company.get(standard)):
                warnings.append(
                    f"{company.name}: configure {setting} in Settings or the native Company defaults"
                )
    if not s.auto_update_last_sync:
        warnings.append(
            "Device integration must maintain Shift Type.last_sync_of_checkin; auto attendance will wait for this watermark"
        )
    warnings.append(
        "Existing employee holiday/shift/salary assignments are preserved. Review existing schedules and tax structures before live payroll."
    )
    result = dict(versions=check(), warnings=warnings, production_certified=False)
    frappe.db.set_single_value("Reckon HR Policy Settings", "setup_status", json.dumps(result, indent=2))
    return result


def setup():
    check()
    frappe.flags.rhp_setup = True
    try:
        custom_fields()
        s = frappe.get_doc("Reckon HR Policy Settings")
        if not s.policy_effective_from:
            s.policy_effective_from = getdate()
        s.save(ignore_permissions=True)
        configure(s)
        frappe.db.add_index("Employee Checkin", ["employee", "time"], "rhp_employee_time")
        frappe.db.add_index("Employee Checkin", ["log_type", "time"], "rhp_log_type_time")
        frappe.db.add_index(
            "Attendance", ["employee", "attendance_date", "docstatus"], "rhp_employee_date_status"
        )
        from reckon_hr_policy.setup.employees import maintain

        maintain()
        return refresh_status(s)
    finally:
        frappe.flags.rhp_setup = False


def before_uninstall():
    if frappe.db.count("Reckon HR Attendance Summary"):
        frappe.throw(
            "Reckon HR Policy has immutable payroll snapshots. Archive the site and retain this app for audit; disable it in Settings instead."
        )
