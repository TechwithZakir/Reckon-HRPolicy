"""Versioned formulas installed in both Salary Components and Salary Structures."""

POLICY_FORMULAS = {
    "RHP Daily Allowance": ("rhp_assignment_preview or rhp_allowance_enabled", "payment_days * rhp_daily_allowance_rate"),
    "RHP Policy Overtime": ("rhp_assignment_preview or rhp_overtime_enabled", "rhp_ot_blocks * rhp_overtime_block_rate"),
    "RHP Late Deduction": ("rhp_assignment_preview or (rhp_deductions_enabled and rhp_late_enabled)", "floor(rhp_late_entries / rhp_late_threshold) * rhp_daily_salary_rate"),
    "RHP Early Exit Deduction": ("rhp_assignment_preview or (rhp_deductions_enabled and rhp_early_enabled)", "floor(rhp_early_exits / rhp_early_threshold) * rhp_daily_salary_rate"),
    "RHP Break Deduction": ("rhp_assignment_preview or (rhp_deductions_enabled and rhp_break_enabled)", "floor(rhp_break_violations / rhp_break_threshold) * rhp_break_days_per_threshold * rhp_daily_salary_rate"),
    "RHP Basic Salary": ("base > 0", "base"),
    "RHP Hourly Wages": ("1", "hour_rate * total_working_hours"),
}


def empty_context():
    return dict(rhp_assignment_preview=1, rhp_allowance_enabled=0, rhp_overtime_enabled=0,
                rhp_deductions_enabled=0, rhp_late_enabled=0, rhp_early_enabled=0, rhp_break_enabled=0,
                rhp_daily_allowance_rate=0, rhp_ot_blocks=0, rhp_overtime_block_rate=0,
                rhp_late_entries=0, rhp_late_threshold=1, rhp_early_exits=0, rhp_early_threshold=1,
                rhp_break_violations=0, rhp_break_threshold=1, rhp_break_days_per_threshold=0,
                rhp_daily_salary_rate=0)


def period_context(summary, s):
    values = empty_context()
    monthly = summary["payroll_type"] == "Monthly"
    values.update(rhp_assignment_preview=0,
                  rhp_allowance_enabled=int(monthly and s.daily_allowance_enabled),
                  rhp_overtime_enabled=int(monthly and s.early_entry_overtime_enabled),
                  rhp_deductions_enabled=int(monthly and summary["attendance_policy"] == "Standard" and s.attendance_deduction_enabled),
                  rhp_late_enabled=s.late_policy_enabled, rhp_early_enabled=s.early_exit_policy_enabled,
                  rhp_break_enabled=s.break_policy_enabled, rhp_daily_allowance_rate=s.daily_allowance_amount,
                  rhp_ot_blocks=summary["ot_blocks"], rhp_overtime_block_rate=s.overtime_amount_per_block,
                  rhp_late_entries=summary["late_entries"], rhp_late_threshold=s.late_occurrences_per_deduction_day,
                  rhp_early_exits=summary["early_exits"], rhp_early_threshold=s.early_exit_occurrences_per_deduction_day,
                  rhp_break_violations=summary["break_violations"], rhp_break_threshold=s.break_violations_per_deduction_day,
                  rhp_break_days_per_threshold=s.deduction_days_per_threshold,
                  rhp_daily_salary_rate=summary["daily_salary_rate"])
    return values
