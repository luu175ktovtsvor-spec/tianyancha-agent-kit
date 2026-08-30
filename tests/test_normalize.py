from tyc_agent.normalize import normalize_tianyancha_record


def test_normalize_maps_provider_fields_without_source_mutation():
    raw = {
        "id": 7,
        "name": "<em>示例</em>企业",
        "creditCode": "CODE-7",
        "establishmentTime": 20250102,
        "legalPersonName": "负责人",
        "phoneList": ["100", "100", ""],
        "categoryNameLv1": "服务",
        "selfRiskCount": "1",
    }
    result = normalize_tianyancha_record(raw)
    assert result.name == "示例企业"
    assert result.established_on == "2025-01-02"
    assert result.phones == ["100"]
    assert result.categories == ["服务"]
    assert result.risk == {"self": 1, "related": 0, "history": 0}
    assert result.source == raw


def test_normalize_rejects_impossible_provider_date():
    result = normalize_tianyancha_record({"establishmentTime": 20251340})
    assert result.established_on == ""
