from pathlib import Path

import pytest

from tyc_agent.browser_automation import BrowserAutomationError, collect_browser_records, extract_record, load_browser_profile


class _Locator:
    def __init__(self, values):
        self.values = values

    def all_inner_texts(self):
        return self.values


class _Item:
    def __init__(self, values):
        self.values = values

    def locator(self, selector):
        return _Locator(self.values.get(selector, []))


def test_demo_browser_profile_is_valid_and_uses_local_http():
    root = Path(__file__).resolve().parents[1]
    profile = load_browser_profile(root / "examples" / "browser-profile.demo.yaml")
    assert profile.start_url == "http://127.0.0.1:8765/browser-demo.html"
    assert profile.item_selector == "article.company-card"


def test_external_http_browser_profile_is_rejected(tmp_path):
    source = tmp_path / "browser-profile.yaml"
    source.write_text(
        "browser:\n  start_url: http://example.com\n  item_selector: article\n  fields:\n    name: .name\n",
        encoding="utf-8",
    )
    with pytest.raises(BrowserAutomationError, match="HTTPS"):
        load_browser_profile(source)


def test_headless_mode_is_rejected_for_external_url():
    profile = load_browser_profile(Path(__file__).resolve().parents[1] / "examples" / "browser-profile.example.yaml")
    with pytest.raises(BrowserAutomationError, match="headless"):
        collect_browser_records(profile, confirm_ready=True, headless=True)


def test_extract_record_maps_strings_and_multiple_phones():
    record = extract_record(
        _Item({
            ".name": ["示例企业"],
            ".credit": ["DEMO-CODE"],
            ".type": ["有限责任公司"],
            ".date": ["2025年1月2日"],
            ".phone": ["000-0000-0001", "000-0000-0011"],
            ".category": ["示例服务; 其他服务"],
            ".self-risk": ["自身风险 2"],
        }),
        {
            "name": ".name",
            "credit_code": ".credit",
            "entity_type": ".type",
            "established_on": ".date",
            "phones": ".phone",
            "categories": ".category",
        },
        {"self": ".self-risk"},
    )
    assert record["name"] == "示例企业"
    assert record["phones"] == ["000-0000-0001", "000-0000-0011"]
    assert record["categories"] == ["示例服务", "其他服务"]
    assert record["established_on"] == "2025-01-02"
    assert record["risk"] == {"self": 2}
