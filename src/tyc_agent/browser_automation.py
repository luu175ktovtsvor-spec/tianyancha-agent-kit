"""Visible, human-in-the-loop Playwright collection for authorized pages.

The public implementation deliberately uses declarative CSS selectors. It does
not contain source-specific endpoints, request signing, cookie/token export,
CAPTCHA handling, stealth measures, or access-control bypasses.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

from .models import CompanyRecord


class BrowserAutomationError(RuntimeError):
    """Raised when a visible, operator-authorized browser run cannot continue."""


CANONICAL_STRING_FIELDS = {
    "name",
    "credit_code",
    "entity_type",
    "established_on",
    "status",
    "province",
    "city",
    "district",
    "address",
    "representative",
    "business_scope",
    "source_id",
}
CANONICAL_LIST_FIELDS = {"phones", "categories"}
ALLOWED_FIELDS = CANONICAL_STRING_FIELDS | CANONICAL_LIST_FIELDS
RISK_KEYS = {"self", "related", "history"}


@dataclass(frozen=True)
class BrowserCollectionProfile:
    """Site-specific selectors supplied by the operator outside public code."""

    start_url: str
    item_selector: str
    fields: dict[str, str]
    risk_fields: dict[str, str]
    next_selector: str = ""
    max_pages: int = 1
    delay_seconds: float = 1.5


def _nonempty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BrowserAutomationError(f"{field} must be a non-empty string")
    return value.strip()


def _allowed_url(value: Any) -> str:
    url = _nonempty_string(value, "browser.start_url")
    parsed = urlparse(url)
    if parsed.scheme == "https" and parsed.hostname:
        return url
    if parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}:
        return url
    raise BrowserAutomationError("browser.start_url must be HTTPS, except for local HTTP demo URLs")


def _is_local_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}


def load_browser_profile(path: str | Path) -> BrowserCollectionProfile:
    """Load a declarative browser collection profile without executable code."""

    try:
        document = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    except OSError as exc:
        raise BrowserAutomationError(f"could not read browser profile: {exc}") from exc
    except yaml.YAMLError as exc:
        raise BrowserAutomationError(f"invalid browser profile YAML: {exc}") from exc
    if not isinstance(document, dict) or not isinstance(document.get("browser"), dict):
        raise BrowserAutomationError("browser profile must contain a browser mapping")
    browser = document["browser"]
    fields = browser.get("fields")
    if not isinstance(fields, dict) or not fields:
        raise BrowserAutomationError("browser.fields must be a non-empty mapping")
    normalized_fields: dict[str, str] = {}
    for key, selector in fields.items():
        if key not in ALLOWED_FIELDS:
            raise BrowserAutomationError(f"browser.fields contains unsupported field: {key}")
        normalized_fields[key] = _nonempty_string(selector, f"browser.fields.{key}")
    if "name" not in normalized_fields:
        raise BrowserAutomationError("browser.fields.name is required")
    risk = browser.get("risk", {})
    if not isinstance(risk, dict):
        raise BrowserAutomationError("browser.risk must be a mapping")
    risk_fields: dict[str, str] = {}
    for key, selector in risk.items():
        if key not in RISK_KEYS:
            raise BrowserAutomationError(f"browser.risk contains unsupported field: {key}")
        risk_fields[key] = _nonempty_string(selector, f"browser.risk.{key}")
    max_pages = browser.get("max_pages", 1)
    if not isinstance(max_pages, int) or isinstance(max_pages, bool) or max_pages < 1:
        raise BrowserAutomationError("browser.max_pages must be an integer >= 1")
    delay_seconds = browser.get("delay_seconds", 1.5)
    if not isinstance(delay_seconds, (int, float)) or isinstance(delay_seconds, bool) or delay_seconds < 0:
        raise BrowserAutomationError("browser.delay_seconds must be a number >= 0")
    return BrowserCollectionProfile(
        start_url=_allowed_url(browser.get("start_url")),
        item_selector=_nonempty_string(browser.get("item_selector"), "browser.item_selector"),
        fields=normalized_fields,
        risk_fields=risk_fields,
        next_selector=_nonempty_string(browser["next_selector"], "browser.next_selector") if browser.get("next_selector") else "",
        max_pages=max_pages,
        delay_seconds=float(delay_seconds),
    )


def _texts(item: Any, selector: str) -> list[str]:
    try:
        values = item.locator(selector).all_inner_texts()
    except Exception as exc:
        raise BrowserAutomationError(f"could not read selector {selector!r}: {exc}") from exc
    return [value.strip() for value in values if value and value.strip()]


def _list_values(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        result.extend(part.strip() for part in re.split(r"[;,，；\n]+", value) if part.strip())
    return list(dict.fromkeys(result))


def _date_value(value: str) -> str:
    matched = re.search(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", value)
    if not matched:
        return value
    try:
        return date(int(matched.group(1)), int(matched.group(2)), int(matched.group(3))).isoformat()
    except ValueError:
        return value


def _risk_value(values: list[str]) -> int:
    matched = re.search(r"\d+", " ".join(values))
    return int(matched.group()) if matched else 0


def extract_record(item: Any, fields: dict[str, str], risk_fields: dict[str, str] | None = None) -> dict[str, Any]:
    """Extract one canonical record from a result card using safe CSS selectors."""

    values: dict[str, Any] = {name: "" for name in CANONICAL_STRING_FIELDS}
    values.update({name: [] for name in CANONICAL_LIST_FIELDS})
    values["risk"] = {}
    for name, selector in fields.items():
        selected = _texts(item, selector)
        if name in CANONICAL_LIST_FIELDS:
            values[name] = _list_values(selected)
        elif name == "established_on":
            values[name] = _date_value(selected[0]) if selected else ""
        else:
            values[name] = selected[0] if selected else ""
    for key, selector in (risk_fields or {}).items():
        values["risk"][key] = _risk_value(_texts(item, selector))
    return CompanyRecord(**values).to_dict()


def _prompt_for_operator() -> None:
    print(
        "可见浏览器已打开。请在浏览器里完成扫码登录并进入目标结果页；"
        "准备好后按 Enter，让 Agent 按任务配置读取结果卡片。Ctrl-C 取消。",
        file=sys.stderr,
        flush=True,
    )
    input()


def collect_browser_records(
    profile: BrowserCollectionProfile,
    *,
    confirm_ready: bool = False,
    headless: bool = False,
) -> list[dict[str, Any]]:
    """Open a visible browser, wait for the operator to finish login, then collect configured records."""

    if not confirm_ready and not sys.stdin.isatty():
        raise BrowserAutomationError("browser collection requires an interactive terminal")
    if headless and not _is_local_url(profile.start_url):
        raise BrowserAutomationError("headless mode is limited to local demo URLs")
    try:
        from playwright.sync_api import Error as PlaywrightError, sync_playwright
    except ImportError as exc:  # pragma: no cover - optional runtime integration
        raise BrowserAutomationError("install browser support with: pip install -e '.[browser]'") from exc

    records: list[dict[str, Any]] = []
    try:
        with sync_playwright() as playwright:  # pragma: no cover - opens a visible browser
            browser = playwright.chromium.launch(headless=headless)
            context = browser.new_context()
            try:
                page = context.new_page()
                page.goto(profile.start_url, wait_until="domcontentloaded")
                if not confirm_ready:
                    _prompt_for_operator()
                page.wait_for_timeout(300)
                for page_number in range(profile.max_pages):
                    page.wait_for_selector(profile.item_selector)
                    items = page.locator(profile.item_selector).all()
                    records.extend(extract_record(item, profile.fields, profile.risk_fields) for item in items)
                    if not profile.next_selector or page_number + 1 >= profile.max_pages:
                        break
                    next_button = page.locator(profile.next_selector)
                    if not next_button.count() or next_button.first.is_disabled():
                        break
                    next_button.first.click()
                    page.wait_for_timeout(int(profile.delay_seconds * 1000))
            finally:
                context.close()
                browser.close()
    except PlaywrightError as exc:  # pragma: no cover - depends on local browser runtime
        raise BrowserAutomationError(f"browser automation failed: {exc}") from exc
    return records
