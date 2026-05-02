from __future__ import annotations

import base64
import io
import json
import os
import re
import shutil
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf
from scipy import signal as scipy_signal

from .chain import process
from .intent import apply_intent_to_settings, parse_comment_intent
from .metrics import collect_metrics as _metrics
from .reporting import finalize_ai_report
from .render import _match_lufs_with_peak_guard, _resolve_effective_target
from .scoring import (
    apply_taste_and_intent as _apply_taste_and_intent,
    best_candidate as _best_candidate,
    candidate_passes_release_guards as _candidate_passes_release_guards,
    creative_audibility_bonus as _creative_audibility_bonus,
    score_candidate as _score_candidate,
)
from .settings import MasteringSettings, bounded_settings, candidate_settings
from ..audio.source_match import restore_source_balance
from ..models.local_scorer import apply_local_model_scores
from ..history.ranker import TasteRanker
from ..restoration.apollo import restore_with_apollo


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
    if settings.creative_mode:
        creative_bonus, creative_notes = _creative_audibility_bonus(source_metrics, metrics)
        score = float(round(score + creative_bonus, 3))
        score_notes.extend(creative_notes)
        score_notes.append("creative mode: source-match rollback disabled and release guards relaxed")

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


def _restored_source_candidate(
    restored_path: Path,
    basename: str,
    audio: np.ndarray,
    sr: int,
    source_metrics: dict[str, float],
    engine: str,
) -> dict[str, Any]:
    metrics = _metrics(audio, sr)
    score, score_notes = _score_candidate(source_metrics, metrics, source_metrics["lufs"])
    score_notes = [
        f"{engine} restored source before VST mastering",
        *score_notes,
    ]
    return {
        "name": f"{engine}_restored",
        "description": f"{engine} restored source reference; no VST mastering chain",
        "path": str(restored_path),
        "file": restored_path.name,
        "requested_target_lufs": metrics["lufs"],
        "target_lufs": metrics["lufs"],
        "settings": None,
        "restoration": {"engine": engine, "stage": "source"},
        "metrics": metrics,
        "metric_score": score,
        "metric_score_notes": score_notes,
        "score": score,
        "score_notes": list(score_notes),
        "warnings": [],
    }


def _restored_candidate_settings(settings_catalog: list[MasteringSettings], engine: str) -> list[MasteringSettings]:
    selected = {
        "transparent_repair",
        "creative_analog",
        "ai_deglaze",
        "dynamic_open",
    }
    restored: list[MasteringSettings] = []
    for settings in settings_catalog:
        if settings.name not in selected:
            continue
        restored.append(
            bounded_settings(
                settings,
                f"{engine}_{settings.name}",
                f"{engine} restoration -> {settings.description}",
                {
                    # Keep Apollo candidates tone-first. The restoration source already changes
                    # texture, so avoid source-match rollback and heavy limiting artifacts.
                    "source_match_presence_max_db": min(settings.source_match_presence_max_db, 1.2),
                    "source_match_side_max_db": min(settings.source_match_side_max_db, 1.4),
                    "source_match_sub_trim_max_db": min(settings.source_match_sub_trim_max_db, 0.5),
                    "loud_section_max_crest_loss_db": min(settings.loud_section_max_crest_loss_db, 0.6),
                },
            )
        )
    return restored


def _render_restored_candidates(
    restored_path: Path,
    restored_audio: np.ndarray,
    sr: int,
    source_metrics: dict[str, float],
    out_dir: Path,
    basename: str,
    target_lufs: float,
    settings_catalog: list[MasteringSettings],
    jobs: int,
    engine: str,
) -> list[dict[str, Any]]:
    settings = _restored_candidate_settings(settings_catalog, engine)
    if not settings:
        return []
    rendered = _render_initial_candidates(
        restored_path,
        restored_audio,
        sr,
        source_metrics,
        out_dir,
        basename,
        target_lufs,
        settings,
        jobs,
    )
    for candidate in rendered:
        candidate["restoration"] = {"engine": engine, "source": str(restored_path)}
    return rendered


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


