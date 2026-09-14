"""Pure, deterministic policy arithmetic. No database or Frappe dependency."""

from dataclasses import asdict, dataclass
from datetime import timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Rules:
    enabled: int = 1
    late_policy_enabled: int = 1
    late_grace_minutes: int = 30
    late_occurrences_per_deduction_day: int = 3
    early_exit_policy_enabled: int = 1
    early_exit_grace_minutes: int = 30
    early_exit_occurrences_per_deduction_day: int = 3
    break_policy_enabled: int = 1
    maximum_break_minutes: int = 30
    break_violations_per_deduction_day: int = 3
    deduction_days_per_threshold: float = 1
    early_entry_overtime_enabled: int = 1
    minimum_early_entry_minutes: int = 30
    overtime_block_minutes: int = 30
    overtime_amount_per_block: float = 1
    daily_allowance_enabled: int = 1
    daily_allowance_amount: float = 2
    attendance_deduction_enabled: int = 1
    sunday_weekly_holiday: int = 1

    def as_dict(self):
        return asdict(self)


def deduction_days(count, threshold, multiplier=1):
    if count < 0 or threshold <= 0 or multiplier < 0:
        raise ValueError("Counts must be nonnegative and thresholds positive")
    return (count // threshold) * multiplier


def overtime(minutes, rules):
    if not rules.enabled or not rules.early_entry_overtime_enabled:
        return 0, 0.0
    if rules.overtime_block_minutes <= 0:
        raise ValueError("Overtime block must be positive")
    blocks = (
        int(minutes // rules.overtime_block_minutes) if minutes >= rules.minimum_early_entry_minutes else 0
    )
    return blocks, float(Decimal(blocks) * Decimal(str(rules.overtime_amount_per_block)))


def strict_pairs(logs):
    """Reject an ambiguous sequence in full; never guess the meaning of duplicate punches."""
    ordered = sorted(logs, key=lambda x: (x["time"], x.get("name", "")))
    if not ordered or len(ordered) % 2:
        return []
    previous = None
    for index, log in enumerate(ordered):
        if log.get("log_type") != ("IN" if index % 2 == 0 else "OUT"):
            return []
        if previous and log["time"] <= previous:
            return []
        previous = log["time"]
    return list(zip(ordered[::2], ordered[1::2], strict=True))


def shift_events(logs, start, end, rules, holiday=False):
    result = dict(break_violations=0, early_entry_ot_minutes=0.0, ot_blocks=0, ot_amount=0.0, breaks=[])
    if holiday or not rules.enabled:
        return result
    pairs = strict_pairs(logs)
    if not pairs:
        return result
    # No overnight break is ever penalized, including shifts spanning midnight.
    for (_, out_log), (in_log, _) in zip(pairs, pairs[1:], strict=False):
        out_time, in_time = out_log["time"], in_log["time"]
        if start <= out_time < in_time <= end and out_time.date() == in_time.date():
            minutes = (in_time - out_time).total_seconds() / 60
            if rules.break_policy_enabled and minutes > rules.maximum_break_minutes:
                result["break_violations"] += 1
                result["breaks"].append(
                    dict(out=out_log.get("name"), checkin=in_log.get("name"), minutes=minutes)
                )
    # A complete, unambiguous shift is required for paid early arrival.
    if pairs[0][0]["time"] < start and pairs[-1][1]["time"] >= start:
        minutes = (start - pairs[0][0]["time"]).total_seconds() / 60
        result["early_entry_ot_minutes"] = minutes
        result["ot_blocks"], result["ot_amount"] = overtime(minutes, rules)
    return result


def consequences(late, early, breaks, rules, payroll_type="Monthly", attendance_policy="Standard"):
    eligible = (
        rules.enabled
        and rules.attendance_deduction_enabled
        and payroll_type == "Monthly"
        and attendance_policy == "Standard"
    )
    return {
        "late_deduction_days": deduction_days(late, rules.late_occurrences_per_deduction_day)
        if eligible and rules.late_policy_enabled
        else 0,
        "early_deduction_days": deduction_days(early, rules.early_exit_occurrences_per_deduction_day)
        if eligible and rules.early_exit_policy_enabled
        else 0,
        "break_deduction_days": deduction_days(
            breaks, rules.break_violations_per_deduction_day, rules.deduction_days_per_threshold
        )
        if eligible and rules.break_policy_enabled
        else 0,
    }


def local_deadline(start, hours, zone):
    """Elapsed hours in UTC, returned in site wall time. Reject ambiguous/nonexistent local times."""
    tz = ZoneInfo(zone)
    if start.tzinfo is not None:
        raise ValueError("Expected a naive site-local checkin")
    aware = start.replace(tzinfo=tz)
    if aware.utcoffset() != start.replace(tzinfo=tz, fold=1).utcoffset():
        raise ValueError("Ambiguous or nonexistent site-local time requires HR review")
    if aware.astimezone(timezone.utc).astimezone(tz).replace(tzinfo=None) != start:
        raise ValueError("Nonexistent site-local time requires HR review")
    due = (aware.astimezone(timezone.utc) + timedelta(hours=hours)).astimezone(tz).replace(tzinfo=None)
    if due.replace(tzinfo=tz).utcoffset() != due.replace(tzinfo=tz, fold=1).utcoffset():
        raise ValueError("Ambiguous checkout time requires HR review")
    return due
