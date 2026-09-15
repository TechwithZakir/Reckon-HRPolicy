import frappe

from reckon_hr_policy.utils.settings import policy_types


def defaults(doc, method=None):
    if not doc.is_new() or not frappe.get_meta("Salary Structure Assignment").has_field("rhp_hourly_rate"):
        return
    employee = frappe.get_cached_doc("Employee", doc.employee)
    from reckon_hr_policy.setup.grades import hydrate
    from reckon_hr_policy.utils.settings import settings

    employee, profile = hydrate(employee, settings())
    payroll_type, policy = policy_types(employee)
    doc.rhp_payroll_type = payroll_type
    doc.rhp_attendance_policy = policy
    doc.rhp_hourly_rate = employee.get("rhp_hourly_rate") or 0
    if profile:
        doc.rhp_grade = employee.grade


class PolicyAssignmentMixin:
    def _get_component_eval_context(self):
        from reckon_hr_policy.payroll.formulas import empty_context

        context = super()._get_component_eval_context()
        context.update(empty_context())
        return context

    def get_timesheet_config(self):
        config = super().get_timesheet_config()
        if self.get("rhp_managed") and config.based_on_timesheet:
            config.hour_rate = self.get("rhp_hourly_rate") or 0
            if config.hour_rate <= 0:
                frappe.throw("Enter a positive hourly rate in a dated Salary Structure Assignment")
        return config
