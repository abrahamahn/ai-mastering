from __future__ import annotations

import re
import shutil
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

from .chain import process
from .intent import apply_intent_to_settings, parse_comment_intent
from .metrics import collect_metrics as _metrics
from .reporting import finalize_ai_report
from .render import _match_lufs_with_peak_guard, _resolve_effective_target
from .scoring import (
    apply_intent_bias as _apply_intent_bias,
    best_candidate as _best_candidate,
    score_candidate as _score_candidate,
)
from .settings import MasteringSettings, candidate_settings
from ..audio.source_match import restore_source_balance
from ..models.local_scorer import apply_local_model_scores


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_") or "candidate"


def _render_candidate(
    source_audio: np.ndarray,
    sr: int,
    source_metrics: dict[str, float],
    out_dir: Path,
    basename: str,
    requested_target: float,
    settings: MasteringSettings,
) -> dict[str, Any]:
    effective_target, target_note = _resolve_effective_target(requested_target, source_metrics["lufs"])
    name = _safe_name(settings.name)
    output_name = f"{basename}_ai_{name}.wav"
    output_path = out_dir / output_name

    print(f"[ai-master] Rendering {settings.name}: {settings.description}")
    mastered = process(source_audio.copy(), sr, effective_target, settings=settings)
    if settings.source_match_enabled:
        mastered, source_match = restore_source_balance(
            mastered,
            source_audio,
            sr,
            presence_max_db=settings.source_match_presence_max_db,
            sub_trim_max_db=settings.source_match_sub_trim_max_db,
            side_max_db=settings.source_match_side_max_db,
        )
    else:
        source_match = {
            "source_match_moves": [],
            "presence_loss_db_before_restore": 0.0,
            "sub_lift_db_before_restore": 0.0,
        }

    mastered, qc = _match_lufs_with_peak_guard(
        mastered,
        sr,
        effective_target,
        source_metrics.get("loud_window_crest_db"),
    )
    sf.write(str(output_path), mastered.T, sr, subtype="PCM_24")
    metrics = _metrics(mastered, sr)
    score, score_notes = _score_candidate(source_metrics, metrics, effective_target)
    warnings = list(qc.get("warnings", []))
    if target_note:
        warnings.append(target_note)

    return {
        "name": settings.name,
        "description": settings.description,
        "path": str(output_path),
        "file": output_name,
        "requested_target_lufs": requested_target,
        "target_lufs": effective_target,
        "settings": settings.to_dict(),
        "metrics": metrics,
        "metric_score": score,
        "metric_score_notes": score_notes,
        "score": score,
        "score_notes": score_notes,
        "warnings": warnings,
        **qc,
        **source_match,
    }


def _render_candidate_from_path(
    input_path: str,
    source_metrics: dict[str, float],
    out_dir: str,
    basename: str,
    requested_target: float,
    settings: MasteringSettings,
) -> dict[str, Any]:
    source_audio, sr = _read_audio(input_path)
    return _render_candidate(
        source_audio,
        sr,
        source_metrics,
        Path(out_dir),
        basename,
        requested_target,
        settings,
    )


def _render_initial_candidates(
    input_path: Path,
    source_audio: np.ndarray,
    sr: int,
    source_metrics: dict[str, float],
    out_dir: Path,
    basename: str,
    target_lufs: float,
    settings_catalog: list[MasteringSettings],
    jobs: int,
) -> list[dict[str, Any]]:
    if jobs <= 1 or len(settings_catalog) <= 1:
        return [
            _render_candidate(source_audio, sr, source_metrics, out_dir, basename, target_lufs, settings)
            for settings in settings_catalog
        ]

    workers = max(1, min(jobs, len(settings_catalog)))
    print(f"  [ai-master] Rendering {len(settings_catalog)} candidates with {workers} worker processes")
    results: dict[int, dict[str, Any]] = {}
    with ProcessPoolExecutor(max_workers=workers) as executor:
        future_map = {
            executor.submit(
                _render_candidate_from_path,
                str(input_path),
                source_metrics,
                str(out_dir),
                basename,
                target_lufs,
                settings,
            ): index
            for index, settings in enumerate(settings_catalog)
        }
        for future in as_completed(future_map):
            index = future_map[future]
            results[index] = future.result()

    return [results[index] for index in range(len(settings_catalog))]


def _source_candidate(input_path: Path, out_dir: Path, basename: str, audio: np.ndarray, sr: int) -> dict[str, Any]:
    output_name = f"{basename}_ai_original.wav"
    output_path = out_dir / output_name
    shutil.copy2(input_path, output_path)
    metrics = _metrics(audio, sr)
    return {
        "name": "original",
        "description": "unprocessed source reference",
        "path": str(output_path),
        "file": output_name,
        "requested_target_lufs": metrics["lufs"],
        "target_lufs": metrics["lufs"],
        "settings": None,
        "metrics": metrics,
        "metric_score": 50.0,
        "metric_score_notes": ["reference baseline — not eligible to win unless all processed candidates fail guards"],
        "score": 50.0,
        "score_notes": ["reference baseline — not eligible to win unless all processed candidates fail guards"],
        "warnings": [],
    }


def _read_audio(path: str) -> tuple[np.ndarray, int]:
    audio, sr = sf.read(path, dtype="float32", always_2d=True)
    return audio.T, sr


def render_ai_master(
    input_path: Path,
    out_dir: Path,
    basename: str,
    target_lufs: float,
    style: str,
    use_local_models: bool | None,
    json_out: Path | None,
    jobs: int = 1,
) -> dict[str, Any]:
    if not input_path.exists():
        raise FileNotFoundError(f"Input WAV not found: {input_path}")

    out_dir.mkdir(parents=True, exist_ok=True)
    source_audio, sr = _read_audio(str(input_path))
    source_metrics = _metrics(source_audio, sr)
    comment_intent = parse_comment_intent(style)
    print(
        "  [ai-master] Comment intent: "
        f"{', '.join(comment_intent.tags) if comment_intent.tags else 'neutral'}"
    )
    candidates: list[dict[str, Any]] = [_source_candidate(input_path, out_dir, basename, source_audio, sr)]

    settings_catalog = apply_intent_to_settings(candidate_settings(style), comment_intent)
    candidates.extend(
        _render_initial_candidates(
            input_path,
            source_audio,
            sr,
            source_metrics,
            out_dir,
            basename,
            target_lufs,
            settings_catalog,
            max(1, jobs),
        )
    )

    local_model_report = apply_local_model_scores(candidates, source_audio, sr, style, use_local_models)
    _apply_intent_bias(candidates, comment_intent)
    best = _best_candidate(source_metrics, candidates)

    best_output = out_dir / f"{basename}_ai_best.wav"
    shutil.copy2(best["path"], best_output)
    report = {
        "input": str(input_path),
        "out_dir": str(out_dir),
        "basename": basename,
        "style": style,
        "comment_intent": comment_intent.to_dict(),
        "target_lufs": target_lufs,
        "jobs": max(1, jobs),
        "selection": "deterministic release guards + local CLAP/MERT + intent bias",
        "source_metrics": source_metrics,
        "local_model_scoring": local_model_report,
        "best_candidate": best["name"],
        "best_path": str(best_output),
        "best_reason": "highest guarded pillar score",
        "candidates": candidates,
    }

    return finalize_ai_report(report, json_out)
