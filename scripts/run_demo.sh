#!/usr/bin/env bash
set -euo pipefail

DEMO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEMO_PYTHON="${DEMO_PYTHON:-$DEMO_ROOT/.venv/bin/python}"
DEMO_OUTPUT_DIR="${DEMO_OUTPUT_DIR:-$(mktemp -d)}"
DEMO_PORT=8765

if [[ ! -x "$DEMO_PYTHON" ]]; then
  echo "Missing virtual environment. Run the installation commands in README first." >&2
  exit 2
fi

"$DEMO_PYTHON" -m http.server "$DEMO_PORT" --directory "$DEMO_ROOT/examples" >/dev/null 2>&1 &
DEMO_SERVER_PID=$!

cleanup() {
  kill "$DEMO_SERVER_PID" 2>/dev/null || true
  wait "$DEMO_SERVER_PID" 2>/dev/null || true
}
trap cleanup EXIT

sleep 1

"$DEMO_PYTHON" -m tyc_agent browser-collect \
  --browser-profile "$DEMO_ROOT/examples/browser-profile.demo.yaml" \
  --output "$DEMO_OUTPUT_DIR/captured.json" \
  --ready \
  --headless

"$DEMO_PYTHON" -m tyc_agent phone-leads \
  --profile "$DEMO_ROOT/examples/industry-profile.example.yaml" \
  --input "$DEMO_OUTPUT_DIR/captured.json" \
  --input-kind canonical \
  --format xlsx \
  --output-dir "$DEMO_OUTPUT_DIR/output"

"$DEMO_PYTHON" - "$DEMO_OUTPUT_DIR" <<'PY'
import json
import sys
from pathlib import Path

import openpyxl

output = Path(sys.argv[1])
records = json.loads((output / "captured.json").read_text(encoding="utf-8"))
required = {
    "all_phone_leads.xlsx",
    "enterprise_phone_leads.xlsx",
    "individual_business_phone_leads.xlsx",
    "rejected_phone_leads.json",
}
actual = {path.name for path in (output / "output").iterdir()}
workbook = openpyxl.load_workbook(output / "output" / "all_phone_leads.xlsx", read_only=True, data_only=True)
lead_rows = workbook.active.max_row - 1
workbook.close()
rejected = json.loads((output / "output" / "rejected_phone_leads.json").read_text(encoding="utf-8"))
if len(records) != 5 or lead_rows != 2 or len(rejected) != 3 or not required <= actual:
    raise SystemExit("demo output verification failed")
print(json.dumps({"ok": True, "captured_records": len(records), "phone_leads": lead_rows, "rejected": len(rejected), "output_dir": str(output)}, ensure_ascii=False))
PY
