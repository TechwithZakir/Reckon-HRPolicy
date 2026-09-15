import frappe

from reckon_hr_policy.policy import Rules


def settings():
    return frappe.get_cached_doc("Reckon HR Policy Settings")


def rules(doc=None):
    doc = doc or settings()
    return Rules(**{key: doc.get(key) for key in Rules.__dataclass_fields__})


def require_manager():
    frappe.only_for(["HR Manager", "System Manager"])


def policy_types(employee, doc=None):
    doc = doc or settings()
    if not employee.get("_rhp_assignment_policy"):
        from reckon_hr_policy.setup.grades import mapping

        profile = mapping(employee, doc)
        if profile:
            return profile.payroll_type, profile.attendance_policy
    return (
        employee.get("rhp_payroll_type") or doc.default_payroll_type,
        employee.get("rhp_attendance_policy") or doc.default_attendance_policy,
    )