def _loudest_segment(audio: np.ndarray, sr: int, seconds: float = 14.0) -> np.ndarray:
    segment_len = int(seconds * sr)
    if audio.shape[-1] <= segment_len:
        return audio
    mono = audio.mean(axis=0) if audio.ndim > 1 else audio
    hop = max(sr, segment_len // 4)
    best_start = 0
    best_rms = -1.0
    for start in range(0, len(mono) - segment_len, hop):
        segment = mono[start:start + segment_len]
        rms = float(np.sqrt(np.mean(segment ** 2)))
        if rms > best_rms:
            best_rms = rms
            best_start = start
    return audio[..., best_start:best_start + segment_len]


def _clip_to_base64_wav(audio: np.ndarray, sr: int) -> str:
    clip = _loudest_segment(audio, sr)
    target_sr = min(sr, 24000)
    if target_sr != sr:
        clip = scipy_signal.resample_poly(clip, target_sr, sr, axis=-1)
        sr = target_sr
    buffer = io.BytesIO()
    sf.write(buffer, clip.T, sr, format="WAV", subtype="PCM_16")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _read_audio(path: str) -> tuple[np.ndarray, int]:
    audio, sr = sf.read(path, dtype="float32", always_2d=True)
    return audio.T, sr


def _extract_json(text: str) -> dict[str, Any] | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None


def _call_openai_judge(
    source_audio: np.ndarray,
    sr: int,
    source_metrics: dict[str, float],
    candidates: list[dict[str, Any]],
    style: str,
    model: str,
) -> dict[str, Any] | None:
    if not os.environ.get("OPENAI_API_KEY"):
        return None

    try:
        from openai import OpenAI
    except ImportError:
        return {"error": "openai package is not installed in this Python environment"}

    top = sorted(candidates, key=lambda item: item["score"], reverse=True)[:3]
    content: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": (
                "You are a senior mastering engineer. Compare the source and candidate masters for "
                f"style goal: {style}. Prefer bright, open, wide, emotionally forward pop/EDM mastering "
                "that survives streaming loudness normalization. Do not reward raw LUFS that will simply "
                "be turned down; judge perceived loudness at matched playback volume. Avoid brittle "
                "digital shimmer and harsh 8-16 kHz buildup. Do not prefer a candidate that is darker, "
                "narrower, harsher, or less present than the source. "
                "Return strict JSON with keys: best_candidate, reasoning, suggested_settings. "
                "suggested_settings may contain only these bounded numeric keys: soothe_depth_scale, "
                "soothe1_mix, soothe2_depth_scale, soothe2_mix, multipass_macro_cap, alpha_ratio, "
                "alpha_threshold_offset, tape_color_scale, tape_color_offset, source_match_presence_max_db, "
                "source_match_side_max_db, source_match_sub_trim_max_db, gullfoss_recover, "
                "gullfoss_tame, gullfoss_brighten, bax_low_shelf_db, bax_high_shelf_db, "
                "bx_stereo_width, bx_mono_maker_hz, low_end_focus_contrast, low_end_focus_gain_db, "
                "inflator_effect, inflator_curve, inflator_input_gain, inflator_output_gain, "
                "ozone_imager_band_1_width_percent, ozone_imager_band_2_width_percent, "
                "ozone_imager_band_3_width_percent, ozone_imager_band_4_width_percent, "
                "ozone_imager_width_scale, ozone_imager_stereoizer_delay_ms, "
                "weiss_amount, weiss_limiter_gain_db, weiss_out_trim_dbfs, weiss_parallel_mix, "
                "ms_mid_warmth_db, ms_mid_presence_db, ms_side_presence_db, ms_side_hf_shelf_db, "
                "soft_clip_drive_db, soft_clip_mix, soft_clip_output_trim_db, "
                "hf_guard_ratio_threshold, hf_guard_air_to_presence_db, hf_guard_frequency_hz, "
                "hf_guard_max_reduction_db, loud_section_seconds, loud_section_min_crest_db, "
                "loud_section_max_crest_loss_db. "
                "It may also include these booleans: gullfoss_enabled, bax_enabled, bx_digital_enabled, "
                "bx_mono_maker_enabled, low_end_focus_enabled, inflator_enabled, ozone_imager_enabled, "
                "ozone_imager_stereoizer_enabled, hf_guard_enabled, loud_section_guard_enabled, "
                "creative_mode, ms_tone_enabled, soft_clip_enabled. "
                "It may include these strings only with valid values: final_limiter='ozone9' or 'weiss_mm1', "
                "low_end_focus_mode='Punchy' or 'Smooth', weiss_style='Transparent', 'Loud', 'Punch', "
                "'Wide', or 'De-ess'."
            ),
        },
        {"type": "text", "text": f"Source metrics:\n{json.dumps(source_metrics, indent=2)}"},
        {"type": "text", "text": "Source audio reference:"},
        {"type": "input_audio", "input_audio": {"data": _clip_to_base64_wav(source_audio, sr), "format": "wav"}},
        {
            "type": "text",
            "text": "Candidate metrics:\n" + json.dumps(
                [
                    {
                        "name": item["name"],
                        "description": item["description"],
                        "score": item["score"],
                        "score_notes": item["score_notes"],
                        "local_model_scores": item.get("local_model_scores", {}),
                        "metrics": item["metrics"],
                    }
                    for item in top
                ],
                indent=2,
            ),
        },
    ]

    for item in top:
        audio, candidate_sr = _read_audio(item["path"])
        content.extend([
            {"type": "text", "text": f"Candidate audio: {item['name']}"},
            {
                "type": "input_audio",
                "input_audio": {
                    "data": _clip_to_base64_wav(audio, candidate_sr),
                    "format": "wav",
                },
            },
        ])

    try:
        client = OpenAI()
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": content}],
        )
        text = response.choices[0].message.content or ""
        parsed = _extract_json(text)
        return parsed or {"error": "OpenAI response was not valid JSON", "raw": text}
    except Exception as exc:
        return {"error": str(exc)}


