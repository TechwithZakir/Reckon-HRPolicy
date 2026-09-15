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
section(
    "grade_setup",
    [
        field(
            "auto_setup_from_grade",
            default=1,
            description="Assign Employee Grade and save Employee to provision dated salary and policy automatically.",
        ),
        field(
            "grade_change_timing",
            "Select",
            "Next Month",
            options="Next Month\nToday",
            description="Changes to existing grade-based salary take effect next month by default; initial setup uses policy/grade/joining dates.",
        ),
        field(
            "grade_policies",
            "Table",
            options="Reckon HR Grade Policy",
            description="App seeds Desk and Production Hourly grades for each company. Enter real grade salary/rates once here. Zero rates block salary provisioning, never guessed.",
        ),
    ],
)
section(
    "native_payroll_setup",
    [
        field(
            "manage_native_payroll_settings",
            default=1,
            description="Applies the following three site-wide native Payroll Settings on setup/save. Turn off to manage them directly in HRMS.",
        ),
        field("native_payroll_basis", "Select", "Attendance", options="Attendance\nLeave", reqd=1),
        field(
            "native_unmarked_as",
            "Select",
            "Present",
            options="Present\nAbsent",
            reqd=1,
            description="Present prevents missing/unprocessed records from becoming automatic absence deductions.",
        ),
        field("native_include_holidays", default=0),
        field("auto_create_payroll_periods", default=1),
        field(
            "payroll_year_start_month",
            "Int",
            1,
            description="Month 1–12; creates current and next annual payroll periods only where no existing period overlaps.",
        ),
    ],
)
doctype("Reckon HR Policy Settings", settings, single=True)
doctype(
    "Reckon HR Grade Policy",
    [
        field(
            "grade_name",
            "Data",
            reqd=1,
            in_list_view=1,
            description="Native Employee Grade is created automatically if missing.",
        ),
        field("company", "Link", options="Company", reqd=1, in_list_view=1),
        field("currency", "Link", options="Currency", reqd=1),
        field("payroll_type", "Select", "Monthly", options="Monthly\nHourly", reqd=1, in_list_view=1),
        field("attendance_policy", "Select", "Standard", options="Standard\nNo Attendance Deduction", reqd=1),
        field("monthly_salary", "Currency", 0, options="currency", in_list_view=1),
        field("hourly_rate", "Currency", 0, options="currency", in_list_view=1),
        field("effective_from", "Date", "Today", reqd=1),
        field("employee_grade", "Link", options="Employee Grade", read_only=1),
        field("salary_structure", "Link", options="Salary Structure", read_only=1),
    ],
    child=True,
)
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
effectiveness_name = "Reckon HR Policy Effectiveness Report"
effectiveness_dir = MODULE / "report" / "reckon_hr_policy_effectiveness_report"
effectiveness_dir.mkdir(parents=True, exist_ok=True)
(effectiveness_dir / "__init__.py").touch()
effectiveness_metadata = json.loads(
    (report_dir / "reckon_hr_attendance_policy_report.json").read_text(encoding="utf-8")
)
effectiveness_metadata.update(name=effectiveness_name, report_name=effectiveness_name)
(effectiveness_dir / "reckon_hr_policy_effectiveness_report.json").write_text(
    json.dumps(effectiveness_metadata, indent=2) + "\n", encoding="utf-8"
)
content = [
    dict(id=f"rhp-{i}", type="shortcut", data=dict(shortcut_name=label, col=3))
    for i, (label, _) in enumerate(shortcuts)
]
content.append(
    dict(id="rhp-effectiveness", type="shortcut", data=dict(shortcut_name="Policy Effectiveness", col=3))
)
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
    shortcuts=[dict(label=label, type="DocType", link_to=dt, doc_view="List") for label, dt in shortcuts]
    + [dict(label="Policy Effectiveness", type="Report", link_to=effectiveness_name, is_query_report=1)],
    links=[
        dict(type="Card Break", label="Reports"),
        dict(type="Link", label=report_name, link_type="Report", link_to=report_name, is_query_report=1),
        dict(
            type="Link",
            label=effectiveness_name,
            link_type="Report",
            link_to=effectiveness_name,
            is_query_report=1,
        ),
    ],
)
ws_dir = MODULE / "workspace" / "reckon_hr_policy"
# Ordered operational home: reports are intentionally before salary processing.
stages = [
    (
        "01 · Review policy and grade setup",
        [
            ("Policy and Grade Settings", "DocType", "Reckon HR Policy Settings"),
            ("Employee Grades", "DocType", "Employee Grade"),
            ("Companies and Accounts", "DocType", "Company"),
            ("Native HR Settings", "DocType", "HR Settings"),
            ("Native Payroll Settings", "DocType", "Payroll Settings"),
        ],
    ),
    (
        "02 · Assign employee grades and inspect generated setup",
        [
            ("Assign Grade to Employee", "DocType", "Employee"),
            ("Salary Structure Assignments", "DocType", "Salary Structure Assignment"),
            ("Salary Structures", "DocType", "Salary Structure"),
            ("Salary Components", "DocType", "Salary Component"),
            ("Shift Types", "DocType", "Shift Type"),
            ("Shift Assignments", "DocType", "Shift Assignment"),
            ("Holiday Lists", "DocType", "Holiday List"),
            ("Holiday List Assignments", "DocType", "Holiday List Assignment"),
        ],
    ),
    (
        "03 · Complete attendance and approved hours",
        [
            ("Employee Checkins", "DocType", "Employee Checkin"),
            ("Attendance", "DocType", "Attendance"),
            ("Timesheets for Hourly Payroll", "DocType", "Timesheet"),
            ("Leave Applications", "DocType", "Leave Application"),
        ],
    ),
    (
        "04 · Review reports before processing salary",
        [
            ("Policy Effectiveness and Smart Help", "Report", effectiveness_name),
            ("Attendance Policy Breakdown", "Report", report_name),
            ("Monthly Attendance Sheet", "Report", "Monthly Attendance Sheet"),
        ],
    ),
    (
        "05 · Process salary and retain audit",
        [
            ("Payroll Entry", "DocType", "Payroll Entry"),
            ("Salary Slips", "DocType", "Salary Slip"),
            ("Submitted Policy Snapshots", "DocType", "Reckon HR Attendance Summary"),
        ],
    ),
    (
        "06 · Supporting payroll configuration and diagnostics",
        [
            ("Payroll Periods", "DocType", "Payroll Period"),
            ("Income Tax Slabs", "DocType", "Income Tax Slab"),
            ("Additional Salary", "DocType", "Additional Salary"),
            ("Ledger Accounts", "DocType", "Account"),
            ("Scheduled Jobs", "DocType", "Scheduled Job Type"),
            ("Custom Fields", "DocType", "Custom Field"),
            ("Setup and Checkout Error Log", "DocType", "Error Log"),
        ],
    ),
]
workspace.update(app="reckon_hr_policy", type="Workspace", shortcuts=[], links=[])
content = []
sidebar_items = [
    dict(type="Link", label="Home", link_type="Workspace", link_to="Reckon HR Policy", icon="home")
]
for index, (stage, entries) in enumerate(stages):
    content.append(
        dict(
            id=f"stage-{index}",
            type="header",
            data=dict(text=f'<span class="h4"><b>{stage}</b></span>', col=12),
        )
    )
    sidebar_items.append(dict(type="Section Break", label=stage, collapsible=1, keep_closed=0))
    workspace["links"].append(dict(type="Card Break", label=stage))
    for number, (label, kind, target) in enumerate(entries):
        shortcut = dict(label=label, type=kind, link_to=target)
        if kind == "DocType":
            shortcut["doc_view"] = "List"
        else:
            shortcut["report_ref_doctype"] = (
                "Attendance" if target == "Monthly Attendance Sheet" else "Employee"
            )
        workspace["shortcuts"].append(shortcut)
        workspace["links"].append(
            dict(
                type="Link",
                label=label,
                link_type=kind,
                link_to=target,
                is_query_report=int(kind == "Report"),
            )
        )
        content.append(
            dict(id=f"step-{index}-{number}", type="shortcut", data=dict(shortcut_name=label, col=4))
        )
        sidebar_items.append(dict(type="Link", label=label, link_type=kind, link_to=target, child=1))
workspace["content"] = json.dumps(content)
for folder, data in (
    (
        "workspace_sidebar",
        dict(
            doctype="Workspace Sidebar",
            name="Reckon HR Policy",
            title="Reckon HR Policy",
            app="reckon_hr_policy",
            module="Reckon HR Policy",
            standard=1,
            header_icon="users",
            items=sidebar_items,
        ),
    ),
    (
        "desktop_icon",
        dict(
            doctype="Desktop Icon",
            name="Reckon HR Policy",
            label="Reckon HR Policy",
            app="reckon_hr_policy",
            standard=1,
            icon_type="Link",
            link_type="Workspace Sidebar",
            link_to="Reckon HR Policy",
            icon="users",
            hidden=0,
            roles=[{"role": "HR Manager"}, {"role": "System Manager"}],
        ),
    ),
):
    path = ROOT / folder
    path.mkdir(parents=True, exist_ok=True)
    (path / "reckon_hr_policy.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
ws_dir.mkdir(parents=True, exist_ok=True)
(ws_dir / "reckon_hr_policy.json").write_text(json.dumps(workspace, indent=2) + "\n", encoding="utf-8")
