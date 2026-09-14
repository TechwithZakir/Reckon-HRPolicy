"""Cooperative Frappe v16 mixin; policy rows enter before native tax/totals."""

import hashlib
import json

import frappe
from frappe.utils import flt, getdate

from reckon_hr_policy.attendance.summary import collect
from reckon_hr_policy.policy import consequences
from reckon_hr_policy.setup.install import POLICY_COMPONENTS
from reckon_hr_policy.utils.settings import rules, settings


def reject_reserved_components(doc, method=None):
    if doc.salary_component in POLICY_COMPONENTS:
        frappe.throw(
            "RHP policy components are calculated from attendance; use another component for Additional Salary"
        )


def reject_structure_policy_rows(doc, method=None):
    if any(
        row.salary_component in POLICY_COMPONENTS
        for table in ("earnings", "deductions")
        for row in doc.get(table)
    ):
        frappe.throw(
            "RHP policy components are inserted by the payroll engine and must not be added to Salary Structures"
        )


class PolicySalarySlipMixin:
    def calculate_net_pay(self, skip_tax_breakup_computation=False):
        # Submitted documents are immutable: do not let whitelisted preview paths recalculate history.
        if self.name and frappe.db.get_value("Salary Slip", self.name, "docstatus") in (1, 2):
            return
        for table in ("earnings", "deductions"):
            self.set(table, [row for row in self.get(table) if row.salary_component not in POLICY_COMPONENTS])
        self.rhp_calculation = None
        self.rhp_calculation_hash = None
        self._rhp_result = None
        self._rhp_applied = False
        # Native SSA evaluation is cached on the document; reset it between calculations.
        self._evaluated_components = None
        self._ssa_doc = None
        if self.salary_structure and self.salary_slip_based_on_timesheet:
            config = self._get_ssa_doc().get_timesheet_config()
            self._timesheet_component = config.timesheet_component
            self.add_timesheet_earning_component(config)
        result = super().calculate_net_pay(skip_tax_breakup_computation=skip_tax_breakup_computation)
        if self._rhp_result:
            self._rhp_result["native_totals"] = dict(
                gross_pay=self.gross_pay, total_deduction=self.total_deduction, net_pay=self.net_pay
            )
            self.rhp_calculation = json.dumps(self._rhp_result, sort_keys=True, default=str, indent=2)
            self.rhp_calculation_hash = hashlib.sha256(self.rhp_calculation.encode()).hexdigest()
        return result

    def calculate_component_amounts(self, component_type):
        result = super().calculate_component_amounts(component_type)
        if component_type == "earnings" and not getattr(self, "_rhp_applied", False):
            self._rhp_applied = True
            self.apply_reckon_policy()
        return result

    def apply_reckon_policy(self):
        s = settings()
        if not s.enabled or getdate(self.end_date) < getdate(s.policy_effective_from):
            return
        if getdate(self.start_date) < getdate(s.policy_effective_from):
            frappe.throw(
                "Salary period crosses the RHP effective date. Start policy on a payroll-period boundary."
            )
        employee = frappe.get_cached_doc("Employee", self.employee)
        assignment = self._get_ssa_doc()
        reject_structure_policy_rows(frappe.get_cached_doc("Salary Structure", self.salary_structure))
        # Effective-dated assignment values beat today's employee defaults.
        employee = frappe._dict(employee.as_dict())
        for field in ("rhp_payroll_type", "rhp_attendance_policy"):
            if assignment.get(field):
                employee[field] = assignment.get(field)
        if bool(self.salary_slip_based_on_timesheet) != (
            (employee.rhp_payroll_type or s.default_payroll_type) == "Hourly"
        ):
            frappe.throw("RHP Payroll Type does not match the native Salary Structure's Timesheet setting")
        # Do not silently apply the wrong assignment across a mid-period change.
        if frappe.db.exists(
            "Salary Structure Assignment",
            {
                "employee": self.employee,
                "docstatus": 1,
                "from_date": ["between", [frappe.utils.add_days(self.actual_start_date, 1), self.end_date]],
            },
        ):
            frappe.throw(
                "A Salary Structure Assignment changes within this payroll period. Split payroll at the effective date."
            )
        summary = collect([employee], self.actual_start_date, self.actual_end_date, s)[self.employee]
        summary.update(
            consequences(
                summary["late_entries"],
                summary["early_exits"],
                summary["break_violations"],
                rules(s),
                summary["payroll_type"],
                summary["attendance_policy"],
            )
        )
        working, payment = flt(self.total_working_days), flt(self.payment_days)
        numerator = flt(assignment.base)
        denominator = working
        if s.day_rate_basis == "Assignment Base / Payment Days":
            denominator = payment
        elif s.day_rate_basis == "Assignment Base / Calendar Days":
            denominator = (getdate(self.end_date) - getdate(self.start_date)).days + 1
        elif s.day_rate_basis == "Gross / Payment Days":
            numerator = sum(flt(row.amount) for row in self.earnings if not row.do_not_include_in_total)
            denominator = payment
        rate = numerator / denominator if denominator > 0 else 0
        precision = self.precision("gross_pay")
        if precision is None:
            precision = 2
        summary.update(
            working_days=working,
            payment_days=payment,
            daily_salary_rate=rate,
            day_rate_numerator=numerator,
            day_rate_denominator=denominator,
            day_rate_basis=s.day_rate_basis,
            salary_structure_assignment=assignment.name,
            company=self.company,
            currency=self.currency,
            start_date=self.start_date,
            end_date=self.end_date,
            policy_settings={
                k: v for k, v in s.as_dict().items() if k not in ("setup_status", "company_accounts")
            },
            native_payroll_settings={
                key: frappe.get_cached_doc("Payroll Settings").get(key)
                for key in (
                    "payroll_based_on",
                    "include_holidays_in_total_working_days",
                    "consider_marked_attendance_on_holidays",
                    "daily_wages_fraction_for_half_day",
                    "consider_unmarked_attendance_as",
                )
            },
            native_payroll_inputs=dict(
                joining_date=self.joining_date,
                relieving_date=self.relieving_date,
                actual_start_date=self.actual_start_date,
                actual_end_date=self.actual_end_date,
                leave_without_pay=self.leave_without_pay,
                absent_days=self.get("absent_days"),
                hour_rate=self.hour_rate,
                total_working_hours=self.total_working_hours,
                exchange_rate=self.exchange_rate,
            ),
            app_version=frappe.get_attr("reckon_hr_policy.__version__"),
        )
        for prefix in ("late", "early", "break"):
            summary[f"{prefix}_deduction_amount"] = flt(rate * summary[f"{prefix}_deduction_days"], precision)
        summary["total_attendance_deduction"] = sum(
            summary[f"{prefix}_deduction_amount"] for prefix in ("late", "early", "break")
        )
        summary["daily_allowance_amount"] = (
            flt(payment * s.daily_allowance_amount, precision)
            if s.daily_allowance_enabled and summary["payroll_type"] == "Monthly"
            else 0
        )
        amounts = {
            "RHP Daily Allowance": summary["daily_allowance_amount"],
            "RHP Policy Overtime": flt(summary["ot_amount"], precision),
            "RHP Late Deduction": summary["late_deduction_amount"],
            "RHP Early Exit Deduction": summary["early_deduction_amount"],
            "RHP Break Deduction": summary["break_deduction_amount"],
        }
        from hrms.payroll.doctype.salary_slip.salary_slip import get_salary_component_data

        for component, amount in amounts.items():
            if not amount:
                continue
            if not frappe.get_cached_value("Salary Component", component, "rhp_managed"):
                frappe.throw(f"Missing or unowned policy component: {component}; run RHP setup")
            data = get_salary_component_data(component)
            data.depends_on_payment_days = 0  # Already evaluated against native payment days.
            data.deduct_full_tax_on_selected_payroll_date = 0
            self.update_component_row(
                data,
                amount,
                "deductions" if component.endswith("Deduction") else "earnings",
                default_amount=amount,
            )
        self._rhp_result = summary
