"""A JSON-speaking CLI for turning company data into acquisition leads."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .browser_automation import BrowserAutomationError, collect_browser_records, load_browser_profile
from .exporters import export_phone_leads, export_records
from .normalize import normalize_tianyancha_records, record_from_dict
from .privacy import PrivacyPathError, audit_public_tree, require_private_path
from .profile import ProfileError, load_profile
from .rules import build_phone_leads, filter_records


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _record_list(value: Any, shape: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError(f"{shape} must contain only JSON objects")
    return list(value)


def _read_json(path: str) -> list[dict[str, Any]]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read JSON input: {exc}") from exc
    if isinstance(data, list):
        return _record_list(data, "JSON list")
    if isinstance(data, dict):
        nested = data.get("data")
        if isinstance(nested, dict) and isinstance(nested.get("companyList"), list):
            return _record_list(nested["companyList"], "data.companyList")
        if isinstance(data.get("records"), list):
            return _record_list(data["records"], "records")
    raise ValueError("input must be a JSON list, {records: [...]}, or {data: {companyList: [...]}}")


def _load_records(path: str, input_kind: str):
    items = _read_json(path)
    if input_kind == "tianyancha":
        return normalize_tianyancha_records(items)
    return [record_from_dict(item) for item in items]


def _write_json(path: str, payload: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def command_validate(args: argparse.Namespace) -> int:
    profile = load_profile(args.profile)
    _emit({
        "ok": True,
        "profile": profile.name,
        "positive_term_count": len(profile.positive_terms),
        "negative_term_count": len(profile.negative_terms),
        "entity_classes": [entity_class.key for entity_class in profile.entity_classes],
        "target_entity_classes": profile.target_entity_classes,
        "min_phone_count": profile.min_phone_count,
    })
    return 0


def command_run(args: argparse.Namespace) -> int:
    profile = load_profile(args.profile)
    records = _load_records(args.input, args.input_kind)
    output = require_private_path(args.output, "research output")
    result = filter_records(records, profile)
    destination = export_records(result.accepted, output, args.format, profile.export_redactions)
    if args.rejected:
        _write_json(str(require_private_path(args.rejected, "rejection audit")), result.rejected)
    _emit({
        "ok": True,
        "profile": profile.name,
        "input_records": len(records),
        "accepted": len(result.accepted),
        "rejected": len(result.rejected),
        "reason_counts": result.reason_counts,
        "output": str(destination),
        "redacted_fields": profile.export_redactions,
    })
    return 0


def command_normalize(args: argparse.Namespace) -> int:
    records = normalize_tianyancha_records(_read_json(args.input))
    output = require_private_path(args.output, "normalized results")
    _write_json(str(output), [record.to_dict() for record in records])
    _emit({"ok": True, "normalized": len(records), "output": str(output)})
    return 0


def command_browser_collect(args: argparse.Namespace) -> int:
    profile = load_browser_profile(args.browser_profile)
    output = require_private_path(args.output, "browser collection output")
    records = collect_browser_records(profile, confirm_ready=args.ready, headless=args.headless)
    _write_json(str(output), records)
    _emit({"ok": True, "records": len(records), "output": str(output), "input_kind": "canonical"})
    return 0


def _process_phone_leads(profile, records, output_dir: str, fmt: str, rejected: str | None) -> int:
    leads = build_phone_leads(records, profile)
    for entity_class in profile.target_entity_classes:
        leads.leads_by_entity.setdefault(entity_class, [])
    outputs = export_phone_leads(leads.leads_by_entity, output_dir, fmt, profile.export_redactions)
    rejected_path = Path(rejected) if rejected else Path(output_dir) / "rejected_phone_leads.json"
    _write_json(str(rejected_path), leads.rejected)
    _emit({
        "ok": True,
        "profile": profile.name,
        "input_records": len(records),
        "accepted": leads.accepted_count,
        "accepted_by_entity": {key: len(value) for key, value in leads.leads_by_entity.items()},
        "rejected": len(leads.rejected),
        "reason_counts": leads.reason_counts,
        "min_phone_count": max(profile.min_phone_count, 1),
        "outputs": {key: str(value) for key, value in outputs.items()},
        "rejected_output": str(rejected_path),
        "redacted_fields": profile.export_redactions,
    })
    return 0


def command_phone_leads(args: argparse.Namespace) -> int:
    profile = load_profile(args.profile)
    records = _load_records(args.input, args.input_kind)
    output_dir = require_private_path(args.output_dir, "phone-lead output")
    rejected = str(require_private_path(args.rejected, "rejection audit")) if args.rejected else None
    return _process_phone_leads(profile, records, str(output_dir), args.format, rejected)


def command_audit(args: argparse.Namespace) -> int:
    findings = audit_public_tree(args.path)
    _emit({"ok": not findings, "path": str(Path(args.path).resolve()), "findings": findings})
    return 0 if not findings else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tyc-agent",
        description="Turn company data into configurable acquisition leads.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    validate = subcommands.add_parser("validate", help="Validate an industry profile")
    validate.add_argument("--profile", required=True)
    validate.set_defaults(func=command_validate)

    normalize = subcommands.add_parser("normalize", help="Normalize a Tianyancha JSON response")
    normalize.add_argument("--input", required=True)
    normalize.add_argument("--output", required=True)
    normalize.set_defaults(func=command_normalize)

    browser_collect = subcommands.add_parser(
        "browser-collect",
        help="Use visible Playwright automation with an operator-supplied selector profile",
    )
    browser_collect.add_argument("--browser-profile", required=True, help="Private YAML file containing selectors and an HTTPS URL (or local demo URL)")
    browser_collect.add_argument("--output", required=True, help="Task-workspace canonical JSON output")
    browser_collect.add_argument("--ready", action="store_true", help="Capture immediately only when login and the result page are already ready")
    browser_collect.add_argument("--headless", action="store_true", help="Run headless mode for local demo URLs only")
    browser_collect.set_defaults(func=command_browser_collect)

    phone_leads = subcommands.add_parser("phone-leads", help="Filter phone-bearing records into individual/enterprise acquisition leads")
    phone_leads.add_argument("--profile", required=True)
    phone_leads.add_argument("--input", required=True, help="JSON file")
    phone_leads.add_argument("--input-kind", choices=("tianyancha", "canonical"), default="tianyancha")
    phone_leads.add_argument("--output-dir", required=True, help="Task-workspace directory for acquisition-lead files")
    phone_leads.add_argument("--format", choices=("jsonl", "csv", "xlsx"), default="xlsx")
    phone_leads.add_argument("--rejected", help="Task-workspace JSON audit trail; defaults under --output-dir")
    phone_leads.set_defaults(func=command_phone_leads)

    run = subcommands.add_parser("run", help="Normalize, filter, and export a company-data file")
    run.add_argument("--profile", required=True)
    run.add_argument("--input", required=True, help="JSON file")
    run.add_argument("--input-kind", choices=("tianyancha", "canonical"), default="tianyancha")
    run.add_argument("--output", required=True)
    run.add_argument("--format", choices=("jsonl", "csv", "xlsx"), default="jsonl")
    run.add_argument("--rejected", help="Optional task-workspace audit trail for rejected records")
    run.set_defaults(func=command_run)

    audit = subcommands.add_parser("audit-public", help="Flag likely private files before sharing source code")
    audit.add_argument("--path", default=".")
    audit.set_defaults(func=command_audit)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (BrowserAutomationError, ProfileError, PrivacyPathError, ValueError) as exc:
        _emit({"ok": False, "error": str(exc)})
        return 1
    except KeyboardInterrupt:
        _emit({"ok": False, "error": "cancelled"})
        return 130


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
