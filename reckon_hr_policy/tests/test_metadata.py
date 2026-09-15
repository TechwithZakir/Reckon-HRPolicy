"""Packaging-level checks runnable without a Frappe database."""

import ast
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestMetadata(unittest.TestCase):
    def test_homepage_reports_precede_payroll(self):
        path = ROOT / "reckon_hr_policy/workspace/reckon_hr_policy/reckon_hr_policy.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        targets = [row["link_to"] for row in doc["shortcuts"]]
        self.assertLess(
            targets.index("Reckon HR Policy Effectiveness Report"), targets.index("Payroll Entry")
        )
        for doctype in (
            "Employee Grade",
            "Salary Component",
            "Salary Structure",
            "Salary Structure Assignment",
            "Shift Type",
            "Shift Assignment",
            "Holiday List",
            "Holiday List Assignment",
            "Employee Checkin",
            "Attendance",
            "Salary Slip",
            "Reckon HR Attendance Summary",
        ):
            self.assertIn(doctype, targets)

    def test_hooks_resolve_to_python_files_and_symbols(self):
        from reckon_hr_policy import hooks

        targets = [
            hooks.before_install,
            hooks.before_migrate,
            hooks.after_install,
            hooks.after_migrate,
            hooks.before_uninstall,
        ]
        targets += [value for values in hooks.extend_doctype_class.values() for value in values]
        targets += [value for events in hooks.doc_events.values() for value in events.values()]
        targets += [value for values in hooks.scheduler_events.values() for value in values]
        for path in targets:
            with self.subTest(path=path):
                module, symbol = path.rsplit(".", 1)
                file = ROOT.parent / (module.replace(".", "/") + ".py")
                tree = ast.parse(file.read_text(encoding="utf-8"))
                self.assertIn(symbol, {getattr(node, "name", None) for node in tree.body})

    def test_settings_and_snapshot_roles(self):
        for slug in ("reckon_hr_policy_settings", "reckon_hr_attendance_summary"):
            data = json.loads((ROOT / "reckon_hr_policy/doctype" / slug / f"{slug}.json").read_text())
            self.assertEqual({p["role"] for p in data["permissions"]}, {"System Manager", "HR Manager"})
            if slug.endswith("summary"):
                self.assertTrue(all(not p.get("write") and not p.get("create") for p in data["permissions"]))

    def test_all_rule_fields_are_configurable(self):
        from reckon_hr_policy.policy import Rules

        path = ROOT / "reckon_hr_policy/doctype/reckon_hr_policy_settings/reckon_hr_policy_settings.json"
        fields = {f["fieldname"]: f for f in json.loads(path.read_text())["fields"]}
        for name, value in Rules().as_dict().items():
            with self.subTest(name=name):
                self.assertIn(name, fields)
                self.assertEqual(float(fields[name]["default"]), float(value))

    def test_doctype_controller_names(self):
        for path in (ROOT / "reckon_hr_policy/doctype").rglob("*.json"):
            data = json.loads(path.read_text())
            controller = ast.parse(path.with_suffix(".py").read_text())
            expected = data["name"].replace(" ", "").replace("-", "")
            self.assertIn(expected, {getattr(node, "name", None) for node in controller.body})
