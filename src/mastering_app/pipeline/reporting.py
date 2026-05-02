from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .report_html import write_ai_html_report


def finalize_ai_report(report: dict[str, Any], json_out: Path | None) -> dict[str, Any]:
    """Persist history, HTML, optional JSON, and print the machine-readable report."""
    try:
        from ..history.db import HistoryDB

        db = HistoryDB()
        run_id = db.save_run(report)
        db.close()
        report["history_run_id"] = run_id
        print(
            f"  [ai-master] Run saved to history DB (id={run_id}). "
            f"To record your preference: master.py prefer {run_id} <candidate_name>"
        )
    except Exception as exc:
        print(f"  [ai-master] WARNING: could not save to history DB: {exc}")

    html_out = json_out.with_suffix(".html") if json_out else Path(report["out_dir"]) / "ai-mastering-report.html"
    report["html_report"] = str(html_out)
    try:
        write_ai_html_report(report, html_out)
        print(f"  [ai-master] HTML report written: {html_out}")
    except Exception as exc:
        print(f"  [ai-master] WARNING: could not write HTML report: {exc}")

    text = json.dumps(report, indent=2)
    if json_out:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(text, encoding="utf-8")
    print(text)
    return report
