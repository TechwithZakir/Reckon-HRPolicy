frappe.query_reports["Reckon HR Attendance Policy Report"] = {
    filters: [
        { fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company" },
        { fieldname: "employee", label: __("Employee"), fieldtype: "Link", options: "Employee" },
        { fieldname: "department", label: __("Department"), fieldtype: "Link", options: "Department" },
        { fieldname: "branch", label: __("Branch"), fieldtype: "Link", options: "Branch" },
        { fieldname: "payroll_period", label: __("Payroll Period"), fieldtype: "Link", options: "Payroll Period" },
        { fieldname: "from_date", label: __("From Date"), fieldtype: "Date", default: frappe.datetime.month_start() },
        { fieldname: "to_date", label: __("To Date"), fieldtype: "Date", default: frappe.datetime.month_end() },
        { fieldname: "payroll_type", label: __("Payroll Type"), fieldtype: "Select", options: "\nMonthly\nHourly" },
        { fieldname: "attendance_policy", label: __("Attendance Policy"), fieldtype: "Select", options: "\nStandard\nNo Attendance Deduction" }
    ]
};
