"""Pure effective-date selection for automatic grade assignment changes."""

from datetime import timedelta


def change_date(initial_date, today, timing, last_payroll_end=None):
    next_month = (today.replace(day=28) + timedelta(days=4)).replace(day=1)
    effective = max(initial_date, next_month if timing == "Next Month" else today)
    if last_payroll_end and effective <= last_payroll_end:
        effective = last_payroll_end + timedelta(days=1)
    return effective


def same_compensation(previous, *, grade, amount, payroll_type, attendance_policy, currency):
    return (
        previous.get("rhp_grade") == grade
        and previous.get("rhp_payroll_type") == payroll_type
        and previous.get("rhp_attendance_policy") == attendance_policy
        and previous.get("currency") == currency
        and float(previous.get("rhp_hourly_rate" if payroll_type == "Hourly" else "base") or 0)
        == float(amount)
    )
