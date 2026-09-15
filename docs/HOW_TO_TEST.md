# How to test Reckon HR Policy before salary processing

[Back to README](../README.md)

Use **Employee Checkin → Attendance → Policy Effectiveness Report → Draft Salary Slip**. You can verify event counts and policy deduction days before generating payroll. Final currency amounts, taxes and payment days require a draft native Salary Slip. Use a staging site/test employee for artificial attendance data.

## Install this report update

Update the app files on the bench using your normal repository deployment process, then run:

```bash
bench --site <site> migrate
bench build --app reckon_hr_policy
bench --site <site> clear-cache
bench restart
```

Reload Desk. Search **Reckon HR Policy Effectiveness Report**, or open **Reckon HR Policy → Policy Effectiveness**. HR Manager or System Manager access is required. No manual Report creation is necessary. Running migrate also repeats the app's idempotent setup; review its status and Error Log.

## 1. Confirm policy and employee setup

In **Reckon HR Policy Settings**, check Enabled, attendance deduction, late/early/break flags and Policy Effective From. Put the effective date on a payroll boundary; a crossing Salary Slip is blocked. Review regular and Saturday shift times.

For a monthly test employee:

- RHP Payroll Type: Monthly.
- RHP Attendance Policy: Standard.
- Default Shift: RHP Regular, or the native shift intended for the employee.
- Applicable Saturday Shift Assignment: RHP Saturday, normally created automatically for future Saturdays.
- Actual salary amount and Salary Effective From: entered, with a submitted Salary Structure Assignment covering the payroll start or joining date.

Use past test dates on/after policy/employee joining dates. For backdated Saturdays, inspect the native assignment explicitly: the automatic provisioning horizon starts today; it does not backfill historical schedules.

## 2. Enter controlled checkins

Examples assume regular shift **08:30–17:30**, 30-minute grace, and a non-holiday date:

| Test | IN/OUT sequence | Expected |
|---|---|---|
| On time | IN 08:30 → OUT 17:30 | No late or early flag |
| Grace boundary | IN 09:00 → OUT 17:30 | Not late |
| Late | IN 09:01 → OUT 17:30 | Late Entry checked |
| Early boundary | IN 08:30 → OUT 17:00 | Not early |
| Early exit | IN 08:30 → OUT 16:59 | Early Exit checked |
| Allowed break | IN 08:30 → OUT 12:00 → IN 12:30 → OUT 17:30 | No break violation |
| Excessive break | IN 08:30 → OUT 12:00 → IN 12:31 → OUT 17:30 | One break violation |
| Early overtime | IN 08:00 → OUT 17:30 | 30 minutes, one block, one slip-currency unit |
| Partial block | IN 07:31 → OUT 17:30 | 59 minutes, one block |

On Employee Checkin, check explicit IN/OUT directions, Shift, Shift Start and Shift End. Ordinary test punches must not have Skip Auto Attendance or Offshift enabled. Duplicate timestamps, repeated INs, missing final OUTs, and blank log types invalidate a shift for break/OT calculations.

For Saturday's 10:00 start, 10:30 is within grace and 10:31 is late. Sunday/other applicable holidays are excluded from extra policy penalties. Use separate dates for threshold tests so multiple late punches on one date are not mistaken for multiple late dates.

## 3. Generate and inspect native Attendance

Open the applicable **Shift Type**:

1. Enable Auto Attendance must be enabled.
2. Process Attendance After must include your test dates.
3. Finish importing all checkins for those dates.
4. Last Sync of Checkin must be later than the shift's actual end, including its checkout buffer. With 17:30 end and 60-minute buffer, the watermark must be later than 18:30 for that date.
5. Run **Process Auto Attendance**, or allow the native scheduled processing to run.

Do not advance the sync watermark before delayed biometric punches have arrived. With a real-time feed, the central Auto Update Last Sync setting can use native HRMS updates; delayed ingestion should supply a reliable watermark through its device integration.

Open **Attendance**, filter by employee and dates, and verify submitted records, status, Late Entry and Early Exit. The policy late/early calculation excludes draft and cancelled Attendance. Break/OT calculations read valid checkins, so those numbers can exist before Attendance has been submitted; the report will warn about missing submitted Attendance.

## 4. Open the employee-wise effectiveness report

Search **Reckon HR Policy Effectiveness Report**. Set Company, Employee or Department/Branch, From Date and To Date. Optionally filter Payroll Type, Attendance Policy or Readiness.

The report shows:

- **Policy Effectiveness:** Active, Disabled, Not yet effective, Effective date conflict, Hourly exemption, or attendance-deduction exemption.
- **Readiness:** Action required for a missing salary assignment/effective-date conflict; Review for detected data gaps; Preview available when the available checks permit a preview. This is not a full validation of payroll, tax, financial accounts or all missing workdays.
- **Attendance:** distinct submitted dates, draft record count, submitted Absent, Half Day and On Leave dates. These status counts can overlap for multiple shifts and are not summed as a payroll denominator. They include submitted holiday statuses for inspection; native payroll decides whether to charge them.
- **Policy breakdown:** late/early dates, excessive breaks, deduction days per rule, total policy days, early OT minutes/blocks, OT currency preview, allowance rule, invalid/excluded shift counts.
- **Salary Assignment:** the submitted assignment at the selected start (or joining date). Its saved category overrides today's employee category. If the assignment changes inside the period, Smart Help requires a split and the preview uses the starting assignment only.
- **Smart Help:** click the row button for employee-specific guidance and links to Attendance and Employee. The text column is also available in exports. A **How to Test** toolbar button provides a short checklist.

