"""Native setup adapters; reuse the site's accounting defaults and preserve existing periods."""

import hashlib
from datetime import date, timedelta

import frappe
from frappe.utils import getdate


def seed_accounts(s):
    configured = {row.company for row in s.company_accounts}
    for company in frappe.get_all(
        "Company",
        fields=["name", "default_expense_account", "default_payroll_payable_account", "default_currency"],
    ):
        if company.name in configured:
            continue
        payable = company.default_payroll_payable_account or frappe.db.get_value(
            "Account",
            {
                "company": company.name,
                "account_name": frappe._("Payroll Payable"),
                "account_currency": company.default_currency,
                "is_group": 0,
                "disabled": 0,
            },
            "name",
        )
        s.append(
            "company_accounts",
            dict(
                company=company.name,
                expense_account=company.default_expense_account,
                deduction_account=company.default_expense_account,
                payroll_payable_account=payable,
            ),
        )


def configure_native(s):
    if s.enabled and s.manage_native_payroll_settings:
        native = frappe.get_doc("Payroll Settings")
        native.payroll_based_on = s.native_payroll_basis
        native.consider_unmarked_attendance_as = s.native_unmarked_as
        native.include_holidays_in_total_working_days = s.native_include_holidays
        native.save(ignore_permissions=True)
    ensure_payroll_periods(s)


def ensure_payroll_periods(s):
    from reckon_hr_policy.setup.install import owned

    if not s.auto_create_payroll_periods:
        return
    today = getdate()
    year = today.year - int(today.month < s.payroll_year_start_month)
    for company in frappe.get_all("Company", pluck="name"):
        for offset in (0, 1):
            start = date(year + offset, s.payroll_year_start_month, 1)
            end = date(year + offset + 1, s.payroll_year_start_month, 1) - timedelta(days=1)
            if frappe.db.exists(
                "Payroll Period", {"company": company, "start_date": ["<=", end], "end_date": [">=", start]}
            ):
                continue
            suffix = hashlib.sha256(company.encode()).hexdigest()[:10]
            owned(
                "Payroll Period",
                f"RHP Payroll {start.year}-{start.month:02} {suffix}",
                dict(company=company, start_date=start, end_date=end),
            )


def company_created(doc, method=None):
    if (
        frappe.flags.in_install
        or frappe.flags.in_migrate
        or not frappe.db.exists("DocType", "Reckon HR Policy Settings")
    ):
        return
    frappe.enqueue("reckon_hr_policy.setup.install.setup", enqueue_after_commit=True, queue="long")
