"""Bounded bulk source loading; no full-table checkin scans and no stale persistent cache."""

from collections import defaultdict
from datetime import datetime, time, timedelta

import frappe
from frappe.utils import get_datetime, getdate

from reckon_hr_policy.policy import consequences, shift_events
from reckon_hr_policy.utils.settings import policy_types, rules, settings


def collect(employees, start, end, s=None):
    """One attendance and one checkin range query for a batch of up to 200 employees."""
    s = s or settings()
    start, end = getdate(start), getdate(end)
    if end < start or (end - start).days > 366:
        frappe.throw("Policy calculation requires a valid period of at most 367 days")
    if not employees:
        return {}
    if len(employees) > 200:
        frappe.throw("Use batches of at most 200 employees")
    names = [e.name for e in employees]
    attendance = frappe.get_all(
        "Attendance",
        filters={"employee": ["in", names], "attendance_date": ["between", [start, end]], "docstatus": 1},
        fields=[
            "name",
            "employee",
            "attendance_date",
            "status",
            "late_entry",
            "early_exit",
            "shift",
            "modified",
        ],
        order_by="employee,attendance_date,name",
    )
    # A one-day guard captures overnight shifts but only shifts starting in the requested period count.
    checkins = frappe.get_all(
        "Employee Checkin",
        filters={
            "employee": ["in", names],
            "time": [
                "between",
                [
                    datetime.combine(start - timedelta(days=1), time.min),
                    datetime.combine(end + timedelta(days=2), time.min),
                ],
            ],
        },
        fields=[
            "name",
            "employee",
            "time",
            "log_type",
            "shift",
            "shift_start",
            "shift_end",
            "skip_auto_attendance",
            "offshift",
            "rhp_auto_checkout_for",
            "modified",
        ],
        order_by="employee,time,name",
    )
    holidays = holiday_map(
        employees,
        start,
        end,
        {a.shift for a in attendance if a.shift} | {c.shift for c in checkins if c.shift},
    )
    by_employee = defaultdict(list)
    shifts = defaultdict(lambda: defaultdict(list))
    for row in attendance:
        by_employee[row.employee].append(row)
    for row in checkins:
        if row.shift_start and row.shift_end:
            row.time, row.shift_start, row.shift_end = map(
                get_datetime, (row.time, row.shift_start, row.shift_end)
            )
            if start <= row.shift_start.date() <= end:
                shifts[row.employee][(row.shift, row.shift_start, row.shift_end)].append(row)
    r = rules(s)
    results = {}
    for employee in employees:
        payroll_type, policy = policy_types(employee, s)
        result = dict(
            employee=employee.name,
            employee_name=employee.employee_name,
            payroll_type=payroll_type,
            attendance_policy=policy,
            late_entries=0,
            early_exits=0,
            break_violations=0,
            early_entry_ot_minutes=0.0,
            ot_blocks=0,
            ot_amount=0.0,
            evidence=[],
            excluded_shifts=[],
        )
        late_dates, early_dates = set(), set()
        for row in by_employee[employee.name]:
            if is_holiday(employee.name, row.attendance_date, row.shift, holidays, r) or row.status not in (
                "Present",
                "Half Day",
                "Work From Home",
            ):
                continue
            if row.late_entry:
                late_dates.add(row.attendance_date)
            if row.early_exit:
                early_dates.add(row.attendance_date)
            result["evidence"].append(
                dict(
                    attendance=row.name,
                    date=row.attendance_date,
                    late=row.late_entry,
                    early=row.early_exit,
                    modified=row.modified,
                )
            )
        result["late_entries"], result["early_exits"] = len(late_dates), len(early_dates)
        for (shift, shift_start, shift_end), logs in shifts[employee.name].items():
            if any(log.skip_auto_attendance or log.offshift or log.rhp_auto_checkout_for for log in logs):
                result["excluded_shifts"].append(
                    dict(
                        shift=shift,
                        start=shift_start,
                        reason="Contains skipped, offshift, or synthetic punch",
                    )
                )
                continue
            values = shift_events(
                logs,
                shift_start,
                shift_end,
                r,
                holiday=is_holiday(employee.name, shift_start.date(), shift, holidays, r),
            )
            for key in ("break_violations", "early_entry_ot_minutes", "ot_blocks", "ot_amount"):
                result[key] += values[key]
            result["evidence"].append(
                dict(
                    shift=shift,
                    start=shift_start,
                    end=shift_end,
                    checkins=[
                        dict(name=log.name, time=log.time, log_type=log.log_type, modified=log.modified)
                        for log in logs
                    ],
                    breaks=values["breaks"],
                    ot_blocks=values["ot_blocks"],
                )
            )
        result.update(
            consequences(
                result["late_entries"],
                result["early_exits"],
                result["break_violations"],
                r,
                payroll_type,
                policy,
            )
        )
        result["total_deduction_days"] = sum(
            result[k] for k in ("late_deduction_days", "early_deduction_days", "break_deduction_days")
        )
        if payroll_type == "Hourly":
            result["ot_amount"] = 0  # Native hourly wages already pay actual Timesheet hours.
        results[employee.name] = result
    return results


def holiday_map(employees, start, end, shifts):
    from hrms.utils.holiday_list import get_assigned_holiday_lists_to_employee_and_company

    ranges = get_assigned_holiday_lists_to_employee_and_company(
        list({e.name for e in employees} | {e.company for e in employees}), start, end
    )
    shift_lists = (
        dict(
            frappe.get_all(
                "Shift Type",
                filters={"name": ["in", list(shifts)]},
                fields=["name", "holiday_list"],
                as_list=True,
            )
        )
        if shifts
        else {}
    )
    lists = {r["holiday_list"] for rows in ranges.values() for r in rows} | {
        v for v in shift_lists.values() if v
    }
    dates = defaultdict(set)
    if lists:
        for row in frappe.get_all(
            "Holiday",
            filters={"parent": ["in", list(lists)], "holiday_date": ["between", [start, end]]},
            fields=["parent", "holiday_date"],
        ):
            dates[row.parent].add(row.holiday_date)
    return dict(
        ranges=ranges, shift_lists=shift_lists, dates=dates, companies={e.name: e.company for e in employees}
    )


def is_holiday(employee, day, shift, mapping, r):
    day = getdate(day)
    if r.sunday_weekly_holiday and day.weekday() == 6:
        return True
    holiday_list = mapping["shift_lists"].get(shift)
    if holiday_list:
        return day in mapping["dates"][holiday_list]
    for assigned in (employee, mapping["companies"][employee]):
        for span in mapping["ranges"].get(assigned, []):
            if getdate(span["from_date"]) <= day <= getdate(span["to_date"]):
                return day in mapping["dates"][span["holiday_list"]]
    return False
