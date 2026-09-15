frappe.query_reports["Reckon HR Policy Effectiveness Report"] = {
    filters: [
        { fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company" },
        { fieldname: "employee", label: __("Employee"), fieldtype: "Link", options: "Employee" },
        { fieldname: "department", label: __("Department"), fieldtype: "Link", options: "Department" },
        { fieldname: "branch", label: __("Branch"), fieldtype: "Link", options: "Branch" },
        { fieldname: "from_date", label: __("From Date"), fieldtype: "Date", reqd: 1, default: frappe.datetime.month_start() },
        { fieldname: "to_date", label: __("To Date"), fieldtype: "Date", reqd: 1, default: frappe.datetime.month_end() },
        { fieldname: "payroll_type", label: __("Payroll Type"), fieldtype: "Select", options: "\nMonthly\nHourly" },
        { fieldname: "attendance_policy", label: __("Attendance Policy"), fieldtype: "Select", options: "\nStandard\nNo Attendance Deduction" },
        { fieldname: "readiness", label: __("Readiness"), fieldtype: "Select", options: "\nAction required\nReview\nPreview available" }
    ],
    formatter(value, row, column, data, default_formatter) {
        const esc = frappe.utils.escape_html;
        if (column.fieldname === "help_action" && data) {
            return `<button type="button" class="btn btn-xs btn-default rhp-smart-help" data-employee="${esc(data.employee)}">${__("Smart Help")}</button>`;
        }
        if (column.fieldname === "readiness" && data) {
            const colors = { "Action required": "red", "Review": "orange", "Preview available": "blue" };
            return `<span class="indicator-pill ${colors[value] || "gray"}">${esc(value || "")}</span>`;
        }
        return default_formatter(value, row, column, data);
    },
    onload(report) {
        report.page.add_inner_button(__("How to Test"), () => frappe.msgprint({
            title: __("Before Payroll: Test Sequence"),
            message: __("1. Review Policy Settings and employee assignment.<br>2. Import complete IN/OUT punches for past working dates.<br>3. Check Shift Type processing dates and sync watermark; process auto attendance.<br>4. Verify submitted Attendance late/early/absent flags.<br>5. Refresh this report and open employee Smart Help.<br>6. Save one draft Salary Slip to verify payable days and amounts. Keep it in Draft while testing.<br><br>Default late test: 08:30 shift, 30-minute grace; 09:01 IN is late. Three late dates produce one policy deduction day. Absences affect native Payment Days when Payroll Based On is Attendance.")
        }));
        report.page.wrapper.off("click.rhpHelp", ".rhp-smart-help").on("click.rhpHelp", ".rhp-smart-help", function () {
            const employee = $(this).attr("data-employee");
            const row = (report.data || []).find(item => item.employee === employee);
            if (!row) return;
            const esc = frappe.utils.escape_html;
            const dialog = new frappe.ui.Dialog({
                title: __("Employee Policy Help"),
                fields: [{ fieldname: "guidance", fieldtype: "HTML" }],
                primary_action_label: __("Open Attendance"),
                primary_action() {
                    dialog.hide();
                    frappe.set_route("List", "Attendance", {
                        employee,
                        attendance_date: ["between", [report.get_filter_value("from_date"), report.get_filter_value("to_date")]]
                    });
                },
                secondary_action_label: __("Open Employee"),
                secondary_action() { dialog.hide(); frappe.set_route("Form", "Employee", employee); }
            });
            dialog.fields_dict.guidance.$wrapper.html(
                `<p><strong>${esc(row.employee_name || employee)}</strong> — ${esc(row.policy_status)}</p>` +
                `<p>${esc(row.smart_help)}</p>` +
                `<ul>${[row.late_rule, row.early_rule, row.break_rule, row.allowance_rule].map(text => `<li>${esc(text || "")}</li>`).join("")}</ul>` +
                `<p>${__("Absences are handled through native payroll payment days. This report does not approve or submit payroll.")}</p>`
            );
            dialog.show();
        });
    }
};
