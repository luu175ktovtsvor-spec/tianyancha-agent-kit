import json
from pathlib import Path

from tyc_agent.cli import main


def test_run_writes_machine_readable_summary_and_redacted_export(tmp_path, capsys):
    root = Path(__file__).resolve().parents[1]
    profile = tmp_path / "profile.yaml"
    profile.write_text(
        """profile:
  name: test
  positive_terms: [个体经营部]
  negative_terms: []
  privacy:
    redact_fields: [phones]
""",
        encoding="utf-8",
    )
    output = tmp_path / "result.jsonl"
    exit_code = main([
        "run", "--profile", str(profile), "--input", str(root / "examples" / "authorized-results.example.json"),
        "--output", str(output), "--format", "jsonl",
    ])
    summary = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert summary["accepted"] == 1
    assert json.loads(output.read_text(encoding="utf-8").splitlines()[0])["phones"] == []
