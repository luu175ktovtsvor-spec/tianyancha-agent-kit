"""Transparent, profile-driven filtering with an auditable rejection reason."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace

from .models import CompanyRecord, FilterResult, IndustryProfile, PhoneLeadResult


def _contains_any(text: str, terms: list[str]) -> bool:
    return any(term.casefold() in text.casefold() for term in terms)


def _candidate_text(record: CompanyRecord) -> str:
    return "\n".join([record.name, record.business_scope, *record.categories])


def _matches_entity(record: CompanyRecord, profile: IndustryProfile) -> bool:
    if profile.entity_mode == "any":
        return True
    markers = profile.individual_markers if profile.entity_mode == "individual" else profile.company_markers
    return _contains_any(record.entity_type, markers)


def classify_entity(record: CompanyRecord, profile: IndustryProfile) -> str:
    """Classify by ordered profile rules; return a stable key for lead routing."""

    fallback = "unclassified"
    for entity_class in profile.entity_classes:
        if entity_class.fallback:
            fallback = entity_class.key
        elif _contains_any(record.entity_type, entity_class.markers):
            return entity_class.key
    return fallback


def _matches_location(record: CompanyRecord, profile: IndustryProfile) -> bool:
    if profile.allowed_cities and record.city not in profile.allowed_cities:
        return False
    if not profile.allowed_districts:
        return True
    if record.city not in profile.allowed_districts:
        return False
    allowed_districts = profile.allowed_districts[record.city]
    return not allowed_districts or record.district in allowed_districts


def first_rejection_reason(record: CompanyRecord, profile: IndustryProfile) -> str | None:
    """Return the first failed rule in a predictable order, or ``None``."""

    text = _candidate_text(record)
    if profile.positive_terms and not _contains_any(text, profile.positive_terms):
        return "positive_terms"
    if profile.negative_terms and _contains_any(text, profile.negative_terms):
        return "negative_terms"
    if profile.required_terms and not _contains_any(text, profile.required_terms):
        return "required_terms"
    if not _matches_entity(record, profile):
        return "entity_type"
    if profile.established_on_or_after and (
        not record.established_on or record.established_on < profile.established_on_or_after
    ):
        return "established_on"
    if profile.allowed_statuses and record.status not in profile.allowed_statuses:
        return "status"
    for key, maximum in profile.max_risk.items():
        if record.risk.get(key, 0) > maximum:
            return f"risk.{key}"
    minimum = max(profile.min_phone_count, 1 if profile.require_phone else 0)
    if len(record.phones) < minimum:
        return "phone_count"
    if not _matches_location(record, profile):
        return "location"
    return None


def deduplicate(records: Iterable[CompanyRecord]) -> list[CompanyRecord]:
    """Deduplicate with stable ordering; prefer credit code then source id."""

    seen: set[str] = set()
    output: list[CompanyRecord] = []
    for record in records:
        key = record.credit_code or record.source_id
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        output.append(record)
    return output


def filter_records(records: Iterable[CompanyRecord], profile: IndustryProfile) -> FilterResult:
    result = FilterResult()
    for record in deduplicate(records):
        reason = first_rejection_reason(record, profile)
        if reason:
            result.reject(record, reason)
        else:
            result.accepted.append(record)
    return result


def build_phone_leads(records: Iterable[CompanyRecord], profile: IndustryProfile) -> PhoneLeadResult:
    """Filter phone-bearing records and route them into entity-specific buckets.

    ``phone-leads`` always requires at least one number even if the profile was
    originally written for a broader company-research task.
    """

    effective_profile = replace(profile, min_phone_count=max(profile.min_phone_count, 1))
    result = filter_records(records, effective_profile)
    leads = PhoneLeadResult(rejected=list(result.rejected), reason_counts=dict(result.reason_counts))
    selected_classes = set(profile.target_entity_classes)
    for record in result.accepted:
        entity_class = classify_entity(record, effective_profile)
        if selected_classes and entity_class not in selected_classes:
            reason = f"entity_class.{entity_class}"
            leads.rejected.append({"reason": reason, "record": record.to_dict()})
            leads.reason_counts[reason] = leads.reason_counts.get(reason, 0) + 1
            continue
        leads.leads_by_entity.setdefault(entity_class, []).append(record)
    return leads
