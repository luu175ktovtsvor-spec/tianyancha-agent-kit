"""Adapters that turn authorized provider results into canonical records."""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date
from typing import Any

from .models import CompanyRecord


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _strip_markup(value: Any) -> str:
    return re.sub(r"<[^>]+>", "", _text(value)).strip()


def _date(value: Any) -> str:
    text = _text(value)
    if len(text) == 8 and text.isdigit():
        candidate = f"{text[:4]}-{text[4:6]}-{text[6:]}"
    else:
        candidate = text[:10] if len(text) >= 10 else ""
    try:
        return date.fromisoformat(candidate).isoformat()
    except ValueError:
        return ""


def _integer(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _phones(value: Any) -> list[str]:
    if isinstance(value, str):
        values = re.split(r"[;,，；]+", value)
    elif isinstance(value, list):
        values = value
    else:
        return []
    return list(dict.fromkeys(_text(item) for item in values if _text(item)))


def normalize_tianyancha_record(raw: dict[str, Any]) -> CompanyRecord:
    """Map an authorized Tianyancha search-result object to ``CompanyRecord``.

    This adapter contains no authentication, request signing, anti-bot
    evasion, or embedded account data. Supply only data you are authorized to
    access and handle under the source's terms and applicable law.
    """

    categories = [_text(raw.get(f"categoryNameLv{i}")) for i in range(1, 5)]
    representative = next(
        (_strip_markup(raw.get(key)) for key in ("legalPersonName", "firstPositionValue", "legalPersonForList") if raw.get(key)),
        "",
    )
    return CompanyRecord(
        name=_strip_markup(raw.get("name") or raw.get("alias")),
        credit_code=_text(raw.get("creditCode") or raw.get("taxCode")),
        entity_type=_text(raw.get("orgType") or raw.get("companyType") or raw.get("type")),
        established_on=_date(raw.get("establishmentTime") or raw.get("estiblishTime")),
        status=_text(raw.get("regStatus")),
        province=_text(raw.get("provinceName")),
        city=_text(raw.get("cityName")),
        district=_text(raw.get("districtName")),
        address=_text(raw.get("regLocation")),
        representative=representative,
        phones=_phones(raw.get("phoneList")) or _phones(raw.get("phoneNum")),
        business_scope=_text(raw.get("businessScope")),
        categories=[item for item in categories if item],
        risk={
            "self": _integer(raw.get("selfRiskCount")),
            "related": _integer(raw.get("relatedRiskCount")),
            "history": _integer(raw.get("historyRiskCount")),
        },
        source_id=_text(raw.get("id")),
        source=dict(raw),
    )


def normalize_tianyancha_records(raw_records: Iterable[dict[str, Any]]) -> list[CompanyRecord]:
    return [normalize_tianyancha_record(record) for record in raw_records if isinstance(record, dict)]


def _canonical_text(data: dict[str, Any], field: str) -> str:
    value = data.get(field, "")
    if not isinstance(value, str):
        raise ValueError(f"canonical record.{field} must be a string")
    return value


def _canonical_strings(data: dict[str, Any], field: str) -> list[str]:
    value = data.get(field, [])
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"canonical record.{field} must be a list of strings")
    return list(dict.fromkeys(item for item in value if item))


def _canonical_risk(data: dict[str, Any]) -> dict[str, int]:
    value = data.get("risk", {})
    if not isinstance(value, dict) or any(
        not isinstance(key, str) or not isinstance(count, int) or isinstance(count, bool)
        for key, count in value.items()
    ):
        raise ValueError("canonical record.risk must map strings to integers")
    return dict(value)


def record_from_dict(data: dict[str, Any]) -> CompanyRecord:
    """Load a type-checked canonical record exported by this package."""

    if not isinstance(data, dict):
        raise ValueError("canonical record must be a JSON object")
    source = data.get("source", {})
    if not isinstance(source, dict):
        raise ValueError("canonical record.source must be a mapping")
    return CompanyRecord(
        name=_canonical_text(data, "name"),
        credit_code=_canonical_text(data, "credit_code"),
        entity_type=_canonical_text(data, "entity_type"),
        established_on=_canonical_text(data, "established_on"),
        status=_canonical_text(data, "status"),
        province=_canonical_text(data, "province"),
        city=_canonical_text(data, "city"),
        district=_canonical_text(data, "district"),
        address=_canonical_text(data, "address"),
        representative=_canonical_text(data, "representative"),
        phones=_canonical_strings(data, "phones"),
        business_scope=_canonical_text(data, "business_scope"),
        categories=_canonical_strings(data, "categories"),
        risk=_canonical_risk(data),
        source_id=_canonical_text(data, "source_id"),
        source=dict(source),
    )
