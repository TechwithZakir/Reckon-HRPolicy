import frappe
from frappe.model.document import Document


class ReckonHRAttendanceSummary(Document):
    def validate(self):
        if not self.is_new() or not self.flags.rhp_freeze:
            frappe.throw("Policy snapshots are immutable and may only be created by Salary Slip submission")

    def on_trash(self):
        frappe.throw("Retain policy snapshots for payroll audit, including cancelled Salary Slips")
