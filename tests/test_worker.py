import json
import os
import subprocess
import sys

from ifcchef import worker
from ifcchef.cleaner import CleanReport


def _run_worker(*args):
    completed = subprocess.run(
        [sys.executable, "-m", "ifcchef.worker", *map(str, args)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    lines = completed.stdout.splitlines()
    statuses = [
        line.removeprefix(worker.STATUS) for line in lines if line.startswith(worker.STATUS)
    ]
    result = json.loads(lines[-1].removeprefix(worker.RESULT))
    return completed.returncode, statuses, result


def test_worker_success(ifc_path, otl_path):
    code, statuses, result = _run_worker(ifc_path, otl_path)

    assert code == 0
    assert result["ok"]
    assert result["output"] == str(ifc_path.with_name("voorbeeld_bewerkt.ifc"))
    assert CleanReport.from_dict(result["report"]).removed_properties == 4
    assert any("opslaan" in s for s in statuses)


def test_worker_reports_existing_output(ifc_path, otl_path):
    _run_worker(ifc_path, otl_path)
    code, _, result = _run_worker(ifc_path, otl_path)

    assert code == 1
    assert not result["ok"]
    assert "bestaat al" in result["message"]


def test_worker_missing_file(tmp_path, otl_path):
    code, _, result = _run_worker(tmp_path / "geen.ifc", otl_path)

    assert code == 1
    assert not result["ok"]


def test_report_roundtrip(model, otl_path):
    from ifcchef.cleaner import clean_ils
    from ifcchef.otl import load_otl

    report = clean_ils(model, load_otl(otl_path))
    data = json.loads(json.dumps(report.to_dict()))
    assert CleanReport.from_dict(data) == report
