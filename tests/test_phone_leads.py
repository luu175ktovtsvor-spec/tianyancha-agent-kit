import argparse
import json
from pathlib import Path

import openpyxl

from tyc_agent.cli import build_parser, main


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_phone_leads_splits_individual_and_enterprise_and_requires_phone(tmp_path, capsys):
    root = _root()
    exit_code = main([
        "phone-leads",
        "--profile", str(root / "examples" / "industry-profile.example.yaml"),
        "--input", str(root / "examples" / "authorized-results.example.json"),
        "--format", "csv",
        "--output-dir", str(tmp_path),
    ])
    summary = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert summary["accepted"] == 2
    assert summary["accepted_by_entity"] == {"enterprise": 1, "individual_business": 1}
    assert summary["reason_counts"] == {
        "entity_class.other": 1,
        "negative_terms": 1,
        "phone_count": 1,
    }
    assert summary["min_phone_count"] == 1
    assert (tmp_path / "individual_business_phone_leads.csv").exists()
    assert (tmp_path / "enterprise_phone_leads.csv").exists()
    assert (tmp_path / "all_phone_leads.csv").exists()
    assert (tmp_path / "rejected_phone_leads.json").exists()
    header = (tmp_path / "all_phone_leads.csv").read_text(encoding="utf-8-sig").splitlines()[0]
    assert "entity_class" in header and "phone_count" in header and "phone_1" in header


def test_one_phone_enterprise_is_accepted(tmp_path, capsys):
    root = _root()
    records = json.loads((root / "examples" / "authorized-results.example.json").read_text(encoding="utf-8"))
    enterprise = next(record for record in records if record["id"] == "demo-002")
    enterprise["phoneList"] = ["000-0000-0001"]
    source = tmp_path / "one-phone-enterprise.json"
    source.write_text(json.dumps([enterprise], ensure_ascii=False), encoding="utf-8")
    exit_code = main([
        "phone-leads",
        "--profile", str(root / "examples" / "industry-profile.example.yaml"),
        "--input", str(source),
        "--output-dir", str(tmp_path / "output"),
    ])
    summary = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert summary["accepted"] == 1
    assert summary["accepted_by_entity"] == {"enterprise": 1, "individual_business": 0}
    assert summary["min_phone_count"] == 1


def test_phone_leads_xlsx_has_dynamic_phone_columns(tmp_path, capsys):
    root = _root()
    exit_code = main([
        "phone-leads",
        "--profile", str(root / "examples" / "industry-profile.example.yaml"),
        "--input", str(root / "examples" / "authorized-results.example.json"),
        "--format", "xlsx",
        "--output-dir", str(tmp_path),
    ])
    capsys.readouterr()
    assert exit_code == 0
    workbook = openpyxl.load_workbook(tmp_path / "all_phone_leads.xlsx", read_only=True, data_only=True)
    header = [cell.value for cell in next(workbook.active.iter_rows(max_row=1))]
    assert "phone_1" in header and "phone_2" in header and "phone_3" not in header
    assert "entity_class" in header and "phone_count" in header


def test_cli_exposes_complete_workflow_commands():
    parser = build_parser()
    action = next(item for item in parser._actions if isinstance(item, argparse._SubParsersAction))
    assert set(action.choices) == {"audit-public", "browser-collect", "normalize", "phone-leads", "run", "validate"}
