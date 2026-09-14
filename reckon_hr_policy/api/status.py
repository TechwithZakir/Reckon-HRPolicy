import frappe

from reckon_hr_policy.utils.settings import require_manager, settings


@frappe.whitelist()
def get_setup_status():
    require_manager()
    return frappe.parse_json(settings().setup_status or "{}")
