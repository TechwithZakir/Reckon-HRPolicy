import unittest
from dataclasses import replace
from datetime import date

from reckon_hr_policy.policy import Rules
from reckon_hr_policy.reporting.effectiveness import explain


class TestEffectiveness(unittest.TestCase):
    def result(self, *, r=None, summary=None, **kwargs):
        data = dict(
            payroll_type="Monthly",
            attendance_policy="Standard",
            late_entries=7,
            early_exits=4,
            break_violations=5,
            ot_amount=8,
            submitted_attendance_dates=20,
            draft_attendance_records=0,
            absent_dates=0,
            excluded_shifts=[],
        )
        data.update(summary or {})
        inputs = dict(
            assignment={"name": "SSA-1"},
            payroll_based_on="Attendance",
            unmarked_as="Present",
            today=date(2026, 10, 1),
            default_shift="RHP Regular",
        )
        inputs.update(kwargs)
        return explain(
            data,
            r or Rules(),
            date(2026, 9, 1),
            date(2026, 9, 30),
            inputs.pop("effective", date(2026, 9, 1)),
            **inputs,
        )

    def test_default_breakdown(self):
        row = self.result()
        self.assertEqual(row["total_deduction_days"], 4)
        self.assertEqual(row["readiness"], "Preview available")

    def test_disabled_keeps_evidence_but_zeroes_amounts(self):
        row = self.result(r=replace(Rules(), enabled=0))
        self.assertEqual(row["late_entries"], 7)
        self.assertEqual(row["total_deduction_days"], 0)
        self.assertEqual(row["ot_amount"], 0)
        self.assertEqual(row["policy_status"], "Disabled")

    def test_before_effective(self):
        row = self.result(effective=date(2026, 10, 1))
        self.assertEqual(row["policy_status"], "Not yet effective")
        self.assertEqual(row["total_deduction_days"], 0)

    def test_crossing_effective_date_blocks(self):
        row = self.result(effective=date(2026, 9, 15))
        self.assertEqual(row["readiness"], "Action required")
        self.assertEqual(row["total_deduction_days"], 0)

    def test_hourly_exemption(self):
        row = self.result(summary={"payroll_type": "Hourly"})
        self.assertEqual(row["total_deduction_days"], 0)
        self.assertEqual(row["ot_amount"], 0)
        self.assertEqual(row["allowance_rule"], "Not applicable")

    def test_exempt_monthly_still_allowance(self):
        row = self.result(summary={"attendance_policy": "No Attendance Deduction"})
        self.assertEqual(row["total_deduction_days"], 0)
        self.assertIn("payment days", row["allowance_rule"])

    def test_missing_assignment_blocks(self):
        self.assertEqual(self.result(assignment=None)["readiness"], "Action required")

    def test_midperiod_assignment_blocks(self):
        self.assertEqual(self.result(assignment_changes=1)["readiness"], "Action required")

    def test_draft_attendance_guidance(self):
        row = self.result(summary={"draft_attendance_records": 2})
        self.assertEqual(row["readiness"], "Review")
        self.assertIn("Draft Attendance is excluded", row["smart_help"])

    def test_absence_native_settings_warning(self):
        row = self.result(summary={"absent_dates": 2}, payroll_based_on="Leave")
        self.assertEqual(row["readiness"], "Review")
        self.assertIn("Payroll Based On is not Attendance", row["smart_help"])

    def test_future_dates_warn(self):
        self.assertEqual(self.result(today=date(2026, 9, 15))["readiness"], "Review")

    def test_invalid_punches_warn(self):
        row = self.result(punch_issues=2)
        self.assertIn("missing IN/OUT", row["smart_help"])
        self.assertEqual(row["readiness"], "Review")
