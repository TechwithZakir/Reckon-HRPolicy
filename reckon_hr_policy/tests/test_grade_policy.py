import unittest
from datetime import date

from reckon_hr_policy.grade_policy import change_date, same_compensation


class TestGradePolicy(unittest.TestCase):
    def test_change_starts_next_month(self):
        self.assertEqual(change_date(date(2026, 9, 1), date(2026, 9, 15), "Next Month"), date(2026, 10, 1))

    def test_year_rollover(self):
        self.assertEqual(change_date(date(2026, 1, 1), date(2026, 12, 31), "Next Month"), date(2027, 1, 1))

    def test_today_setting(self):
        self.assertEqual(change_date(date(2026, 9, 1), date(2026, 9, 15), "Today"), date(2026, 9, 15))

    def test_respects_future_profile_date(self):
        self.assertEqual(change_date(date(2027, 1, 1), date(2026, 9, 15), "Next Month"), date(2027, 1, 1))

    def test_does_not_overlap_submitted_payroll(self):
        self.assertEqual(
            change_date(date(2026, 9, 1), date(2026, 9, 15), "Today", date(2026, 9, 30)), date(2026, 10, 1)
        )

    def test_unchanged_compensation_is_idempotent(self):
        previous = dict(
            rhp_grade="Desk",
            base=600,
            rhp_payroll_type="Monthly",
            rhp_attendance_policy="Standard",
            currency="BDT",
        )
        self.assertTrue(
            same_compensation(
                previous,
                grade="Desk",
                amount=600,
                payroll_type="Monthly",
                attendance_policy="Standard",
                currency="BDT",
            )
        )
        self.assertFalse(
            same_compensation(
                previous,
                grade="Desk",
                amount=650,
                payroll_type="Monthly",
                attendance_policy="Standard",
                currency="BDT",
            )
        )
        self.assertFalse(
            same_compensation(
                previous,
                grade="Desk",
                amount=600,
                payroll_type="Monthly",
                attendance_policy="Standard",
                currency="USD",
            )
        )

    def test_hourly_rate_signature(self):
        previous = dict(
            rhp_grade="Production",
            base=0,
            rhp_hourly_rate=5,
            rhp_payroll_type="Hourly",
            rhp_attendance_policy="No Attendance Deduction",
            currency="BDT",
        )
        self.assertTrue(
            same_compensation(
                previous,
                grade="Production",
                amount=5,
                payroll_type="Hourly",
                attendance_policy="No Attendance Deduction",
                currency="BDT",
            )
        )
