"""Developer utility: regenerate committed DocType metadata (not run at install)."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "reckon_hr_policy"
MODULE = ROOT / "reckon_hr_policy"


def field(name, kind="Check", default=None, **kw):
    result = dict(fieldname=name, fieldtype=kind, label=name.replace("_", " ").title(), **kw)
    if default is not None:
        result["default"] = str(default)
    return result


def doctype(name, fields, *, single=False, child=False, snapshot=False):
    slug = name.lower().replace(" ", "_")
    directory = MODULE / "doctype" / slug
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "__init__.py").touch()
    permissions = (
        []
        if child
        else [
            dict(
                role=role,
                read=1,
                write=int(not snapshot),
                create=int(not snapshot),
                report=1,
                export=1,
                print=1,
            )
            for role in ("System Manager", "HR Manager")
        ]
    )
    doc = dict(
        doctype="DocType",
        name=name,
        module="Reckon HR Policy",
        engine="InnoDB",
        issingle=int(single),
        istable=int(child),
        track_changes=1,
        fields=fields,
        field_order=[f["fieldname"] for f in fields],
        permissions=permissions,
        sort_field="modified",
        sort_order="DESC",
    )
    if not single and not child:
        doc["autoname"] = "hash"
    (directory / f"{slug}.json").write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


settings = []


def section(name, entries):
    settings.append(field(name + "_section", "Section Break", label_override=name))
    settings[-1].pop("label_override")
    settings[-1]["label"] = name.replace("_", " ").title()
    settings.extend(entries)


section(
    "general",
    [
        field("enabled", default=1),
        field(
            "policy_effective_from",
            "Date",
            "Today",
            reqd=1,
            description="No policy payroll before this date. Change rules at payroll-period boundaries.",
        ),
        field("setup_status", "Code", options="JSON", read_only=1),
    ],
)
section(
    "attendance",
    [
        field("late_policy_enabled", default=1),
        field("late_grace_minutes", "Int", 30),
        field("late_occurrences_per_deduction_day", "Int", 3),
        field("early_exit_policy_enabled", default=1),
        field("early_exit_grace_minutes", "Int", 30),
        field("early_exit_occurrences_per_deduction_day", "Int", 3),
    ],
)
section(
    "break",
    [
        field("break_policy_enabled", default=1),
        field("maximum_break_minutes", "Int", 30),
        field("break_violations_per_deduction_day", "Int", 3),
        field("deduction_days_per_threshold", "Float", 1),
    ],
)
section(
    "overtime",
    [
        field("early_entry_overtime_enabled", default=1),
        field("minimum_early_entry_minutes", "Int", 30),
        field("overtime_block_minutes", "Int", 30),
        field(
            "overtime_amount_per_block",
            "Float",
            1,
            description="In Salary Slip currency; complete blocks per shift only.",
        ),
    ],
)
section(
    "payroll",
    [
        field("daily_allowance_enabled", default=1),
        field(
            "daily_allowance_amount",
            "Float",
            2,
            description="In Salary Slip currency per native payment day.",
        ),
        field("attendance_deduction_enabled", default=1),
        field(
            "day_rate_basis",
            "Select",
            "Assignment Base / Working Days",
            options="Assignment Base / Working Days\nAssignment Base / Payment Days\nAssignment Base / Calendar Days\nGross / Payment Days",
        ),
        field("policy_earnings_taxable", default=1),
        field(
            "company_accounts",
            "Table",
            options="Reckon HR Company Account",
            description="Optional overrides for native Company expense/payroll payable accounts; no accounts are invented.",
        ),
    ],
)
section(
    "auto_checkout",
    [
        field("auto_checkout_enabled", default=1),
        field("maximum_open_checkin_hours", "Float", 24),
        field("checkout_batch_size", "Int", 500),
    ],
)
section(
    "shift",
    [
        field("regular_shift_start", "Time", "08:30:00"),
        field("regular_shift_end", "Time", "17:30:00"),
        field("saturday_shift_start", "Time", "10:00:00"),
        field("saturday_shift_end", "Time", "17:30:00"),
        field("sunday_weekly_holiday", default=1),
        field("checkin_buffer_minutes", "Int", 120),
        field("checkout_buffer_minutes", "Int", 60),
        field("half_day_hours", "Float", 4),
        field("absent_hours", "Float", 1),
        field(
            "auto_update_last_sync",
            default=0,
            description="Enable only for real-time checkin ingestion. Otherwise your device integration supplies Shift Type last_sync_of_checkin.",
        ),
        field("assignment_horizon_days", "Int", 60),
        field("auto_assign_shifts", default=1),
    ],
)
section(
    "employee_defaults",
    [
        field("default_payroll_type", "Select", "Monthly", options="Monthly\nHourly"),
        field("default_attendance_policy", "Select", "Standard", options="Standard\nNo Attendance Deduction"),
    ],
)
doctype("Reckon HR Policy Settings", settings, single=True)
doctype(
    "Reckon HR Company Account",
    [
        field("company", "Link", options="Company", reqd=1, in_list_view=1),
        field("expense_account", "Link", options="Account", in_list_view=1),
        field("deduction_account", "Link", options="Account", in_list_view=1),
        field("payroll_payable_account", "Link", options="Account", in_list_view=1),
    ],
    child=True,
)
summary = [
    field("salary_slip", "Link", options="Salary Slip", reqd=1, unique=1, in_list_view=1),
    field("employee", "Link", options="Employee", reqd=1, in_list_view=1),
    field("company", "Link", options="Company", reqd=1),
    field("start_date", "Date", reqd=1, in_list_view=1),
    field("end_date", "Date", reqd=1),
    field("payroll_period", "Link", options="Payroll Period"),
    field("currency", "Link", options="Currency"),
    field("payroll_type", "Data"),
    field("attendance_policy", "Data"),
]
summary += [
    field(n, "Float")
    for n in (
        "working_days",
        "payment_days",
        "late_entries",
        "early_exits",
        "break_violations",
        "late_deduction_days",
        "early_deduction_days",
        "break_deduction_days",
        "total_deduction_days",
        "early_entry_ot_minutes",
        "ot_blocks",
    )
]
summary += [
    field(n, "Currency", options="currency")
    for n in (
        "ot_amount",
        "daily_salary_rate",
        "late_deduction_amount",
        "early_deduction_amount",
        "break_deduction_amount",
        "total_attendance_deduction",
        "daily_allowance_amount",
    )
]
summary += [field("calculation_hash", "Data"), field("calculation", "Code", options="JSON")]
doctype("Reckon HR Attendance Summary", summary, snapshot=True)

for package in (
    "api",
    "attendance",
    "payroll",
    "setup",
    "utils",
    "config",
    "tests",
    "reckon_hr_policy",
    "reckon_hr_policy/doctype",
    "reckon_hr_policy/report",
    "reckon_hr_policy/workspace",
):
    path = ROOT / package
    path.mkdir(parents=True, exist_ok=True)
    (path / "__init__.py").touch()

report_name = "Reckon HR Attendance Policy Report"
report_dir = MODULE / "report" / "reckon_hr_attendance_policy_report"
report_dir.mkdir(parents=True, exist_ok=True)
(report_dir / "__init__.py").touch()
(report_dir / "reckon_hr_attendance_policy_report.json").write_text(
    json.dumps(
        dict(
            doctype="Report",
            name=report_name,
            report_name=report_name,
            ref_doctype="Employee",
            report_type="Script Report",
            is_standard="Yes",
            module="Reckon HR Policy",
            roles=[{"role": "HR Manager"}, {"role": "System Manager"}],
            add_total_row=0,
            disabled=0,
        ),
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)
shortcuts = [
    ("Policy Settings", "Reckon HR Policy Settings"),
    ("Attendance Summary", "Reckon HR Attendance Summary"),
    ("Employee", "Employee"),
    ("Employee Checkin", "Employee Checkin"),
    ("Attendance", "Attendance"),
    ("Salary Slip", "Salary Slip"),
    ("Payroll Entry", "Payroll Entry"),
]
content = [
    dict(id=f"rhp-{i}", type="shortcut", data=dict(shortcut_name=label, col=3))
    for i, (label, _) in enumerate(shortcuts)
]
workspace = dict(
    doctype="Workspace",
    name="Reckon HR Policy",
    label="Reckon HR Policy",
    title="Reckon HR Policy",
    module="Reckon HR Policy",
    public=1,
    icon="hr",
    is_hidden=0,
    content=json.dumps(content),
    roles=[{"role": "HR Manager"}, {"role": "System Manager"}],
    shortcuts=[dict(label=label, type="DocType", link_to=dt, doc_view="List") for label, dt in shortcuts],
    links=[
        dict(type="Card Break", label="Reports"),
        dict(type="Link", label=report_name, link_type="Report", link_to=report_name, is_query_report=1),
    ],
)
ws_dir = MODULE / "workspace" / "reckon_hr_policy"
ws_dir.mkdir(parents=True, exist_ok=True)
(ws_dir / "reckon_hr_policy.json").write_text(json.dumps(workspace, indent=2) + "\n", encoding="utf-8")
