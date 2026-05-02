"""SQLite history database for mastering runs and preference labels."""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _db_path() -> Path:
    raw = os.environ.get("MASTERING_HISTORY_DB", "")
    if raw.strip():
        return Path(raw).expanduser()
    return Path(__file__).resolve().parents[4] / "history.db"


def _ref_dir() -> Path | None:
    raw = os.environ.get("MASTERING_REFERENCE_DIR", "")
    return Path(raw).expanduser() if raw.strip() else None


_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_at      TEXT    NOT NULL,
    basename    TEXT    NOT NULL,
    source_path TEXT,
    style       TEXT,
    target_lufs REAL,
    model_best  TEXT,
    model_reason TEXT
);

CREATE TABLE IF NOT EXISTS candidates (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          INTEGER NOT NULL REFERENCES runs(id),
    name            TEXT    NOT NULL,
    description     TEXT,
    metric_score    REAL,
    final_score     REAL,
    mert_preservation REAL,
    clap_delta      REAL,
    presence_db     REAL,
    air_db          REAL,
    sub_db          REAL,
    side_to_mid_db  REAL,
    crest_factor_db REAL,
    lufs            REAL,
    wav_path        TEXT,
    settings_json   TEXT,
    score_notes     TEXT
);

CREATE TABLE IF NOT EXISTS preferences (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          INTEGER NOT NULL,
    preferred_name  TEXT    NOT NULL,
    noted_at        TEXT    NOT NULL,
    reason_tags     TEXT
);

CREATE TABLE IF NOT EXISTS pairwise_labels (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id    INTEGER NOT NULL,
    winner    TEXT    NOT NULL,
    loser     TEXT    NOT NULL,
    noted_at  TEXT    NOT NULL
);
"""


class HistoryDB:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _db_path()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._con = sqlite3.connect(str(self._path))
        self._con.row_factory = sqlite3.Row
        self._con.executescript(_SCHEMA)
        self._con.commit()

    # ── Write ────────────────────────────────────────────────────────────────

    def save_run(self, report: dict[str, Any]) -> int:
        """Persist an ai-render report and return the new run_id."""
        now = datetime.now(timezone.utc).isoformat()
        cur = self._con.execute(
            "INSERT INTO runs (run_at, basename, source_path, style, target_lufs, model_best, model_reason) "
            "VALUES (?,?,?,?,?,?,?)",
            (
                now,
                report.get("basename", ""),
                report.get("input", ""),
                report.get("style", ""),
                report.get("target_lufs"),
                report.get("best_candidate"),
                report.get("best_reason"),
            ),
        )
        run_id = cur.lastrowid
        assert run_id is not None

        for candidate in report.get("candidates", []):
            metrics = candidate.get("metrics", {})
            local = candidate.get("local_model_scores", {})
            self._con.execute(
                "INSERT INTO candidates "
                "(run_id, name, description, metric_score, final_score, "
                " mert_preservation, clap_delta, presence_db, air_db, sub_db, "
                " side_to_mid_db, crest_factor_db, lufs, wav_path, settings_json, score_notes) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    run_id,
                    candidate.get("name", ""),
                    candidate.get("description", ""),
                    candidate.get("metric_score"),
                    candidate.get("score"),
                    local.get("mert_content_preservation"),
                    local.get("clap_style_delta"),
                    metrics.get("presence_db"),
                    metrics.get("air_db"),
                    metrics.get("sub_db"),
                    metrics.get("side_to_mid_db"),
                    metrics.get("crest_factor_db"),
                    metrics.get("lufs"),
                    candidate.get("path"),
                    json.dumps(candidate.get("settings")) if candidate.get("settings") else None,
                    json.dumps(candidate.get("score_notes", [])),
                ),
            )

        self._con.commit()
        return run_id

    def record_preference(
        self,
        run_id: int,
        preferred_name: str,
        reason_tags: list[str] | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._con.execute(
            "INSERT INTO preferences (run_id, preferred_name, noted_at, reason_tags) VALUES (?,?,?,?)",
            (run_id, preferred_name, now, json.dumps(reason_tags or [])),
        )
        # Auto-generate pairwise labels: winner beats every other candidate in this run
        other_candidates = self._con.execute(
            "SELECT name FROM candidates WHERE run_id=? AND name != ?",
            (run_id, preferred_name),
        ).fetchall()
        for row in other_candidates:
            self._con.execute(
                "INSERT INTO pairwise_labels (run_id, winner, loser, noted_at) VALUES (?,?,?,?)",
                (run_id, preferred_name, row["name"], now),
            )
        self._con.commit()

        ref_dir = _ref_dir()
        if ref_dir:
            wav_row = self._con.execute(
                "SELECT wav_path FROM candidates WHERE run_id=? AND name=?",
                (run_id, preferred_name),
            ).fetchone()
            if wav_row and wav_row["wav_path"] and Path(wav_row["wav_path"]).exists():
                ref_dir.mkdir(parents=True, exist_ok=True)
                dest = ref_dir / f"{run_id}_{preferred_name}.wav"
                shutil.copy2(wav_row["wav_path"], dest)
                print(f"[history] Copied approved master to reference dir: {dest.name}")

    # ── Read ─────────────────────────────────────────────────────────────────

    def recent_runs(self, limit: int = 10) -> list[dict[str, Any]]:
        rows = self._con.execute(
            "SELECT r.id, r.run_at, r.basename, r.model_best, "
            "       p.preferred_name AS user_best "
            "FROM runs r "
            "LEFT JOIN preferences p ON p.run_id = r.id "
            "ORDER BY r.id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    def pairwise_training_data(self) -> list[dict[str, Any]]:
        """Return all pairwise (winner, loser) rows with full feature vectors."""
        labels = self._con.execute(
            "SELECT run_id, winner, loser FROM pairwise_labels"
        ).fetchall()
        result = []
        for label in labels:
            winner = self._candidate_features(label["run_id"], label["winner"])
            loser = self._candidate_features(label["run_id"], label["loser"])
            if winner and loser:
                result.append({"run_id": label["run_id"], "winner": winner, "loser": loser})
        return result

    def _candidate_features(self, run_id: int, name: str) -> dict[str, Any] | None:
        row = self._con.execute(
            "SELECT * FROM candidates WHERE run_id=? AND name=?", (run_id, name)
        ).fetchone()
        return dict(row) if row else None

    def get_run(self, run_id: int) -> dict[str, Any] | None:
        row = self._con.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if not row:
            return None
        candidates = self._con.execute(
            "SELECT * FROM candidates WHERE run_id=?", (run_id,)
        ).fetchall()
        preferences = self._con.execute(
            "SELECT preferred_name, reason_tags FROM preferences WHERE run_id=?", (run_id,)
        ).fetchall()
        return {
            **dict(row),
            "candidates": [dict(c) for c in candidates],
            "preferences": [dict(p) for p in preferences],
        }

    def close(self) -> None:
        self._con.close()
