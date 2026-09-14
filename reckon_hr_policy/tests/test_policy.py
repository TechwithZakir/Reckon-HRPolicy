import unittest
from dataclasses import replace
from datetime import datetime, timedelta

from reckon_hr_policy.policy import (
    Rules,
    consequences,
    deduction_days,
    local_deadline,
    overtime,
    shift_events,
    strict_pairs,
)


class TestPolicy(unittest.TestCase):
    def setUp(self):
        self.rules = Rules()
        self.start = datetime(2026, 9, 14, 8, 30)
        self.end = self.start.replace(hour=17, minute=30)

    def logs(self, minutes=30, early=0):
        noon = self.start.replace(hour=12, minute=0)
        return [
            dict(name=str(i), time=t, log_type=kind)
            for i, (t, kind) in enumerate(
                (
                    (self.start - timedelta(minutes=early), "IN"),
                    (noon, "OUT"),
                    (noon + timedelta(minutes=minutes), "IN"),
                    (self.end, "OUT"),
                )
            )
        ]

    def test_late_thresholds(self):
        for n, expected in ((2, 0), (3, 1), (6, 2), (7, 2), (9, 3)):
            with self.subTest(n=n):
                self.assertEqual(consequences(n, 0, 0, self.rules)["late_deduction_days"], expected)

    def test_early_thresholds(self):
        for n, expected in ((2, 0), (3, 1), (6, 2)):
            self.assertEqual(consequences(0, n, 0, self.rules)["early_deduction_days"], expected)

    def test_break_boundaries(self):
        for n, expected in ((29, 0), (30, 0), (31, 1)):
            with self.subTest(n=n):
                self.assertEqual(
                    shift_events(self.logs(n), self.start, self.end, self.rules)["break_violations"], expected
                )

    def test_break_thresholds(self):
        for n, expected in ((3, 1), (6, 2)):
            self.assertEqual(consequences(0, 0, n, self.rules)["break_deduction_days"], expected)

    def test_break_multiplier(self):
        self.assertEqual(deduction_days(6, 3, 0.5), 1)

    def test_overtime_boundaries(self):
        for n, expected in ((29, 0), (30, 1), (59, 1), (60, 2)):
            with self.subTest(n=n):
                self.assertEqual(overtime(n, self.rules)[1], expected)

    def test_overtime_disabled(self):
        self.assertEqual(overtime(120, replace(self.rules, early_entry_overtime_enabled=0)), (0, 0))

    def test_minimum_does_not_subtract_block(self):
        self.assertEqual(overtime(60, replace(self.rules, minimum_early_entry_minutes=60)), (2, 2))

    def test_hourly_exempt(self):
        self.assertEqual(sum(consequences(6, 6, 6, self.rules, "Hourly").values()), 0)

    def test_explicit_exemption(self):
        self.assertEqual(
            sum(consequences(6, 6, 6, self.rules, "Monthly", "No Attendance Deduction").values()), 0
        )

    def test_disabled(self):
        self.assertEqual(sum(consequences(6, 6, 6, replace(self.rules, enabled=0)).values()), 0)

    def test_holiday(self):
        result = shift_events(self.logs(31, 60), self.start, self.end, self.rules, holiday=True)
        self.assertEqual(result["break_violations"], 0)
        self.assertEqual(result["ot_amount"], 0)

    def test_saturday_ten_am(self):
        start = datetime(2026, 9, 19, 10)
        logs = [
            dict(time=start - timedelta(minutes=30), log_type="IN"),
            dict(time=start + timedelta(hours=7), log_type="OUT"),
        ]
        self.assertEqual(shift_events(logs, start, start + timedelta(hours=7), self.rules)["ot_amount"], 1)

    def test_final_checkout_not_break(self):
        logs = [self.logs()[0], self.logs()[-1]]
        self.assertEqual(shift_events(logs, self.start, self.end, self.rules)["break_violations"], 0)

    def test_duplicate_in_invalidates_shift(self):
        logs = self.logs()
        logs[1]["log_type"] = "IN"
        self.assertEqual(strict_pairs(logs), [])

    def test_equal_timestamps_invalid(self):
        logs = self.logs()
        logs[1]["time"] = logs[0]["time"]
        self.assertEqual(strict_pairs(logs), [])

    def test_incomplete_sequence(self):
        self.assertEqual(strict_pairs(self.logs()[:-1]), [])

    def test_outside_shift_break_ignored(self):
        logs = self.logs(31)
        logs[1]["time"] = self.start - timedelta(minutes=40)
        logs[0]["time"] = self.start - timedelta(minutes=60)
        logs[2]["time"] = self.start - timedelta(minutes=5)
        self.assertEqual(shift_events(logs, self.start, self.end, self.rules)["break_violations"], 0)

    def test_overnight_break_ignored(self):
        start = datetime(2026, 9, 14, 22)
        end = start + timedelta(hours=8)
        logs = [
            dict(time=t, log_type=k)
            for t, k in (
                (start, "IN"),
                (start + timedelta(hours=1), "OUT"),
                (start + timedelta(hours=3), "IN"),
                (end, "OUT"),
            )
        ]
        self.assertEqual(shift_events(logs, start, end, self.rules)["break_violations"], 0)

    def test_timezone_dhaka(self):
        start = datetime(2026, 9, 14, 23, 30)
        self.assertEqual(local_deadline(start, 24, "Asia/Dhaka"), datetime(2026, 9, 15, 23, 30))

    def test_dst_elapsed_hours(self):
        self.assertEqual(
            local_deadline(datetime(2026, 3, 7, 12), 24, "America/New_York"), datetime(2026, 3, 8, 13)
        )
        self.assertEqual(
            local_deadline(datetime(2026, 10, 31, 12), 24, "America/New_York"), datetime(2026, 11, 1, 11)
        )

    def test_ambiguous_dst_rejected(self):
        with self.assertRaises(ValueError):
            local_deadline(datetime(2026, 11, 1, 1, 30), 24, "America/New_York")

    def test_nonexistent_dst_rejected(self):
        with self.assertRaises(ValueError):
            local_deadline(datetime(2026, 3, 8, 2, 30), 24, "America/New_York")

    def test_invalid_threshold(self):
        with self.assertRaises(ValueError):
            deduction_days(3, 0)


if __name__ == "__main__":
    unittest.main()
