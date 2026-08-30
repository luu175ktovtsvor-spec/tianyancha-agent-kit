"""Privacy controls for exports and pre-publication checks."""

from __future__ import annotations

import re
from collections.abc import Iterable
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from .models import CompanyRecord

SENSITIVE_FILE_PATTERNS = (
    "storage_state*.json",
    "*cookie*.json",
    "*session*.json",
    "*state*.json",
    ".env",
    ".env.*",
    "*.xlsx",
    "*.csv",
    "*.tsv",
    "*.jsonl",
    "*.xls",
    "raw_authorized_results.json",
    "rejected_phone_leads.json",
    "browser-profile*.yaml",
    "area*.json",
    "areas*.json",
    "*result*.json",
    "*lead*.json",
    "credentials*.json",
    "*.bak",
    "*.db",
    "*.sqlite*",
    "*.har",
    "*.log",
)
SAFE_PUBLIC_PATHS = {
    "examples/authorized-results.example.json",
    "examples/browser-profile.example.yaml",
    "examples/browser-profile.demo.yaml",
}
SENSITIVE_TEXT_PATTERNS = {
    "authorization header": re.compile(r"authorization\s*[:=]\s*['\"](?:Bearer\s+)?[A-Za-z0-9._-]{12,}", re.IGNORECASE),
    "access token": re.compile(
        r"['\"]?(?:api[_-]?key|auth[_-]?token|access[_-]?token)['\"]?\s*[:=]\s*['\"][A-Za-z0-9._-]{12,}",
        re.IGNORECASE,
    ),
    "absolute home path": re.compile(r"/(?:Users|home)/[^/\s]+/", re.IGNORECASE),
    "absolute Windows home path": re.compile(r"[A-Za-z]:\\\\Users\\\\[^\\\s]+\\\\", re.IGNORECASE),
    "browser cookie store": re.compile(r"[\"']cookies[\"']\s*:\s*\[", re.IGNORECASE),
    "Chinese mobile phone number": re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    "Chinese landline phone number": re.compile(r"(?<!\d)0\d{2,3}-?\d{7,8}(?!\d)"),
    "Chinese unified social credit code": re.compile(r"(?<![0-9A-Z])[159Y][1239][0-9A-Z]{16}(?![0-9A-Z])"),
    "external workspace URL": re.compile(
        r"https?://(?!github\.com/larksuite/cli(?:/|[?#]|\b))[^\s\"']*(?:feishu|larksuite|larkoffice)[^\s\"']*",
        re.IGNORECASE,
    ),
}
IGNORED_AUDIT_DIRECTORIES = {".git", ".venv", "venv", "__pycache__"}
TEXT_AUDIT_SUFFIXES = {".py", ".md", ".txt", ".yml", ".yaml", ".toml", ".json", ".svg", ".html"}


class PrivacyPathError(ValueError):
    """Raised when a private runtime artifact would be written into source."""


def _public_source_root() -> Path | None:
    """Return this editable checkout's root, if the package is run from one.

    A Wheel installation has no source checkout to protect, so this deliberately
    returns ``None`` in that case. It prevents accidentally writing private
    inputs or real outputs into a clone that is later pushed.
    """

    module_path = Path(__file__).resolve()
    for candidate in (module_path.parent, *module_path.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def require_private_path(path: str | Path, purpose: str) -> Path:
    """Resolve a runtime path and reject locations inside this source checkout."""

    target = Path(path).expanduser().resolve()
    source_root = _public_source_root()
    if source_root is None:
        return target
    try:
        target.relative_to(source_root)
    except ValueError:
        return target
    raise PrivacyPathError(
        f"{purpose} must be outside the public source tree: {source_root}. "
        "Use a separate private run directory."
    )


def redact_record(record: CompanyRecord, fields: Iterable[str]) -> dict[str, Any]:
    """Return an export-safe copy; raw provider payload is never exported."""

    values = record.to_dict()
    values.pop("source", None)
    for field in fields:
        if field in values:
            values[field] = [] if field == "phones" else "[REDACTED]"
    return values


def _matches_sensitive_filename(name: str) -> str | None:
    for pattern in SENSITIVE_FILE_PATTERNS:
        if fnmatch(name, pattern):
            return pattern
    return None


def _is_safe_public_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized == ".env.example" or any(
        normalized == safe_path or normalized.endswith(f"/{safe_path}")
        for safe_path in SAFE_PUBLIC_PATHS
    )


def _text_findings(path: str, text: str) -> list[dict[str, str]]:
    return [
        {"path": path, "reason": label}
        for label, pattern in SENSITIVE_TEXT_PATTERNS.items()
        if pattern.search(text)
    ]


def audit_public_tree(root: str | Path) -> list[dict[str, str]]:
    """Find likely secrets and local outputs before a directory is published.

    It intentionally errs on the conservative side: findings require review,
    not automatic deletion.
    """

    base = Path(root).resolve()
    if not base.is_dir():
        raise ValueError(f"audit path must be an existing directory: {base}")
    findings: list[dict[str, str]] = []
    for path in base.rglob("*"):
        if not path.is_file() or any(part in IGNORED_AUDIT_DIRECTORIES for part in path.parts):
            continue
        relative_path = str(path.relative_to(base))
        pattern = _matches_sensitive_filename(path.name)
        if pattern and not _is_safe_public_path(relative_path):
            findings.append({"path": relative_path, "reason": f"sensitive filename pattern: {pattern}"})
        if path.suffix.lower() not in TEXT_AUDIT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            findings.append({"path": relative_path, "reason": "could not inspect text file"})
            continue
        findings.extend(_text_findings(relative_path, text))
    return sorted(findings, key=lambda item: (item["path"], item["reason"]))
