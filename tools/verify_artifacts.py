"""Verify distributable app assets and that local reference/runtime files are excluded."""

import tarfile
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
dist = root / "dist"
wheel = next(dist.glob("reckon_hr_policy-*.whl"))
sdist = next(dist.glob("reckon_hr_policy-*.tar.gz"))
required = [
    "reckon_hr_policy/hooks.py",
    "reckon_hr_policy/modules.txt",
    "reckon_hr_policy/patches.txt",
    "reckon_hr_policy/setup/install.py",
    "reckon_hr_policy/payroll/salary_slip.py",
    "reckon_hr_policy/reckon_hr_policy/doctype/reckon_hr_policy_settings/reckon_hr_policy_settings.json",
    "reckon_hr_policy/reckon_hr_policy/doctype/reckon_hr_attendance_summary/reckon_hr_attendance_summary.json",
    "reckon_hr_policy/reckon_hr_policy/report/reckon_hr_attendance_policy_report/reckon_hr_attendance_policy_report.js",
    "reckon_hr_policy/reckon_hr_policy/workspace/reckon_hr_policy/reckon_hr_policy.json",
]
with zipfile.ZipFile(wheel) as archive:
    names = archive.namelist()
    assert all(path in names for path in required)
    assert not any(".reference/" in path or ".venv/" in path or "__pycache__/" in path for path in names)
with tarfile.open(sdist) as archive:
    names = ["/".join(name.split("/")[1:]) for name in archive.getnames()]
    assert all(
        path in names
        for path in required + ["README.md", "pyproject.toml", "tools/verify_source_contract.py", "COPYING"]
    )
print("Wheel and source archive content: PASS")
