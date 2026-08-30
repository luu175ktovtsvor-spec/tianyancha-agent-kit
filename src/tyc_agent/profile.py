"""Profile loading and validation."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import yaml

from .models import CompanyRecord, EntityClass, IndustryProfile


class ProfileError(ValueError):
    """Raised when an industry profile is malformed or unsafe to interpret."""


def _string_list(value: Any, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ProfileError(f"{field_name} must be a list of strings")
    return [item.strip() for item in value if item.strip()]


def _default_entity_classes(individual_markers: list[str], company_markers: list[str]) -> list[EntityClass]:
    """Conservative defaults suitable for the acquisition-lead workflow.

    Users may replace this list when a source uses different entity labels.
    """

    enterprise_markers = list(dict.fromkeys([*company_markers, "企业", "合伙企业", "个人独资企业", "分公司"]))
    return [
        EntityClass("individual_business", "个体工商户", individual_markers),
        EntityClass("enterprise", "企业", enterprise_markers),
        EntityClass("other", "其他主体", [], fallback=True),
    ]


def _entity_classes(value: Any, individual_markers: list[str], company_markers: list[str]) -> list[EntityClass]:
    if value is None:
        return _default_entity_classes(individual_markers, company_markers)
    if not isinstance(value, list) or not value:
        raise ProfileError("entity_classes must be a non-empty list")
    classes: list[EntityClass] = []
    keys: set[str] = set()
    fallback_count = 0
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ProfileError(f"entity_classes[{index}] must be a mapping")
        key = item.get("key")
        label = item.get("label")
        fallback = _boolean(item.get("fallback", False), f"entity_classes[{index}].fallback")
        if not isinstance(key, str) or not key or not key.replace("_", "").isalnum():
            raise ProfileError(f"entity_classes[{index}].key must contain letters, digits, or underscores")
        if key in keys:
            raise ProfileError(f"entity_classes contains duplicate key: {key}")
        if not isinstance(label, str) or not label.strip():
            raise ProfileError(f"entity_classes[{index}].label is required")
        markers = _string_list(item.get("markers"), f"entity_classes[{index}].markers")
        if fallback:
            fallback_count += 1
            if markers:
                raise ProfileError(f"entity_classes[{index}] fallback cannot define markers")
        elif not markers:
            raise ProfileError(f"entity_classes[{index}] needs markers or fallback: true")
        keys.add(key)
        classes.append(EntityClass(key, label.strip(), markers, fallback))
    if fallback_count > 1:
        raise ProfileError("entity_classes may contain at most one fallback")
    return classes


def _boolean(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ProfileError(f"{field_name} must be true or false")
    return value


def _date_or_empty(value: Any, field_name: str) -> str:
    if value is None or value == "":
        return ""
    if type(value) is date:
        return value.isoformat()
    if not isinstance(value, str):
        raise ProfileError(f"{field_name} must be an ISO date (YYYY-MM-DD) or empty")
    try:
        return date.fromisoformat(value.strip()).isoformat()
    except ValueError as exc:
        raise ProfileError(f"{field_name} must be an ISO date (YYYY-MM-DD) or empty") from exc


def _redactions(value: Any) -> list[str]:
    fields = _string_list(value, "privacy.redact_fields")
    available = set(CompanyRecord.__dataclass_fields__) - {"source"}
    unknown = set(fields) - available
    if unknown:
        raise ProfileError(f"privacy.redact_fields contains unknown field: {sorted(unknown)[0]}")
    return fields


def load_profile(path: str | Path) -> IndustryProfile:
    """Read a YAML profile; no executable values or environment expansion."""

    source = Path(path)
    try:
        document = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    except OSError as exc:
        raise ProfileError(f"could not read profile: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ProfileError(f"invalid YAML: {exc}") from exc
    if not isinstance(document, dict):
        raise ProfileError("profile root must be a mapping")

    data = document.get("profile", document)
    if not isinstance(data, dict):
        raise ProfileError("profile must be a mapping")
    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ProfileError("profile.name is required")

    location = data.get("location") or {}
    privacy = data.get("privacy") or {}
    risk = data.get("max_risk") or {}
    if not isinstance(location, dict) or not isinstance(privacy, dict) or not isinstance(risk, dict):
        raise ProfileError("location, privacy, and max_risk must be mappings")
    districts = location.get("allowed_districts") or {}
    if not isinstance(districts, dict) or any(not isinstance(key, str) for key in districts):
        raise ProfileError("location.allowed_districts must map city names to string lists")

    normalized_districts = {
        city: _string_list(values, f"location.allowed_districts.{city}")
        for city, values in districts.items()
    }
    normalized_risk: dict[str, int] = {}
    for key, value in risk.items():
        if key not in {"self", "related", "history"} or not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ProfileError("max_risk supports non-negative integer self, related, and history keys")
        normalized_risk[key] = value

    entity_mode = data.get("entity_mode", "any")
    if entity_mode not in {"any", "individual", "company"}:
        raise ProfileError("entity_mode must be any, individual, or company")

    individual_markers = _string_list(data.get("individual_markers", ["个体工商户"]), "individual_markers")
    company_markers = _string_list(data.get("company_markers", ["公司"]), "company_markers")
    phone_leads = data.get("phone_leads") or {}
    if not isinstance(phone_leads, dict):
        raise ProfileError("phone_leads must be a mapping")
    min_phone_count = phone_leads.get("min_phone_count", 0)
    if not isinstance(min_phone_count, int) or isinstance(min_phone_count, bool) or min_phone_count < 0:
        raise ProfileError("phone_leads.min_phone_count must be a non-negative integer")
    target_entity_classes = _string_list(phone_leads.get("target_entity_classes"), "phone_leads.target_entity_classes")
    entity_classes = _entity_classes(data.get("entity_classes"), individual_markers, company_markers)
    available_entity_keys = {entity_class.key for entity_class in entity_classes}
    unknown_targets = set(target_entity_classes) - available_entity_keys
    if unknown_targets:
        raise ProfileError(f"phone_leads.target_entity_classes contains unknown class: {sorted(unknown_targets)[0]}")
    export_redactions = _redactions(privacy.get("redact_fields"))

    return IndustryProfile(
        name=name.strip(),
        positive_terms=_string_list(data.get("positive_terms"), "positive_terms"),
        negative_terms=_string_list(data.get("negative_terms"), "negative_terms"),
        required_terms=_string_list(data.get("required_terms"), "required_terms"),
        entity_mode=entity_mode,
        individual_markers=individual_markers,
        company_markers=company_markers,
        entity_classes=entity_classes,
        established_on_or_after=_date_or_empty(data.get("established_on_or_after"), "established_on_or_after"),
        allowed_statuses=_string_list(data.get("allowed_statuses"), "allowed_statuses"),
        max_risk=normalized_risk,
        require_phone=_boolean(data.get("require_phone", False), "require_phone"),
        min_phone_count=min_phone_count,
        target_entity_classes=target_entity_classes,
        allowed_cities=_string_list(location.get("allowed_cities"), "location.allowed_cities"),
        allowed_districts=normalized_districts,
        export_redactions=export_redactions,
    )
