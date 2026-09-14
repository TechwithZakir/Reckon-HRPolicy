"""Read-only contract checks against exact local reference sources, without importing Frappe.

Usage: python tools/verify_source_contract.py .reference
This supplements, never replaces, installation and database-backed tests.
"""

import ast
import json
import sys
from pathlib import Path

source = Path(sys.argv[1] if len(sys.argv) > 1 else ".reference")
ROOT = Path(__file__).resolve().parents[1]


def method(app, path, cls, name, params):
    tree = ast.parse((source / app / app / path).read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls)
    func = next(n for n in node.body if isinstance(n, ast.FunctionDef) and n.name == name)
    assert set(params) <= {arg.arg for arg in func.args.args}, f"Signature mismatch: {cls}.{name}"


method(
    "hrms",
    "payroll/doctype/salary_slip/salary_slip.py",
    "SalarySlip",
    "calculate_net_pay",
    ["self", "skip_tax_breakup_computation"],
)
method(
    "hrms",
    "payroll/doctype/salary_slip/salary_slip.py",
    "SalarySlip",
    "calculate_component_amounts",
    ["self", "component_type"],
)
method(
    "hrms",
    "payroll/doctype/salary_slip/salary_slip.py",
    "SalarySlip",
    "update_component_row",
    ["component_data", "amount", "component_type", "default_amount"],
)
method(
    "hrms",
    "payroll/doctype/salary_structure_assignment/salary_structure_assignment.py",
    "SalaryStructureAssignment",
    "get_timesheet_config",
    ["self"],
)
method(
    "hrms",
    "hr/doctype/employee_checkin/employee_checkin.py",
    "EmployeeCheckin",
    "validate_distance_from_shift_location",
    ["self"],
)
base = (source / "frappe/frappe/model/base_document.py").read_text(encoding="utf-8")
assert 'get_hooks("extend_doctype_class"' in base
tree = ast.parse((ROOT / "reckon_hr_policy/setup/compatibility.py").read_text())
requirements = next(
    ast.literal_eval(n.value)
    for n in tree.body
    if isinstance(n, ast.Assign)
    and any(isinstance(t, ast.Name) and t.id == "REQUIRED_FIELDS" for t in n.targets)
)
schemas = {}
for app in ("frappe", "erpnext", "hrms"):
    for path in (source / app / app).rglob("*.json"):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeError):
            continue
        if isinstance(doc, dict) and doc.get("doctype") == "DocType":
            schemas[doc["name"]] = {f["fieldname"] for f in doc.get("fields", []) if "fieldname" in f}
# HRMS adds these via its install-time custom fields.
custom_source = (source / "hrms/hrms/setup.py").read_text(encoding="utf-8")
for dt, names in requirements.items():
    for name in names.split():
        assert name in schemas[dt] or name == "docstatus" or f'"{name}"' in custom_source, (
            f"Missing source field {dt}.{name}"
        )
for path in (ROOT / "reckon_hr_policy").rglob("*.json"):
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("doctype") == "DocType":
        names = [f["fieldname"] for f in doc["fields"]]
        assert len(names) == len(set(names))
        assert set(names) == set(doc["field_order"])
print("Source contracts, required fields and app JSON schemas: PASS")
