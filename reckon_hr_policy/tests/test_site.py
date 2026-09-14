"""Run with bench run-tests on a disposable, installed Frappe HR v16 site."""

import json
from datetime import timedelta

import frappe
from frappe.utils import getdate, now_datetime
from hrms.tests.utils import HRMSTestSuite

from reckon_hr_policy.setup.compatibility import check
from reckon_hr_policy.setup.install import setup


class TestSite(HRMSTestSuite):
    def test_compatibility(self):
        self.assertTrue(all(v.startswith("16.") for v in check().values()))

    def test_install_idempotence(self):
        setup()
        before = {
            dt: frappe.db.count(dt, {"rhp_managed": 1})
            for dt in (
                "Salary Component",
                "Salary Structure",
                "Shift Type",
                "Holiday List",
                "Holiday List Assignment",
                "Shift Assignment",
            )
        }
        setup()
        after = {dt: frappe.db.count(dt, {"rhp_managed": 1}) for dt in before}
        self.assertEqual(before, after)

    def test_settings_permissions(self):
        doc = frappe.get_doc("Reckon HR Policy Settings")
        self.assertTrue(doc.has_permission("write", user="Administrator"))
        self.assertFalse(doc.has_permission("write", user="Guest"))

    def test_managed_saturday_configuration(self):
        self.assertEqual(str(frappe.get_doc("Shift Type", "RHP Saturday").start_time), "10:00:00")

    def test_payroll_and_checkout(self):
        from erpnext.setup.doctype.employee.test_employee import make_employee

        from reckon_hr_policy.attendance.checkout import close_one
        from reckon_hr_policy.setup.employees import provision
        from reckon_hr_policy.utils.settings import settings

        employee = frappe.get_doc(
            "Employee", make_employee("rhp-payroll@example.com", company="_Test Company")
        )
        s = settings()
        start = getdate().replace(day=1)
        s.policy_effective_from = start
        s.save()
        employee.rhp_payroll_type = "Monthly"
        employee.rhp_attendance_policy = "Standard"
        employee.rhp_monthly_salary = 600
        employee.rhp_salary_effective_from = max(start, getdate(employee.date_of_joining))
        employee.save()
        provision(employee, s)
        slip = frappe.get_doc(
            dict(
                doctype="Salary Slip",
                employee=employee.name,
                company=employee.company,
                start_date=start,
                payroll_frequency="Monthly",
                posting_date=getdate(),
            )
        )
        slip.insert()
        first = [(r.salary_component, r.amount) for r in slip.earnings + slip.deductions]
        slip.save()
        self.assertEqual(first, [(r.salary_component, r.amount) for r in slip.earnings + slip.deductions])
        slip.submit()
        frozen = frappe.get_doc("Reckon HR Attendance Summary", {"salary_slip": slip.name})
        self.assertEqual(json.loads(frozen.calculation)["native_totals"]["net_pay"], slip.net_pay)
        with self.assertRaises(frappe.ValidationError):
            frozen.save()
        now = now_datetime()
        source = frappe.get_doc(
            dict(
                doctype="Employee Checkin",
                employee=employee.name,
                log_type="IN",
                time=now - timedelta(hours=25),
                skip_auto_attendance=1,
            )
        ).insert()
        created = close_one(source.name, s, now)
        self.assertTrue(created)
        self.assertIsNone(close_one(source.name, s, now))
        self.assertEqual(frappe.db.count("Employee Checkin", {"rhp_auto_checkout_for": source.name}), 1)
