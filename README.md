# Reckon HR Policy

Installable Frappe custom app implementing configurable attendance consequences and payroll additions on top of Frappe HR v16. No core files, Server Scripts, monkey patches, or replacement payroll engine are used.

**Release status: 0.1.0 — implementation candidate, not production-certified.** The development workspace contains no installed Frappe site, Bench, database, Redis, or Linux runtime. Official upstream source was inspected instead. Standalone tests and source-contract checks can run here; installation, migration, native payroll, concurrency, tax, and permission tests must pass on the actual deployment site before production acceptance. Do not interpret a successful wheel build or source inspection as a successful site installation.

## Source inspected and compatibility boundary

| Project | Inspected version | Official `version-16` commit |
|---|---|---|
| Frappe | 16.33.1 | [`988e54f3c4c291e2077a83809663f123731abe76`](https://github.com/frappe/frappe/tree/988e54f3c4c291e2077a83809663f123731abe76) |
| HRMS | 16.18.1 | [`a4768b441cff346def505e27f2a2229ee1e05b9b`](https://github.com/frappe/hrms/tree/a4768b441cff346def505e27f2a2229ee1e05b9b) |
| ERPNext | 16.34.2 | [`4048fb70e14d1843956fcdabb7c3cca75a1cbcdd`](https://github.com/frappe/erpnext/tree/4048fb70e14d1843956fcdabb7c3cca75a1cbcdd) |

These are reference checkouts, **not evidence of the user's installed versions**. They are excluded from the app package and Git. Installation/migration require these minimum versions, reject v17, and inspect required DocType fields and method signatures on the actual host. Older v16 builds are deliberately rejected because the inspected payroll and Holiday List Assignment APIs differ from earlier implementations. Newer v16 signatures passing the check still require regression testing.

The inspected Frappe revision requires **Python >=3.14,<3.15**. Follow that revision's supported operating system, database, Redis, Node and Bench requirements. The independent arithmetic tests were run with Python 3.12; they are intentionally framework-free and do not substitute for the required Python 3.14 site tests.

Inspected controllers/schemas: Employee, HRMS Employee override, Employee Checkin, Attendance, Shift Type, Shift Assignment, Holiday List, Holiday List Assignment, Salary Component, Salary Structure, Salary Structure Assignment, Salary Slip, Payroll Entry, Timesheet, HRMS Timesheet override, HRMS install-time custom fields, and Frappe controller extension loading.

## Install

Use an existing, supported Linux Frappe HR bench with Frappe, ERPNext and HRMS installed. Back up the target site and first install on a restored staging copy.

```bash
bench version
bench --site <site> backup --with-files
bench get-app /absolute/path/to/Reckon-HRPolicy
# Once this repository is published, bench get-app <repository-url> also works.
bench --site <site> install-app reckon_hr_policy
bench --site <site> migrate
bench --site <site> enable-scheduler
bench restart
```

Open **Reckon HR Policy** in Desk, then **Policy Settings**. Review the effective date, shifts, auto-attendance ingestion mode, and company account mappings. The app does not assume a company, currency, employee ID, department, grade, designation, or salary.

Normal installation creates all app metadata and reusable payroll/schedule masters. To repeat setup or inspect compatibility:

```bash
bench --site <site> execute reckon_hr_policy.setup.compatibility.check
bench --site <site> execute reckon_hr_policy.setup.install.setup
```

The Settings form also has **Refresh Setup Status**. `setup_status` records actual host versions and configuration warnings; it never declares production certification automatically. Provisioning errors for individual employees are logged as **RHP setup failed: employee** in Error Log. Other employees continue through a savepoint-isolated daily provisioning run.

## What installation creates

| Data | Behavior |
|---|---|
| Reckon HR Policy Settings | Single central Settings DocType; HR Manager and System Manager access |
| Reckon HR Company Account | Settings child rows for optional per-company account overrides |
| Reckon HR Attendance Summary | Immutable snapshot per submitted Salary Slip; stores source evidence and calculation JSON |
| Employee fields | RHP Payroll Type, Attendance Policy, Hourly Rate, Monthly Salary, Salary Effective From |
| Salary Structure Assignment fields | Dated payroll type, attendance policy and hourly rate snapshots |
| Salary Slip fields | Read-only calculation JSON and SHA-256 digest |
| Employee Checkin fields | Unique automatic-checkout source link and reason |
| Ownership fields | Hidden `rhp_managed` marker on app-created masters/assignments |
| Salary Components | RHP Daily Allowance, RHP Policy Overtime, RHP Late Deduction, RHP Early Exit Deduction, RHP Break Deduction |
| Base wage components | RHP Basic Salary, RHP Hourly Wages |
| Salary Structures | Submitted Monthly and Hourly structure per company/currency; deterministic hashed names |
| Shifts | RHP Regular and RHP Saturday with native strict IN/OUT auto-attendance settings |
| Holiday Lists | Current and next calendar year, Sundays by default |
| Holiday List Assignments | Native company assignments where an existing effective calendar does not already govern the period |
| Employee schedules | Blank default shift becomes RHP Regular; Saturday single-day submitted assignments, normally 60 days ahead |
| Workspace/report | Desk shortcuts and Reckon HR Attendance Policy Report |
| Jobs | Hourly automatic checkout, daily calendar/schedule/salary provisioning; standard hooks register the jobs |
| Indexes | Employee Checkin `(employee,time)` and `(log_type,time)`; Attendance `(employee,attendance_date,docstatus)` |

An existing record with an app-reserved name but without app ownership stops setup rather than being overwritten. Existing unrelated salary structures, employee salary assignments, holiday calendars and shift assignments are preserved. Managed reusable records are updated from Settings; submitted salary assignments are never rewritten. No demo employee, salary amount, statutory tax rule, bank account, or financial account is inserted on production installation.

## Employee and hourly setup

1. Review central defaults. Blank employee category fields resolve to Monthly and Standard initially. Grade does not determine behavior.
2. Enter actual **RHP Monthly Salary** or **RHP Hourly Rate** on Employee, plus **RHP Salary Effective From**. Use the native Employee Salary Currency when different from Company currency.
3. Save Employee. The app creates the appropriate native Salary Structure Assignment if no unrelated assignment already controls that date. Native validation still applies, including payable account and employee dates.
4. For later salary/category changes, use a new effective date. The app rejects attempts to mutate an existing dated assignment and dates overlapping submitted payroll. Payroll periods crossing an assignment change are rejected: split at that date.
5. Run the normal Payroll Entry process. Monthly and Timesheet payroll use their native separate modes.

The Monthly structure uses native `base` formula and **Depends on Payment Days** on RHP Basic Salary. `RHP Monthly Salary` is an explicit input for assignment creation; it is not inferred from annual CTC. Its currency must be understood before entering a number.

The Hourly structure uses native Timesheet wages. A small Salary Structure Assignment mixin supplies the **dated assignment rate** to native `get_timesheet_config`; HRMS still selects Timesheets, calculates hours, multiplies wages, calculates totals and manages Timesheet payroll links. Changing today's Employee rate does not alter an older assignment's rate. Hourly employees receive no policy attendance deductions, daily allowance or policy overtime; this avoids paying checkin-derived overtime on top of native Timesheet hours.

**Timesheet recording and approval remain native operational work.** Checkins are not converted to Timesheets. That optional bridge was deliberately not implemented: a synthetic or unapproved punch is not sufficient evidence for paid production hours. Existing native Hourly structures retain their own configured rate unless the assignment is app-managed.

## Central policy values

| Section | Field / initial value | Meaning |
|---|---|---|
| General | Enabled = Yes | Controls calculations and provisioning jobs; disabling does not cancel existing native schedules |
| General | Policy Effective From = installation date | No policy applied before this date; a crossing Salary Slip is blocked |
| Attendance | Late Policy Enabled = Yes | Native Attendance late flag → policy consequence |
| Attendance | Late Grace Minutes = 30 | Applied to managed native Shift Types |
| Attendance | Late Occurrences Per Deduction Day = 3 | Floor division, no remainder carry-forward |
| Attendance | Early Exit Policy Enabled = Yes | Native Attendance early flag → policy consequence |
| Attendance | Early Exit Grace Minutes = 30 | Applied to managed native Shift Types |
| Attendance | Early Exit Occurrences Per Deduction Day = 3 | Floor division |
| Break | Break Policy Enabled = Yes | Strict intermediate OUT→IN break checks |
| Break | Maximum Break Minutes = 30 | Exactly 30 is allowed; >30 is a violation |
| Break | Break Violations Per Deduction Day = 3 | Floor division |
| Break | Deduction Days Per Threshold = 1 | Fractional nonnegative values allowed |
| Overtime | Early Entry Overtime Enabled = Yes | Can be disabled explicitly |
| Overtime | Minimum Early Entry Minutes = 30 | Eligibility gate; not subtracted from eligible minutes |
| Overtime | Overtime Block Minutes = 30 | Complete blocks per shift only |
| Overtime | Overtime Amount Per Block = 1 | Units of Salary Slip currency, not hard-coded dollars |
| Payroll | Daily Allowance Enabled = Yes | Monthly employees, including No Attendance Deduction |
| Payroll | Daily Allowance Amount = 2 | Per native payment day, in Salary Slip currency |
| Payroll | Attendance Deduction Enabled = Yes | Global gate for the three deductions |
| Payroll | Day Rate Basis = Assignment Base / Working Days | See calculation below |
| Payroll | Policy Earnings Taxable = Yes | Native taxable flag for allowance and policy overtime; review your tax configuration |
| Payroll | Company Accounts | Expense/deduction expense/payroll payable overrides, all company-scoped |
| Auto Checkout | Auto Checkout Enabled = Yes | Server scheduled closure |
| Auto Checkout | Maximum Open Checkin Hours = 24 | Elapsed hours, site timezone |
| Auto Checkout | Checkout Batch Size = 500 | Keyset-paginated candidates; maximum 5000 |
| Shift | Regular Start / End = 08:30 / 17:30 | End time is an explicit implementation default, not supplied by the business brief |
| Shift | Saturday Start / End = 10:00 / 17:30 | End configurable |
| Shift | Sunday Weekly Holiday = Yes | Excluded from policy events, even if Attendance was marked |
| Shift | Checkin / Checkout Buffer Minutes = 120 / 60 | Native shift association windows |
| Shift | Half Day / Absent Hours = 4 / 1 | Native auto-attendance thresholds; review before use |
| Shift | Auto Update Last Sync = No | Safe default for delayed biometric-device ingestion |
| Shift | Assignment Horizon Days = 60 | Saturday assignments extended daily, maximum 366 |
| Shift | Auto Assign Shifts = Yes | Applies only to employees with blank/RHP Regular default shift |
| Employee Defaults | Payroll Type = Monthly | Alternative Hourly |
| Employee Defaults | Attendance Policy = Standard | Alternative No Attendance Deduction |

Positive threshold and finite nonnegative amount validation prevents divide-by-zero and invalid values. Managed shifts must begin and end on the same date. Existing native night shifts can be used; their midnight break is never penalized.

Change policy values at payroll-period boundaries. Draft payroll uses the current Settings values; this release does not offer a multi-version, effective-dated central rule history. Submitted slips retain their exact rule/result snapshots. Dated employee assignments preserve employee category/rate history. Changing defaults does not rewrite existing assignment snapshots.

## Attendance and break algorithm

1. Read only submitted Attendance for the selected employees and payroll dates. Count late/early flags on Present, Half Day, or Work From Home. Ignore Absent and On Leave so those statuses remain native absence/LWP concerns.
2. Exclude Sunday when enabled and applicable native holidays. A Shift Type holiday list takes precedence; otherwise dated employee holiday assignments take precedence over company assignments. Half-holiday dates are conservatively excluded as whole dates from these extra policy penalties.
3. Count each late/early date at most once, even with multiple shifts. Late/early classification itself remains entirely HRMS's responsibility. Altering grace settings never rewrites old Attendance.
4. Fetch checkins in a bounded period with a one-day guard. Group by employee plus native shift start/end timestamps. Only shifts starting within the period count. The native assignment determines Saturday's 10:00 start; there is no inferred grade or weekday payroll classification.
5. Sort each shift's punches by time/name. Require strictly increasing timestamps, alternating explicit `IN, OUT, IN, OUT`, starting IN and ending OUT. Reject the whole sequence if incomplete, tied, blank, or nonalternating. Never infer a missing direction.
6. Reject a shift for break/OT consequences if it contains an offshift, skipped, or synthetic checkout punch. For valid pairs, inspect the gap between each completed OUT and the next IN. Both must be within the native shift, on the same calendar date, and the gap must exceed the configured maximum.
7. Final end-of-shift OUT has no next IN within the same shift and is not a break. Overnight gaps and outside-shift gaps are not breaks. Multiple excessive intermediate gaps in one shift count separately.
8. Early entry overtime requires a complete valid shift and an OUT at/after shift start. Eligible minutes are from the first IN to shift start; the native pre-shift buffer limits which early punches belong to that shift.

Examples: 29/30-minute breaks → zero; 31-minute break → one. Three/six violations → one/two days. Early entries of 29/30/59/60 minutes → 0/1/1/2 currency units with defaults. Partial blocks are discarded **per shift**, never pooled across days. Configured minimum early minutes is a gate, not a deductible allowance.

## Salary calculation and lifecycle

The inspected `SalarySlip.validate` sets dates, native working/payment days and the applicable Salary Structure Assignment, then calls `calculate_net_pay`, then YTD/MTD calculations. `calculate_net_pay` computes earnings, gross, deductions/tax, loans, regional deductions and employer contributions before precision/net totals.

The cooperative mixin calls `super()` and inserts policy rows **after native earnings calculation, before gross/deductions/tax totals**. It does not append components in a late `validate` event after totals have already been finalized. It removes only reserved policy rows on recalculation and deterministically reconstructs them. Adding those reserved components to a Salary Structure or Additional Salary is rejected to prevent competing amounts.

Default daily rate:

```text
daily_salary_rate = dated Salary Structure Assignment.base / Salary Slip.total_working_days
late_days         = floor(late_dates / late_threshold)
early_days        = floor(early_dates / early_threshold)
break_days        = floor(break_violations / break_threshold) × configured multiplier
deduction_amount  = applicable days × daily_salary_rate
daily_allowance   = native payment_days × configured daily amount
```

The denominator comes from HRMS Payroll Settings and its actual holiday/LWP/attendance/joining/relieving-date computation. There is no hard-coded 26-day month. The default is appropriate for the generated Monthly structure where `base` is the monthly basic wage. For an existing structure with a different composition, explicitly choose/review the desired basis:

- **Assignment Base / Working Days**: full-cycle base divided by native total working days.
- **Assignment Base / Payment Days**: full-cycle base divided by payable days; intentionally increases the rate when payable days decrease.
- **Assignment Base / Calendar Days**: full-cycle base divided by inclusive Salary Slip period dates.
- **Gross / Payment Days**: actual native earnings before policy allowance/OT, divided by payment days; includes native extra earnings in that gross basis.

A zero denominator produces zero rate, never division by zero. Component amounts are rounded using native Salary Slip currency precision; the daily rate itself is not prematurely rounded. There is no implicit cap on penalty days, and a day can contribute to all three policies. Native negative-net-pay validation still applies. HR must review that policy choice.

Daily allowance uses native `payment_days` directly. **Depends on Payment Days is off on the policy components** because their amounts are already calculated for payment days; applying it again would double-prorate. Basic Salary uses the native payment-days mechanism normally. All totals, exchange rates, loan handling, regional calculations and YTD remain native.

Policy earnings inherit the configured native taxable flag. Native payroll may project current recurring earnings for future tax periods. Jurisdiction-specific tax components/slabs and tax treatment of deductions are not invented by this app. The generated minimal wage structures do not automatically contain statutory deductions. Validate with the organization's approved payroll/tax structures before live use.

## Automatic checkout

The hourly job seeks terminal IN punches old enough to reach the maximum duration. It uses a unique `rhp_auto_checkout_for` source link, native ORM insertion, and an Employee row lock. Ordinary Employee Checkin inserts acquire the same lock; the job rechecks the source and subsequent punches under the lock. A repeated run creates no additional OUT. A later OUT means the pair is complete; a later IN or ambiguous duplicate means the earlier sequence is ambiguous, so no old synthetic OUT is inserted across it. This conservative case requires HR review.

The generated OUT is dated **source IN + maximum elapsed hours**, not the scheduler execution time. It carries an explanatory reason. Frappe `now_datetime()` and the configured site timezone are used. Deadline calculation converts through UTC for DST transitions. Ambiguous/nonexistent wall times are logged for HR review instead of guessed. Source checkins are never deleted or rewritten.

**Synthetic OUT has `skip_auto_attendance=1`.** It closes the administrative open record but does not fabricate 24 paid hours or establish a physical location. It is excluded from break/OT computation. Native attendance for an incomplete source shift may still need HR correction; this is intentional. The dedicated synthetic metadata cannot be supplied/changed through an ordinary Checkin insert/update. Inactive employees or other native validation failures are logged, not bypassed.

Auto attendance needs a trustworthy `last_sync_of_checkin`. If checkins arrive live, enable central **Auto Update Last Sync** to use native HRMS's watermark update. If a biometric system backfills data, leave that off and let the device integration update the watermark after a completed synchronization. Advancing it blindly could mark employees absent before their punches arrive. No administrator must create a Scheduled Job manually, but the site's scheduler/workers must be operational.

## Audit and reporting

Draft slips contain fresh calculation JSON, rules, assignment, numerator/denominator, source Attendance names/flags, valid punch timestamps/directions, break evidence and final native totals. On Salary Slip submission, the same transaction inserts one immutable **Reckon HR Attendance Summary** and a SHA-256 digest. The digest is an integrity check, not a digital signature. The snapshot is not edited when Settings, Employee or source Attendance later changes.

Cancelled slips retain snapshots; an amended slip receives its own snapshot. The Summary controller rejects edits and deletion through the ORM, including normal manager actions. Database administrators remain technically able to change the database, as with other Frappe records. No browser JavaScript computes salary amounts.

**Reckon HR Attendance Policy Report** provides company, employee, department, branch, Payroll Period/from/to dates, payroll type and attendance policy filters. It shows late/early/break events and days, total days, OT minutes and amount. It uses `get_list` for employees so Frappe User Permissions are respected. Source records are read only for that permitted employee batch. It is a live preview with current employee defaults and current policy, not an immutable historical payroll report; use Salary Slip/Summary for the dated applied result. Never aggregate currency amounts across different currencies.

The report bulk-loads up to 200 employees with bounded Attendance/Checkin queries and bulk holiday assignments. In-memory grouping is linear in the fetched records. Individual slips read their own employee and date range. Draft results are intentionally not persisted/reused across saves: invalidation must account for checkin backfills, Attendance amendments, holiday assignments and policy changes. Reuse within a calculation avoids duplicate component application; subsequent calculations deliberately reread source data. High-volume load/EXPLAIN testing on the deployment database is still required. Daily employee provisioning currently iterates active employees and native assignment validations; benchmark its maintenance window separately from payroll.

## Security and ownership

- Settings and report: HR Manager/System Manager only.
- Employee salary policy inputs: permission level 1, plus server role validation when changed.
- Summary: manager read/report/export/print only; server-only creation and immutable controller.
- Status API: manager role check; no guest access.
- Native employees, payroll, attendance and checkins retain their native permissions and validations.
- Parameterized Frappe Query Builder/ORM queries; no interpolated SQL from filters.
- No manual commit in payroll calculation or checkout; Frappe owns request/job transactions. Savepoints isolate job failures. Core controller behavior may have its own transactions, which is another reason to stage installation tests.
- `rhp_managed` identifies provisioned records. A privileged database administrator can alter ownership; it is not a cryptographic trust boundary.

## Core hooks and APIs used

| Hook/API | Purpose |
|---|---|
| `required_apps` | Frappe/ERPNext/HRMS dependency order |
| `before_install`, `before_migrate` | Version, field and signature compatibility checks |
| `after_install`, `after_migrate` | Idempotent bootstrap |
| `before_uninstall` | Prevent loss of payroll snapshots |
| `extend_doctype_class[Salary Slip]` | Cooperative `calculate_net_pay` and `calculate_component_amounts` integration |
| `extend_doctype_class[Salary Structure Assignment]` | Native `get_timesheet_config` dated rate |
| `extend_doctype_class[Employee Checkin]` | `validate` lock/metadata checks and synthetic-location exception |
| `doc_events Employee.validate/on_update` | Protect policy inputs and provision native assignments |
| `doc_events Salary Structure Assignment.before_validate` | Snapshot employee policy/rate on new native assignments |
| `doc_events Salary Slip.on_submit` | Atomic audit snapshot |
| `doc_events Additional Salary.validate` | Reserve policy component identifiers |
| `doc_events Salary Structure.validate` | Prevent conflicting policy rows |
| `scheduler_events.hourly/daily` | Checkout and setup maintenance |
| `SalarySlip._get_ssa_doc`, `add_timesheet_earning_component` | Native assignment/rate and Timesheet wages; private API guarded by the inspected source contract |
| `SalarySlip.update_component_row`, `get_salary_component_data` | Native component flags, proration and deterministic component updates |
| `SalarySlip.actual_start_date/actual_end_date`, `total_working_days/payment_days` | Native employment/payroll date boundaries |
| `get_assigned_holiday_list`, `get_assigned_holiday_lists_to_employee_and_company` | HRMS v16 dated calendars and bulk holiday ranges |
| `create_custom_fields(update=True)` | Install/update app-owned custom fields |
| `add_permission`, `update_permission_property` | Employee salary policy permission level |
| `frappe.get_doc/new_doc/get_cached_doc/get_cached_value/get_list/get_all` | Native documents, metadata, settings and permission-aware employee selection |
| `frappe.db.get_value(for_update=True)`, Query Builder `for_update`, `ExistsCriterion` | Locking and candidate filtering |
| `frappe.db.exists/count/set_value/set_single_value/add_index/savepoint/rollback` | Setup integrity, state, indexes and job isolation |
| `frappe.only_for`, `check_permission`, `has_permission`, `whitelist` | Server access checks |
| `getdate/get_datetime/now_datetime/get_system_timezone/flt` | Native date and money conventions |
| `frappe.log_error/get_traceback` | Operational diagnostics |
| Standard DocType/Report/Workspace JSON sync | App-owned metadata, no manually created reports or workflows |

Frappe's private `_get_extended_class` is inspected only by the compatibility check. Source-level APIs are version-sensitive even within v16; run the native tests after any core upgrade. No core methods are monkey-patched and no `override_doctype_class` replaces HRMS controllers.

## Tests and release checks

Local verification on 2026-09-14: **28 standalone tests passed** (24 policy/timezone cases and 4 metadata/hook checks); Ruff lint/format, Python compilation, JavaScript syntax, reference-source contracts and DocType JSON validation passed. Source archive and wheel were built and checked for required app assets and absence of reference checkouts/local runtime files. **Database-backed site tests: not run — no installed Frappe/HRMS environment available.**

Framework-free checks:

```bash
python -m unittest reckon_hr_policy.tests.test_policy reckon_hr_policy.tests.test_metadata -v
python -m compileall -q reckon_hr_policy tools
ruff check reckon_hr_policy tools
ruff format --check reckon_hr_policy tools
python -m build
python tools/verify_artifacts.py
```

Optional source check after placing the inspected official checkouts in `.reference/{frappe,erpnext,hrms}`:

```bash
python tools/verify_source_contract.py .reference
```

**On a disposable test site only** (tests use HRMS fixtures and payroll records):

```bash
bench --site <test-site> set-config allow_tests true
bench --site <test-site> run-tests --app reckon_hr_policy
bench --site <test-site> execute reckon_hr_policy.setup.install.setup
bench --site <test-site> migrate
bench --site <test-site> migrate
bench --site <test-site> run-tests --app reckon_hr_policy
```

Site tests cover the installed API contract, setup idempotence, settings permissions, Saturday configuration, repeated slip save, snapshot submission/immutability and repeated automatic checkout. They have **not been executed in this workspace**. The exact installation may reveal additional integration adjustments. Also run HRMS's native Salary Slip, Salary Structure Assignment, Employee Checkin, Shift Type and Payroll Entry test suites and an organization's tax/accounting regression pack. Test concurrent real OUT ingestion versus checkout, Timesheet payroll consumption, custom role permissions, non-default currency and a large checkin dataset on staging.

## Sample acceptance data (not inserted during installation)

Use a disposable employee named **RHP Monthly Example**, in an existing test company and its currency. Set Monthly, Standard, monthly base **600**, effective **2026-09-01**, and set central policy effective date to that payroll boundary. Choose September 2026. With only Sundays excluded and HRMS excluding holidays from total working days, there are **26 working days** for this particular month; the app calculates the denominator, it does not fix it at 26.

Submit native Attendance giving **7 late dates**, **4 early dates**, and valid within-shift checkins giving **5 breaks over 30 minutes**. Supply eight separate shifts with 30 early minutes and complete OUT pairs (240 minutes total). Ensure none of the events falls on a holiday and actual payment days are 26.

| Item | Expected result |
|---|---:|
| Daily rate | 600 / 26 = 23.076923… |
| Late days / amount | 2 / 46.15 |
| Early days / amount | 1 / 23.08 |
| Break days / amount | 1 / 23.08 |
| Total policy days / deductions | 4 / 92.31 |
| Daily allowance | 26 × 2 = 52.00 |
| Early-entry OT | 8 blocks × 1 = 8.00 |
| Gross (no other earnings) | 660.00 |
| Net before taxes/loans/other native deductions | 567.69 |

These monetary expectations assume currency precision 2. The brief's 92.32 example rounds daily rate to 23.08 first; this implementation retains the exact rate and rounds each final component, yielding **92.31**. If HRMS reports different working/payment days, expected amounts must change accordingly.

For **RHP Hourly Example**, choose Hourly, No Attendance Deduction, rate **5**, and an appropriate effective date. Submit approved native Timesheets totaling **160 hours**. Native wages should be **800**, with no policy late/early/break deduction, daily allowance or policy overtime. Native tax/other configured deductions may still apply.

For checkout, create one terminal IN more than 24 elapsed hours ago on an active test employee. Run the hourly method twice. There must be exactly one linked synthetic OUT, with `skip_auto_attendance=1`, at IN + 24 hours and an explanatory reason.

## Upgrade

Back up database/files and record app/core commits. Restore to staging, update the app through your normal Git/Bench workflow, run compatibility checks, migrate twice and run the test suite. Review Settings setup status and Error Log. Only after acceptance update production, migrate and restart workers. Existing settings and unrelated records are preserved; submitted snapshots remain unchanged. Do not downgrade past a schema/integration change without restoring a tested backup.

## Disable and uninstall

Turning Enabled off stops new policy calculations and app jobs; recalculated drafts lose policy rows. It does not undo native submitted payroll, already assigned shifts, holiday lists, structures, or accounting entries. Existing managed Shift Type auto attendance is native and can continue; review schedules before discontinuing the app.

Uninstall is blocked when attendance summaries exist to avoid losing payroll evidence. Retain a disabled app or archive the complete site. On a disposable installation without snapshots, Bench uninstall removes app DocTypes and may remove associated custom fields; native masters created by the app and changes to Employee default shifts are not automatically rolled back. Export and review these first. No broad delete routine is provided. Verify native master references and backup recovery before removing code.

## Assumptions, unavoidable setup, and remaining acceptance work

- This release targets the inspected versions, not all historical HRMS v16 releases. The exact installed environment was unavailable.
- Policy is site-wide. Account mappings are company-specific; amount settings represent units of each slip's currency rather than FX-converted base currency amounts.
- Regular/Saturday end times, native absent/half-day thresholds and shift buffers were unspecified; documented defaults require review.
- Existing employment, shift, holiday and salary assignments take priority. The app does not silently replace an organization's roster or compensation scheme. Employees with unrelated assignments may need deliberate native reassignment by HR.
- Saving new policy rules updates app-owned shifts, but HRMS may block time changes while unprocessed checkins exist. Process those records before changing shifts. Existing dated shift assignments are not cancelled when automatic provisioning is disabled.
- Weekly-off changes update future dates in app-owned holiday lists while preserving earlier dates and manually added nonweekly holidays. Existing external holiday assignments remain authoritative for native attendance/payment days. Review payroll when changing calendars.
- Company financial accounts and statutory tax slabs/components cannot be inferred safely. Existing native Company defaults are reused, or HR chooses actual account overrides in the central Settings table. Country-specific payroll compliance requires organizational configuration and verification.
- No custom Workflow is required: native permissions/submission operate normally. Adding an approval workflow is an organizational choice, not a prerequisite for installing the app.
- The app does not fabricate missing Attendance, Timesheets, salaries, or device synchronization completeness. Native operational recording/approval still applies.
- Report preview uses current defaults; authoritative historical evidence is the submitted snapshot. Central policy changes are not retroactively versioned for old drafts.
- Negative net pay, multi-shift interactions, payroll corrections, tax annualization, concurrency and production-scale throughput require host integration acceptance. Framework-free tests are not enough.

## Final verification checklist

- [ ] Confirm actual installed Frappe/ERPNext/HRMS versions and run compatibility check.
- [ ] Install on a staging copy without manual custom fields/components/structures/jobs/reports.
- [ ] Run setup twice and migration twice with unchanged managed record counts.
- [ ] Review all policy defaults, effective date and company account/tax configuration.
- [ ] Confirm Employee default shift and dated Saturday assignment; holiday precedence is correct.
- [ ] Confirm native sync watermark, scheduler and workers; test delayed punch ingestion.
- [ ] Pass threshold, break, OT, hourly, Sunday, Saturday and timezone tests.
- [ ] Pass repeated-save payroll and snapshot immutability tests on the actual site.
- [ ] Compare native payment/working days, LWP, joining/leaving dates and currency rounding.
- [ ] Validate native Timesheet wages and absence of policy deductions for Hourly/exempt employees.
- [ ] Race real OUT ingestion against scheduled closure; one OUT maximum, no paid synthetic hours.
- [ ] Verify restricted users cannot change policy or see other companies' restricted data.
- [ ] Verify native tax, regional deductions, employer contributions, loans, YTD and accounting entries.
- [ ] Benchmark representative payroll/checkin volume and inspect query plans/job duration.
- [ ] Demonstrate backup/restore and cancel/amend payroll audit retention.
- [ ] Record actual site test logs and responsible HR/payroll approval before production certification.
