import csv

from tyc_agent.exporters import export_records
from tyc_agent.models import CompanyRecord


def test_csv_neutralizes_formula_after_leading_whitespace(tmp_path):
    output = tmp_path / "safe.csv"
    export_records([CompanyRecord(name="\t=1+1")], output, "csv")
    with output.open(encoding="utf-8-sig", newline="") as handle:
        row = next(csv.DictReader(handle))
    assert row["name"] == "'\t=1+1"
