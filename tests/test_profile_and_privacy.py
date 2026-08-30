from pathlib import Path

import pytest

from tyc_agent.models import CompanyRecord
from tyc_agent.privacy import PrivacyPathError, audit_public_tree, redact_record, require_private_path
from tyc_agent.profile import ProfileError, load_profile


def test_profile_loads_example():
    root = Path(__file__).resolve().parents[1]
    profile = load_profile(root / "examples" / "industry-profile.example.yaml")
    assert profile.name == "generic-company-phone-leads"
    assert profile.target_entity_classes == ["individual_business", "enterprise"]


def test_profile_rejects_invalid_mode(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("name: bad\nentity_mode: nope\n", encoding="utf-8")
    with pytest.raises(ProfileError):
        load_profile(path)


@pytest.mark.parametrize(
    "contents",
    [
        "name: bad\nrequire_phone: 'false'\n",
        "name: bad\nphone_leads:\n  min_phone_count: true\n",
        "name: bad\nentity_classes:\n  - key: other\n    label: Other\n    fallback: 'false'\n",
    ],
)
def test_profile_rejects_boolean_like_values(contents, tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text(contents, encoding="utf-8")
    with pytest.raises(ProfileError):
        load_profile(path)


def test_redaction_excludes_raw_source():
    record = CompanyRecord(phones=["100"], address="address", source={"private": "never export"})
    exported = redact_record(record, ["phones", "address"])
    assert exported["phones"] == []
    assert exported["address"] == "[REDACTED]"
    assert "source" not in exported


def test_audit_skips_env_example_but_finds_session(tmp_path):
    (tmp_path / ".env.example").write_text("# documented placeholder\n", encoding="utf-8")
    (tmp_path / "storage_state.json").write_text("{}", encoding="utf-8")
    findings = audit_public_tree(tmp_path)
    assert any(item["path"] == "storage_state.json" for item in findings)
    assert not any(item["path"] == ".env.example" for item in findings)


def test_audit_finds_phone_lead_raw_data(tmp_path):
    (tmp_path / "raw_authorized_results.json").write_text("[]", encoding="utf-8")
    findings = audit_public_tree(tmp_path)
    assert any(item["path"] == "raw_authorized_results.json" for item in findings)


def test_audit_finds_private_browser_profile(tmp_path):
    (tmp_path / "browser-profile.private.yaml").write_text("browser: {}\n", encoding="utf-8")
    findings = audit_public_tree(tmp_path)
    assert any(item["path"] == "browser-profile.private.yaml" for item in findings)


def test_audit_inspects_public_svg_text(tmp_path):
    test_phone = "138" + "12345678"
    (tmp_path / "diagram.svg").write_text(f"<svg>{test_phone}</svg>", encoding="utf-8")
    findings = audit_public_tree(tmp_path)
    assert any(item["path"] == "diagram.svg" and item["reason"] == "Chinese mobile phone number" for item in findings)


def test_audit_allows_official_lark_cli_link_but_flags_workspace_urls(tmp_path):
    workspace_url = "https://example." + "feishu.cn/sheets/private-token"
    (tmp_path / "links.md").write_text(
        "https://github.com/larksuite/cli\n"
        f"{workspace_url}\n",
        encoding="utf-8",
    )
    findings = audit_public_tree(tmp_path)
    assert findings == [{"path": "links.md", "reason": "external workspace URL"}]


def test_audit_flags_area_and_result_files_but_allows_public_fixture(tmp_path):
    examples = tmp_path / "examples"
    examples.mkdir()
    (examples / "authorized-results.example.json").write_text("[]", encoding="utf-8")
    (tmp_path / "area_private.json").write_text("{}", encoding="utf-8")
    (tmp_path / "authorized-results.json").write_text("[]", encoding="utf-8")
    findings = audit_public_tree(tmp_path)
    paths = {item["path"] for item in findings}
    assert "area_private.json" in paths
    assert "authorized-results.json" in paths
    assert "examples/authorized-results.example.json" not in paths


def test_private_runtime_paths_cannot_be_written_into_public_checkout(tmp_path):
    root = Path(__file__).resolve().parents[1]
    with pytest.raises(PrivacyPathError, match="outside the public source tree"):
        require_private_path(root / "output", "test output")
    assert require_private_path(tmp_path / "output", "test output") == (tmp_path / "output").resolve()
