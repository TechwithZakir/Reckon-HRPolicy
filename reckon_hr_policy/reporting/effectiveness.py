"""Explain payroll readiness; this preview does not calculate native payable days."""

from datetime import date

from reckon_hr_policy.policy import consequences


def explain(
    summary,
    rules,
    start,
    end,
    effective,
    *,
    assignment=None,
    assignment_changes=0,
    payroll_based_on=None,
    unmarked_as=None,
    today=None,
    punch_issues=0,
    default_shift=None,
    employee_status="Active",
):
    """Pure report semantics, shared by the server report and regression tests."""
    row = dict(summary)
    today = today or date.today()
    advice = []
    status = "Active"
    blocking = False
    if not rules.enabled:
        status = "Disabled"
        advice.append("Enable Reckon HR Policy Settings to apply policy payroll components.")
    elif end < effective:
        status = "Not yet effective"
        advice.append("This period precedes Policy Effective From; no policy components apply.")
    elif start < effective:
        status = "Effective date conflict"
        blocking = True
        advice.append(
            "The payroll period crosses Policy Effective From. Align the effective date with a payroll boundary."
        )
    elif row["payroll_type"] == "Hourly":
        status = "Hourly — attendance exempt"
        advice.append(
            "Use native Timesheet payroll and approved Timesheets. No policy deductions, allowance or overtime apply."
        )
    elif row["attendance_policy"] == "No Attendance Deduction" or not rules.attendance_deduction_enabled:
        status = "Attendance deductions exempt"
        advice.append(
            "Late, early and break deductions are disabled; monthly allowance/overtime may still apply."
        )
    applicable = rules.enabled and start >= effective
    days = consequences(
        row["late_entries"],
        row["early_exits"],
        row["break_violations"],
        rules,
        row["payroll_type"],
        row["attendance_policy"],
    )
    if not applicable:
        days = dict.fromkeys(days, 0)
        row["ot_amount"] = 0
    if row["payroll_type"] == "Hourly":
        row["ot_amount"] = 0
    row.update(days)
    row["total_deduction_days"] = sum(days.values())
    row["policy_status"] = status
    row["salary_assignment"] = assignment.get("name") if assignment else None
    policy_notices = len(advice)
    if not assignment:
        blocking = True
        advice.append(
            "No submitted Salary Structure Assignment covers the period start. Review Grade Setup compensation and effective dates, assign a configured grade and save Employee; inspect setup errors or preserved native assignments."
        )
    elif assignment_changes:
        blocking = True
        advice.append(
            "Salary assignment changes inside the period. Split payroll at the effective date; this row shows the starting assignment only."
        )
    if employee_status != "Active":
        advice.append("Employee is not Active. Review employment dates and native payroll eligibility.")
    if not default_shift:
        advice.append(
            "No default shift is set. Check dated Shift Assignments before expecting native auto attendance."
        )
    if not row.get("submitted_attendance_dates"):
        advice.append(
            "No submitted Attendance exists. Check Shift Assignment, Process Attendance After and Last Sync of Checkin; process auto attendance after punches are fully synced."
        )
    if row.get("draft_attendance_records"):
        advice.append(
            "Draft Attendance is excluded from late/early deductions. Review and submit valid Attendance records."
        )
    if punch_issues or row.get("excluded_shifts"):
        advice.append(
            "Check missing IN/OUT, duplicate timestamps, skipped/offshift or synthetic punches. Invalid shifts earn no policy break/OT result."
        )
    if row.get("absent_dates") and payroll_based_on != "Attendance":
        advice.append(
            "Submitted Absent dates exist, but Payroll Based On is not Attendance. Review Payroll Settings; absence salary effects follow native payroll."
        )
    if unmarked_as == "Absent" and payroll_based_on == "Attendance":
        advice.append(
            "Unmarked attendance is treated as Absent by native payroll. Finish attendance processing before trusting draft payment days."
        )
    if end > today:
        advice.append(
            "The selected period includes future dates. Counts are incomplete; do not treat this as final payroll approval."
        )
    has_warnings = len(advice) > policy_notices
    if not advice:
        advice.append(
            "Policy checks passed for the available records. Review a draft Salary Slip for payment days, currency amounts, tax and net pay."
        )
    row["readiness"] = (
        "Action required"
        if blocking
        else "Review"
        if has_warnings
        or not applicable
        or not row.get("submitted_attendance_dates")
        or punch_issues
        or row.get("draft_attendance_records")
        or end > today
        else "Preview available"
    )
    row["smart_help"] = " ".join(advice)
    row["late_rule"] = (
        f"{row['late_entries']} dates / {rules.late_occurrences_per_deduction_day} = {row['late_deduction_days']} days"
        if rules.late_policy_enabled
        else "Late deduction disabled"
    )
    row["early_rule"] = (
        f"{row['early_exits']} dates / {rules.early_exit_occurrences_per_deduction_day} = {row['early_deduction_days']} days"
        if rules.early_exit_policy_enabled
        else "Early deduction disabled"
    )
    row["break_rule"] = (
        f"{row['break_violations']} violations / {rules.break_violations_per_deduction_day} × {rules.deduction_days_per_threshold} = {row['break_deduction_days']} days"
        if rules.break_policy_enabled
        else "Break deduction disabled"
    )
    row["allowance_rule"] = (
        f"Native payment days × {rules.daily_allowance_amount}; verify draft slip"
        if applicable and rules.daily_allowance_enabled and row["payroll_type"] == "Monthly"
        else "Not applicable"
    )
    return row
