"""Convert tabular API rows to CSV for leadership exports."""

from __future__ import annotations

import csv
import io
import json
from typing import Any, Dict, List


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, default=str)
    return str(value)


def dicts_to_csv(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "export_status\nno_rows_in_scope\n"
    buf = io.StringIO()
    fieldnames = list(rows[0].keys())
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: _cell(row.get(k)) for k in fieldnames})
    return buf.getvalue()
