import math

import frappe
from frappe.model.document import Document
from frappe.utils import get_time, getdate


class ReckonHRPolicySettings(Document):
    def validate(self):
        positive = (
            "late_occurrences_per_deduction_day",
            "early_exit_occurrences_per_deduction_day",
            "break_violations_per_deduction_day",
            "overtime_block_minutes",
            "maximum_open_checkin_hours",
            "checkout_batch_size",
            "assignment_horizon_days",
        )
        nonnegative = (
            "late_grace_minutes",
            "early_exit_grace_minutes",
            "maximum_break_minutes",
            "deduction_days_per_threshold",
            "minimum_early_entry_minutes",
            "overtime_amount_per_block",
            "daily_allowance_amount",
            "checkin_buffer_minutes",
            "checkout_buffer_minutes",
            "half_day_hours",
            "absent_hours",
        )
        for name in positive + nonnegative:
            value = float(self.get(name) or 0)
            if not math.isfinite(value) or value < 0 or (name in positive and value == 0):
                frappe.throw(
                    f"{self.meta.get_label(name)} must be {'positive' if name in positive else 'nonnegative'} and finite"
                )
        if self.assignment_horizon_days > 366 or self.checkout_batch_size > 5000:
            frappe.throw("Assignment horizon is limited to 366 days; checkout batch size to 5000")
        if self.absent_hours > self.half_day_hours:
            frappe.throw("Absent hours cannot exceed half-day hours")
        for prefix in ("regular", "saturday"):
            if get_time(self.get(prefix + "_shift_start")) >= get_time(self.get(prefix + "_shift_end")):
                frappe.throw(
                    "Managed shifts must start and end on the same date. Native external night shifts remain supported."
                )
        if not self.policy_effective_from:
            frappe.throw("Policy Effective From is required")
        getdate(self.policy_effective_from)
        companies = set()
        for row in self.company_accounts:
            if row.company in companies:
                frappe.throw("Only one account configuration per company is allowed")
            companies.add(row.company)
            for name in ("expense_account", "deduction_account", "payroll_payable_account"):
                if row.get(name):
                    account = frappe.get_doc("Account", row.get(name))
                    if account.company != row.company or account.is_group or account.disabled:
                        frappe.throw("Policy accounts must be active ledger accounts in the selected company")
                    expected = "Liability" if name == "payroll_payable_account" else "Expense"
                    if account.root_type != expected:
                        frappe.throw(f"{name} must have root type {expected}")

    def on_update(self):
        if frappe.flags.in_install or frappe.flags.in_migrate or frappe.flags.rhp_setup:
            return
        from reckon_hr_policy.setup.install import configure

        configure(self)

    @frappe.whitelist(methods=["POST"])
    def refresh_setup(self):
        self.check_permission("write")
        from reckon_hr_policy.setup.install import setup

        return setup()