Smart Help is deterministic guidance based on the app's checks. It does not send messages, contact a helpdesk, use an AI service, edit Attendance, or submit payroll. Unassigned/offshift punches with no native shift timestamps cannot be attributed to a shift and are not included in the invalid-shift count; inspect Employee Checkin if counts are unexpectedly empty.

The report applies the current central rules and explicitly shows the effective-date gate. Earlier source counts may remain visible while applicable deduction days/OT amounts are zero. Submitted Salary Slip snapshots remain the authoritative historical result. The older **Reckon HR Attendance Policy Report** remains available as a simpler live event report.

## 5. Verify thresholds

| Submitted/valid events | Expected default result |
|---|---|
| 2 late dates | 0 late deduction days |
| 3 late dates | 1 late deduction day |
| 6 late dates | 2 late deduction days |
| 3 early dates | 1 early deduction day |
| 3 breaks over 30 minutes | 1 break deduction day |
| 3 late + 3 early + 3 excessive breaks | 3 total extra policy deduction days |
| Hourly or No Attendance Deduction | 0 late/early/break deduction days |

Hourly payroll also receives no policy allowance/OT; its wages use approved native Timesheets. No Attendance Deduction monthly employees can still receive enabled allowance/OT.

## 6. Verify absences separately from extra penalties

The effectiveness report's **Absent Dates** shows submitted Absent Attendance dates. You can also filter the Attendance list by Employee, Date range, Status = Absent and Docstatus = Submitted.

Open **Payroll Settings** and review:

- **Payroll Based On = Attendance** if submitted absences should reduce payment days.
- **Consider Unmarked Attendance As**: missing Attendance and a submitted Absent record are different. Choosing Absent can reduce pay for dates whose records have not been processed yet.
- Holiday inclusion and half-day settings: these determine native payroll effects.

An Absent date is not an extra `RHP Absent Deduction` component. Native payroll reduces Payment Days and prorates payment-day-dependent earnings. The report does not guess unmarked working days or the financial effect of absence; a draft Salary Slip is the verification point. An unfinished month includes future dates, so avoid interpreting that preview as final payroll approval.

## 7. Verify one draft Salary Slip

Create/save a draft for the intended employee/period. Check:

1. Total Working Days, Absent Days, Leave Without Pay and Payment Days.
2. Basic Salary's native proration.
3. Separate RHP Late, Early Exit and Break Deduction components.
4. RHP Daily Allowance and Policy Overtime.
5. RHP Calculation JSON: assignment, rules, counts, source evidence, daily-rate numerator/denominator and native totals.
6. Save again: no duplicate policy components and no unexplained amount changes.

Keep it **Draft** during this test. The immutable Attendance Summary is created only on submission. For a full month with 26 actual working/payment days and base 600, seven late dates, four early dates and five excessive breaks produce amounts 46.15 + 23.08 + 23.08 = 92.31 at precision 2. The rate is not rounded before final components. See the [README example](../README.md#sample-acceptance-data-not-inserted-during-installation) for allowance/OT and hourly scenarios.

## Troubleshooting

| Observation | Next check |
|---|---|
| Late checkins but zero late count | Submitted Attendance Late Entry flag, employee/date filters, grace boundary, holiday status |
| Checkins exist but no Attendance | Native shift assignment/timestamps, Process Attendance After, completed sync watermark, auto-attendance job |
| Break is 31 minutes but zero violations | Strict IN/OUT sequence, complete shift, same-day within-shift break, skipped/synthetic punches |
| Late count exists but zero deduction days | Threshold not reached, policy disabled, hourly/exempt category, effective date |
| Absent records but salary does not reduce | Payroll Based On, native holiday settings, payment-day-dependent earnings, draft slip Payment Days |
| Report category differs from Employee | Starting dated salary assignment preserves the earlier policy category |
| No Salary Assignment | Enter actual salary/rate and effective date; save Employee; inspect setup status and Error Log for preserved existing assignments or native errors |
| Smart Help says split period | Assignment changes or central policy effective date occurs inside the selected period |
| Automatic OUT does not create paid hours | Intentional: synthetic OUT is skipped from auto attendance/payroll; HR must review the incomplete source shift |
| New report not visible | App code deployed, migrate completed, clear cache/reload, HR Manager/System Manager role |

## Acceptance evidence

Record the site/core/app versions, settings values, test employee, dates, relevant Attendance/Checkin IDs, report export, and draft-slip results. Run the [automated site tests](../README.md#tests-and-release-checks) on a disposable test site. Confirm actual database-backed tests before declaring production readiness; standalone local tests do not establish that the installed site's integration works.