def render_ai_master(
    input_path: Path,
    out_dir: Path,
    basename: str,
    target_lufs: float,
    style: str,
    rounds: int,
    use_ai: bool,
    model: str,
    use_local_models: bool | None,
    json_out: Path | None,
    jobs: int = 1,
    use_apollo: bool | None = None,
    apollo_only: bool = False,
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
    restored_sources: list[tuple[str, Path, np.ndarray, int]] = []
    restoration_report: dict[str, Any] = {}

    apollo_path, apollo_report = restore_with_apollo(input_path, out_dir, basename, True if apollo_only else use_apollo)
    restoration_report["apollo"] = apollo_report
    if apollo_path:
        try:
            apollo_audio, apollo_sr = _read_audio(str(apollo_path))
            candidates.append(
                _restored_source_candidate(
                    apollo_path,
                    basename,
                    apollo_audio,
                    apollo_sr,
                    source_metrics,
                    "apollo",
                )
            )
            restored_sources.append(("apollo", apollo_path, apollo_audio, apollo_sr))
            print(f"  [ai-master] Apollo restoration ready: {apollo_path.name}")
        except Exception as exc:
            apollo_report.update({"ok": False, "error": f"Could not read Apollo output: {exc}"})
    elif apollo_report.get("enabled"):
        print(f"  [ai-master] Apollo restoration skipped: {apollo_report.get('error', 'no output')}")

    if apollo_only:
        if not apollo_path:
            raise RuntimeError(
                "Apollo-only render requested, but Apollo did not produce output: "
                f"{apollo_report.get('error', 'unknown Apollo error')}"
            )
        local_model_report = apply_local_model_scores(candidates, source_audio, sr, style, use_local_models)
        ranker = TasteRanker()
        _apply_taste_and_intent(candidates, ranker, comment_intent)
        best = next(candidate for candidate in candidates if candidate["name"] == "apollo_restored")
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
            "model": None,
            "source_metrics": source_metrics,
            "restoration": restoration_report,
            "local_model_scoring": local_model_report,
            "best_candidate": best["name"],
            "best_path": str(best_output),
            "best_reason": "apollo-only restoration test",
            "ai_rounds": [],
            "candidates": candidates,
        }
        return finalize_ai_report(report, json_out)

    settings_catalog = apply_intent_to_settings(candidate_settings(style), comment_intent)
    settings_by_name: dict[str, MasteringSettings] = {}
    for settings in settings_catalog:
        settings_by_name[settings.name] = settings
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
    for engine, restored_path, restored_audio, restored_sr in restored_sources:
        restored_settings = _restored_candidate_settings(settings_catalog, engine)
        for settings in restored_settings:
            settings_by_name[settings.name] = settings
        candidates.extend(
            _render_restored_candidates(
                restored_path,
                restored_audio,
                restored_sr,
                source_metrics,
                out_dir,
                basename,
                target_lufs,
                settings_catalog,
                max(1, min(jobs, len(restored_settings) or 1)),
                engine,
            )
        )

    local_model_report = apply_local_model_scores(candidates, source_audio, sr, style, use_local_models)

    ranker = TasteRanker()
    _apply_taste_and_intent(candidates, ranker, comment_intent)
    if ranker.available:
        print(f"  [ai-master] Taste ranker applied to {len(candidates)} candidates")

    ai_rounds: list[dict[str, Any]] = []
    for round_index in range(max(0, rounds)):
        if not use_ai:
            break
        ai_result = _call_openai_judge(source_audio, sr, source_metrics, candidates, style, model)
        if not ai_result:
            break
        ai_rounds.append(ai_result)
        if ai_result.get("error"):
            break

        suggested = ai_result.get("suggested_settings") or {}
        if not isinstance(suggested, dict) or not suggested:
            break
        base_name = ai_result.get("best_candidate")
        base_settings = settings_by_name.get(base_name) or settings_by_name.get(_best_candidate(source_metrics, candidates)["name"])
        if not base_settings:
            base_settings = settings_catalog[0]
        refined = bounded_settings(
            base_settings,
            f"ai_refined_{round_index + 1}",
            f"AI-refined from {base_settings.name}",
            suggested,
        )
        settings_by_name[refined.name] = refined
        candidates.append(_render_candidate(source_audio, sr, source_metrics, out_dir, basename, target_lufs, refined))
        local_model_report = apply_local_model_scores(candidates, source_audio, sr, style, use_local_models)
        _apply_taste_and_intent(candidates, ranker, comment_intent)

    metric_best = _best_candidate(source_metrics, candidates)
    ai_preference = None
    if ai_rounds and not ai_rounds[-1].get("error"):
        preferred_name = ai_rounds[-1].get("best_candidate")
        ai_preference = next((candidate for candidate in candidates if candidate["name"] == preferred_name), None)

    if ai_preference and _candidate_passes_release_guards(source_metrics, ai_preference):
        best = ai_preference
    else:
        best = metric_best

    best_output = out_dir / f"{basename}_ai_best.wav"
    shutil.copy2(best["path"], best_output)
    best_reason = "AI preference passed release guards" if best is ai_preference else "highest guarded metric score"
    report = {
        "input": str(input_path),
        "out_dir": str(out_dir),
        "basename": basename,
        "style": style,
        "comment_intent": comment_intent.to_dict(),
        "target_lufs": target_lufs,
        "jobs": max(1, jobs),
        "model": model if use_ai else None,
        "source_metrics": source_metrics,
        "restoration": restoration_report,
        "local_model_scoring": local_model_report,
        "best_candidate": best["name"],
        "best_path": str(best_output),
        "best_reason": best_reason,
        "ai_rounds": ai_rounds,
        "candidates": candidates,
    }

    return finalize_ai_report(report, json_out)
