from tyc_agent.models import CompanyRecord, IndustryProfile
from tyc_agent.rules import filter_records


def profile():
    return IndustryProfile(
        name="demo",
        positive_terms=["服务"],
        negative_terms=["批发"],
        required_terms=["体验"],
        entity_mode="company",
        established_on_or_after="2024-01-01",
        allowed_statuses=["存续"],
        max_risk={"self": 0},
        require_phone=True,
        allowed_cities=["示例市"],
    )


def record(**changes):
    values = dict(
        name="示例服务企业", credit_code="A", entity_type="有限责任公司", established_on="2025-01-01",
        status="存续", city="示例市", phones=["100"], business_scope="体验服务", risk={"self": 0},
    )
    values.update(changes)
    return CompanyRecord(**values)


def test_filter_accepts_and_deduplicates_stably():
    result = filter_records([record(), record(name="later duplicate")], profile())
    assert len(result.accepted) == 1
    assert not result.rejected


def test_filter_returns_first_explainable_reason():
    result = filter_records([record(business_scope="体验服务批发")], profile())
    assert result.reason_counts == {"negative_terms": 1}


def test_district_map_rejects_unlisted_city_and_district():
    selected = profile()
    selected.allowed_cities = []
    selected.allowed_districts = {"示例市": ["允许区"]}
    result = filter_records(
        [
            record(credit_code="A", district="允许区"),
            record(credit_code="B", district="其他区"),
            record(credit_code="C", city="其他市", district="允许区"),
        ],
        selected,
    )
    assert [item.credit_code for item in result.accepted] == ["A"]
    assert result.reason_counts == {"location": 2}


def test_empty_district_list_allows_whole_listed_city():
    selected = profile()
    selected.allowed_cities = []
    selected.allowed_districts = {"示例市": []}
    result = filter_records([record(district="任意区")], selected)
    assert len(result.accepted) == 1
