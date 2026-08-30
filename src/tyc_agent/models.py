"""Canonical, provider-neutral data structures used by the pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class CompanyRecord:
    """A normalized company record.

    Keep source-specific fields in ``source`` so filtering and exports remain
    stable if a provider changes its response shape.
    """

    name: str = ""
    credit_code: str = ""
    entity_type: str = ""
    established_on: str = ""
    status: str = ""
    province: str = ""
    city: str = ""
    district: str = ""
    address: str = ""
    representative: str = ""
    phones: list[str] = field(default_factory=list)
    business_scope: str = ""
    categories: list[str] = field(default_factory=list)
    risk: dict[str, int] = field(default_factory=dict)
    source_id: str = ""
    source: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class EntityClass:
    """A named entity bucket used for lead routing.

    ``markers`` are matched against the source's entity-type field in order.
    A class with ``fallback=True`` catches every record not matched earlier.
    """

    key: str
    label: str
    markers: list[str] = field(default_factory=list)
    fallback: bool = False


@dataclass(slots=True)
class IndustryProfile:
    """Rules for an acquisition-lead job without embedding a local business standard."""

    name: str
    positive_terms: list[str] = field(default_factory=list)
    negative_terms: list[str] = field(default_factory=list)
    required_terms: list[str] = field(default_factory=list)
    entity_mode: str = "any"
    individual_markers: list[str] = field(default_factory=lambda: ["个体工商户"])
    company_markers: list[str] = field(default_factory=lambda: ["公司"])
    entity_classes: list[EntityClass] = field(default_factory=list)
    established_on_or_after: str = ""
    allowed_statuses: list[str] = field(default_factory=list)
    max_risk: dict[str, int] = field(default_factory=dict)
    require_phone: bool = False
    min_phone_count: int = 0
    target_entity_classes: list[str] = field(default_factory=list)
    allowed_cities: list[str] = field(default_factory=list)
    allowed_districts: dict[str, list[str]] = field(default_factory=dict)
    export_redactions: list[str] = field(default_factory=list)


@dataclass(slots=True)
class FilterResult:
    accepted: list[CompanyRecord] = field(default_factory=list)
    rejected: list[dict[str, Any]] = field(default_factory=list)
    reason_counts: dict[str, int] = field(default_factory=dict)

    def reject(self, record: CompanyRecord, reason: str) -> None:
        self.rejected.append({"reason": reason, "record": record.to_dict()})
        self.reason_counts[reason] = self.reason_counts.get(reason, 0) + 1


@dataclass(slots=True)
class PhoneLeadResult:
    """Final acquisition leads, grouped by entity class, plus the audit trail."""

    leads_by_entity: dict[str, list[CompanyRecord]] = field(default_factory=dict)
    rejected: list[dict[str, Any]] = field(default_factory=list)
    reason_counts: dict[str, int] = field(default_factory=dict)

    @property
    def accepted_count(self) -> int:
        return sum(len(records) for records in self.leads_by_entity.values())
