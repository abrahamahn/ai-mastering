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

from ..audio.analysis import (
    measure_band_correlation,
    measure_band_crest_factor,
    measure_band_db,
    measure_band_side_to_mid_db,
    measure_crest_factor,
    measure_hf_ratio,
    measure_integrated_lufs,
    measure_loudest_window,
    measure_sample_peak_dbfs,
    measure_side_to_mid_db,
    measure_stereo_correlation,
    measure_true_peak_dbfs,
)
from .chain import process
from .intent import apply_intent_score_bias, apply_intent_to_settings, parse_comment_intent
from .report_html import write_ai_html_report
from .render import STREAMING_REFERENCE_LUFS, _match_lufs_with_peak_guard, _resolve_effective_target
from .settings import MasteringSettings, bounded_settings, candidate_settings
from ..audio.source_match import restore_source_balance
from ..models.local_scorer import apply_local_model_scores
from ..history.ranker import TasteRanker
from ..restoration.apollo import restore_with_apollo


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_") or "candidate"


def _window_crest_stats(audio: np.ndarray, sr: int) -> dict[str, float]:
    loud_section = measure_loudest_window(audio, sr, seconds=8.0)
    return {
        "loud_window_crest_db": loud_section["crest_db"],
        "loud_window_rms_dbfs": loud_section["rms_dbfs"],
        "loud_section_start_seconds": loud_section["start_seconds"],
        "loud_section_end_seconds": loud_section["end_seconds"],
        "loud_section_peak_dbfs": loud_section["peak_dbfs"],
    }


def _metrics(audio: np.ndarray, sr: int) -> dict[str, float]:
    sub_db = measure_band_db(audio, sr, 25.0, 120.0)
    punch_db = measure_band_db(audio, sr, 60.0, 120.0)
    mud_db = measure_band_db(audio, sr, 180.0, 350.0)
    low_mid_db = measure_band_db(audio, sr, 180.0, 500.0)
    presence_db = measure_band_db(audio, sr, 500.0, 3000.0)
    vocal_presence_db = measure_band_db(audio, sr, 1500.0, 4000.0)
    upper_presence_db = measure_band_db(audio, sr, 3000.0, 8000.0)
    harsh_db = measure_band_db(audio, sr, 4000.0, 8000.0)
    air_db = measure_band_db(audio, sr, 8000.0, min(16000.0, sr * 0.45))
    fizz_db = measure_band_db(audio, sr, 8000.0, min(14000.0, sr * 0.45))
    lufs = measure_integrated_lufs(audio, sr)
    true_peak = measure_true_peak_dbfs(audio)
    high_side_to_mid_db = measure_band_side_to_mid_db(audio, sr, 6000.0, min(14000.0, sr * 0.45))
    presence_side_to_mid_db = measure_band_side_to_mid_db(audio, sr, 2000.0, 6000.0)
    high_band_correlation = measure_band_correlation(audio, sr, 6000.0, min(14000.0, sr * 0.45))
    hf_crest_db = measure_band_crest_factor(audio, sr, 4000.0, min(14000.0, sr * 0.45))
    metrics = {
        "lufs": lufs,
        "true_peak_dbfs": true_peak,
        "sample_peak_dbfs": measure_sample_peak_dbfs(audio),
        "plr_db": true_peak - lufs,
        "crest_factor_db": measure_crest_factor(audio),
        "stereo_correlation": measure_stereo_correlation(audio),
        "side_to_mid_db": measure_side_to_mid_db(audio),
        "sub_db": sub_db,
        "punch_db": punch_db,
        "mud_db": mud_db,
        "punch_to_mud_db": punch_db - mud_db,
        "low_mid_db": low_mid_db,
        "presence_db": presence_db,
        "vocal_presence_db": vocal_presence_db,
        "upper_presence_db": upper_presence_db,
        "harsh_db": harsh_db,
        "harsh_to_vocal_db": harsh_db - vocal_presence_db,
        "air_db": air_db,
        "fizz_db": fizz_db,
        "fizz_to_vocal_db": fizz_db - vocal_presence_db,
        "air_to_presence_db": air_db - presence_db,
        "upper_to_presence_db": upper_presence_db - presence_db,
        "high_side_to_mid_db": high_side_to_mid_db,
        "presence_side_to_mid_db": presence_side_to_mid_db,
        "high_band_correlation": high_band_correlation,
        "hf_crest_db": hf_crest_db,
        "artifact_index": (
            max(0.0, harsh_db - vocal_presence_db)
            + max(0.0, fizz_db - vocal_presence_db)
            + max(0.0, high_side_to_mid_db + 8.0) * 0.35
            + max(0.0, hf_crest_db - 12.0) * 0.25
            + max(0.0, -high_band_correlation) * 4.0
        ),
        "hf_ratio": measure_hf_ratio(audio, sr, threshold_hz=8000.0),
    }
    metrics.update(_window_crest_stats(audio, sr))
    return metrics


def _source_is_harsh(metrics: dict[str, float]) -> bool:
    return (
        metrics["hf_ratio"] > 0.22
        or metrics["air_to_presence_db"] > 0.35
        or metrics["upper_to_presence_db"] > 1.8
    )


def _streaming_gain_db(metrics: dict[str, float]) -> float:
    """Pessimistic down-only normalization gain for playback comparison."""
    return min(0.0, STREAMING_REFERENCE_LUFS - metrics["lufs"])


def _normalized_band_delta(
    source_metrics: dict[str, float],
    candidate_metrics: dict[str, float],
    key: str,
) -> float:
    return (
        candidate_metrics[key]
        + _streaming_gain_db(candidate_metrics)
        - source_metrics[key]
        - _streaming_gain_db(source_metrics)
    )


def _commercial_pop_score(source_metrics: dict[str, float], candidate_metrics: dict[str, float]) -> float:
    """Reward pop/EDM release qualities after streaming-style normalization."""
    score = 0.0

    turn_down_db = max(0.0, candidate_metrics["lufs"] - STREAMING_REFERENCE_LUFS)
    if 0.0 <= turn_down_db <= 1.5:
        score += 1.0
    elif turn_down_db > 2.5:
        score -= min(3.5, (turn_down_db - 2.5) * 0.8)

    side_delta = candidate_metrics["side_to_mid_db"] - source_metrics["side_to_mid_db"]
    if side_delta > -0.35:
        score += 1.2
    else:
        score -= 2.0

    presence_delta = _normalized_band_delta(source_metrics, candidate_metrics, "presence_db")
    if presence_delta > -0.4:
        score += 1.2
    else:
        score -= 2.0

    sub_delta = _normalized_band_delta(source_metrics, candidate_metrics, "sub_db")
    if 0.4 <= sub_delta <= 2.4:
        score += 1.3
    elif sub_delta > 3.2:
        score -= 1.5

    air_delta = _normalized_band_delta(source_metrics, candidate_metrics, "air_db")
    if _source_is_harsh(source_metrics):
        if -5.0 <= air_delta <= -0.7:
            score += 1.0
        elif air_delta > -0.2:
            score -= 1.8
    else:
        if -0.5 <= air_delta <= 1.5:
            score += 0.8
        elif air_delta > 2.0:
            score -= 1.5

    crest_reduction = source_metrics["crest_factor_db"] - candidate_metrics["crest_factor_db"]
    if crest_reduction <= 3.0:
        score += 0.8
    else:
        score -= 1.5

    return float(score)


def _audible_polish_score(source_metrics: dict[str, float], candidate_metrics: dict[str, float]) -> float:
    """Reward safe differences that should be obvious after level matching."""
    score = 0.0
    normalized_presence_delta = _normalized_band_delta(source_metrics, candidate_metrics, "presence_db")
    normalized_low_mid_delta = _normalized_band_delta(source_metrics, candidate_metrics, "low_mid_db")
    normalized_sub_delta = _normalized_band_delta(source_metrics, candidate_metrics, "sub_db")
    normalized_air_delta = _normalized_band_delta(source_metrics, candidate_metrics, "air_db")
    side_delta = candidate_metrics["side_to_mid_db"] - source_metrics["side_to_mid_db"]
    crest_reduction = source_metrics["crest_factor_db"] - candidate_metrics["crest_factor_db"]

    if 0.25 <= normalized_low_mid_delta <= 1.8:
        score += min(2.8, normalized_low_mid_delta * 1.4)
    if 0.15 <= normalized_presence_delta <= 1.6:
        score += min(2.2, normalized_presence_delta * 1.1)
    if 0.2 <= normalized_sub_delta <= 2.0:
        score += min(1.8, normalized_sub_delta * 0.8)
    if side_delta >= -0.25:
        score += min(1.8, max(0.0, side_delta + 0.25) * 1.2)
    if 0.2 <= crest_reduction <= 1.6:
        score += min(2.0, crest_reduction * 1.1)
    if _source_is_harsh(source_metrics) and -4.5 <= normalized_air_delta <= -0.4:
        score += min(2.5, abs(normalized_air_delta) * 0.8)

    if crest_reduction > 2.2:
        score -= min(4.0, (crest_reduction - 2.2) * 2.0)
    if normalized_air_delta > 0.3:
        score -= min(4.0, normalized_air_delta * 2.0)

    return float(np.clip(score, -4.0, 10.0))


def _harshness_adjustment(source_metrics: dict[str, float], candidate_metrics: dict[str, float]) -> float:
    """Reward necessary de-harshing and always punish added digital edge."""
    score = 0.0
    air_delta = candidate_metrics["air_db"] - source_metrics["air_db"]
    upper_delta = candidate_metrics["upper_presence_db"] - source_metrics["upper_presence_db"]
    hf_delta = candidate_metrics["hf_ratio"] - source_metrics["hf_ratio"]
    presence_delta = candidate_metrics["presence_db"] - source_metrics["presence_db"]
    source_harsh = _source_is_harsh(source_metrics)

    if source_harsh and -5.0 <= air_delta <= -0.7:
        score += min(7.0, abs(air_delta) * 2.1)
    elif air_delta > 0.2:
        score -= min(8.0, air_delta * 2.5)
    elif air_delta < -6.0:
        score -= min(6.0, abs(air_delta + 6.0) * 1.5)

    if source_harsh and -4.0 <= upper_delta <= -0.5:
        score += min(5.0, abs(upper_delta) * 1.6)
    elif upper_delta < -5.0:
        score -= min(5.0, abs(upper_delta + 5.0) * 1.2)
    elif upper_delta > 0.3:
        score -= min(5.0, upper_delta * 1.5)

    if source_harsh and hf_delta < -0.015:
        score += min(5.0, abs(hf_delta) * 75.0)
    elif hf_delta > 0.01:
        score -= min(6.0, hf_delta * 90.0)

    # On harsh sources, _score_candidate already exempts up to -1.5 dB presence loss.
    # Avoid double-penalizing the same beneficial reduction here.
    if presence_delta < -0.9:
        if not source_harsh:
            score -= min(8.0, abs(presence_delta) * 4.0)
        elif presence_delta < -2.5:
            score -= min(4.0, abs(presence_delta + 2.5) * 2.5)

    return float(np.clip(score, -10.0, 12.0))


def _musical_restoration_score(
    source_metrics: dict[str, float],
    candidate_metrics: dict[str, float],
) -> tuple[float, list[str]]:
    """Reward the actual target: musical color, punch, width, and AI-artifact reduction."""
    score = 0.0
    notes: list[str] = []

    punch_delta = candidate_metrics["punch_to_mud_db"] - source_metrics["punch_to_mud_db"]
    low_mid_delta = _normalized_band_delta(source_metrics, candidate_metrics, "low_mid_db")
    vocal_delta = _normalized_band_delta(source_metrics, candidate_metrics, "vocal_presence_db")
    harsh_delta = candidate_metrics["harsh_to_vocal_db"] - source_metrics["harsh_to_vocal_db"]
    fizz_delta = candidate_metrics["fizz_to_vocal_db"] - source_metrics["fizz_to_vocal_db"]
    artifact_delta = candidate_metrics["artifact_index"] - source_metrics["artifact_index"]
    presence_width_delta = candidate_metrics["presence_side_to_mid_db"] - source_metrics["presence_side_to_mid_db"]
    high_width_delta = candidate_metrics["high_side_to_mid_db"] - source_metrics["high_side_to_mid_db"]
    high_corr_delta = candidate_metrics["high_band_correlation"] - source_metrics["high_band_correlation"]
    plr_delta = candidate_metrics["plr_db"] - source_metrics["plr_db"]
    loud_crest_delta = candidate_metrics["loud_window_crest_db"] - source_metrics["loud_window_crest_db"]

    if 0.25 <= punch_delta <= 2.4:
        reward = min(7.0, punch_delta * 2.8)
        score += reward
        notes.append(f"punch/mud balance improved {punch_delta:+.2f} dB")
    elif punch_delta > 3.2:
        score -= min(5.0, (punch_delta - 3.2) * 2.0)
        notes.append(f"punch tilt may be exaggerated {punch_delta:+.2f} dB")

    if 0.15 <= low_mid_delta <= 1.6:
        reward = min(6.0, low_mid_delta * 2.5)
        score += reward
        notes.append(f"analog warmth/low-mid body {low_mid_delta:+.2f} dB")
    elif low_mid_delta > 2.3:
        score -= min(6.0, (low_mid_delta - 2.3) * 3.0)
        notes.append(f"low-mid warmth risks mud {low_mid_delta:+.2f} dB")

    if -0.35 <= vocal_delta <= 1.4:
        score += min(5.0, max(0.0, vocal_delta + 0.35) * 1.8)
    elif vocal_delta < -0.8:
        score -= min(10.0, abs(vocal_delta + 0.8) * 5.0)
        notes.append(f"vocal/emotional presence lost {vocal_delta:+.2f} dB")

    if -4.0 <= harsh_delta <= -0.35:
        reward = min(8.0, abs(harsh_delta) * 2.2)
        score += reward
        notes.append(f"harsh/vocal ratio improved {harsh_delta:+.2f} dB")
    elif harsh_delta > 0.25:
        score -= min(8.0, harsh_delta * 2.5)
        notes.append(f"harshness increased {harsh_delta:+.2f} dB")

    if -4.5 <= fizz_delta <= -0.35:
        reward = min(7.0, abs(fizz_delta) * 1.8)
        score += reward
        notes.append(f"AI fizz/shimmer reduced {fizz_delta:+.2f} dB")
    elif fizz_delta > 0.25:
        score -= min(8.0, fizz_delta * 2.2)
        notes.append(f"AI fizz/shimmer increased {fizz_delta:+.2f} dB")

    if artifact_delta < -0.25:
        reward = min(9.0, abs(artifact_delta) * 1.4)
        score += reward
        notes.append(f"artifact index improved {artifact_delta:+.2f}")
    elif artifact_delta > 0.4:
        score -= min(10.0, artifact_delta * 1.6)
        notes.append(f"artifact index worsened {artifact_delta:+.2f}")

    if 0.2 <= presence_width_delta <= 2.2:
        reward = min(6.0, presence_width_delta * 2.0)
        score += reward
        notes.append(f"presence-band stereo width improved {presence_width_delta:+.2f} dB")
    elif presence_width_delta < -0.7:
        score -= min(8.0, abs(presence_width_delta + 0.7) * 3.0)
        notes.append(f"presence-band image narrowed {presence_width_delta:+.2f} dB")

    # Wide high sides can be desirable, but on Suno artifacts they often mean phasey fizz.
    if source_metrics["high_side_to_mid_db"] > -8.0 and -2.0 <= high_width_delta <= -0.25:
        score += min(4.0, abs(high_width_delta) * 1.3)
        notes.append(f"phasey side-highs stabilized {high_width_delta:+.2f} dB")
    elif high_width_delta > 2.0:
        score -= min(6.0, (high_width_delta - 2.0) * 2.0)
        notes.append(f"side-high widening may expose artifacts {high_width_delta:+.2f} dB")

    if source_metrics["high_band_correlation"] < -0.05 and high_corr_delta > 0.05:
        score += min(5.0, high_corr_delta * 8.0)
        notes.append(f"high-band phase correlation improved {high_corr_delta:+.3f}")
    if candidate_metrics["high_band_correlation"] < -0.18:
        score -= min(7.0, abs(candidate_metrics["high_band_correlation"] + 0.18) * 10.0)
        notes.append(f"high-band phase remains unstable {candidate_metrics['high_band_correlation']:+.3f}")

    if plr_delta >= -0.5:
        score += min(4.0, (plr_delta + 0.5) * 1.2)
    elif plr_delta < -1.2:
        score -= min(8.0, abs(plr_delta + 1.2) * 4.0)
        notes.append(f"peak-loudness ratio reduced {plr_delta:+.2f} dB")

    if loud_crest_delta >= -0.45:
        score += min(4.0, (loud_crest_delta + 0.45) * 1.5)
    elif loud_crest_delta < -1.0:
        score -= min(8.0, abs(loud_crest_delta + 1.0) * 4.0)
        notes.append(f"loudest section got less dynamic {loud_crest_delta:+.2f} dB")

    return float(np.clip(score, -24.0, 42.0)), notes


def _score_candidate(source_metrics: dict[str, float], candidate_metrics: dict[str, float], target_lufs: float) -> tuple[float, list[str]]:
    score = 100.0
    notes: list[str] = []
    source_harsh = _source_is_harsh(source_metrics)

    presence_delta = candidate_metrics["presence_db"] - source_metrics["presence_db"]
    side_delta = candidate_metrics["side_to_mid_db"] - source_metrics["side_to_mid_db"]
    corr_delta = candidate_metrics["stereo_correlation"] - source_metrics["stereo_correlation"]
    sub_delta = candidate_metrics["sub_db"] - source_metrics["sub_db"]
    crest_reduction = source_metrics["crest_factor_db"] - candidate_metrics["crest_factor_db"]
    loud_window_crest_delta = candidate_metrics["loud_window_crest_db"] - source_metrics["loud_window_crest_db"]
    lufs_gain = candidate_metrics["lufs"] - source_metrics["lufs"]
    streaming_turn_down_db = max(0.0, candidate_metrics["lufs"] - STREAMING_REFERENCE_LUFS)
    normalized_presence_delta = _normalized_band_delta(source_metrics, candidate_metrics, "presence_db")
    normalized_low_mid_delta = _normalized_band_delta(source_metrics, candidate_metrics, "low_mid_db")
    normalized_air_delta = _normalized_band_delta(source_metrics, candidate_metrics, "air_db")

    # On harsh sources, presence reduction up to 1.5 dB is de-harshing, not damage.
    if presence_delta < -0.4:
        if source_harsh and presence_delta >= -1.5:
            pass  # desired de-harshing; no penalty
        elif source_harsh:
            penalty = min(20.0, abs(presence_delta + 1.5) * 8.0)
            score -= penalty
            notes.append(f"excessive presence loss on harsh source {presence_delta:+.2f} dB")
        else:
            penalty = min(30.0, abs(presence_delta) * 10.0)
            score -= penalty
            notes.append(f"presence loss {presence_delta:+.2f} dB")
    elif presence_delta > 0.2:
        score += min(4.0, presence_delta * 1.5)

    if side_delta < -0.35:
        penalty = min(25.0, abs(side_delta) * 9.0)
        score -= penalty
        notes.append(f"side energy loss {side_delta:+.2f} dB")
    elif side_delta > 0.15:
        score += min(4.0, side_delta * 2.0)

    if corr_delta > 0.025:
        penalty = min(22.0, corr_delta * 180.0)
        score -= penalty
        notes.append(f"stereo correlation increased {corr_delta:+.3f}")

    if sub_delta > 0.8:
        penalty = min(18.0, (sub_delta - 0.8) * 8.0)
        score -= penalty
        notes.append(f"sub/bass lift {sub_delta:+.2f} dB")

    # Same context-aware treatment for normalized presence: exempt up to -1.2 dB on harsh sources.
    if normalized_presence_delta < -0.6:
        if source_harsh and normalized_presence_delta >= -1.2:
            pass  # desired de-harshing at streaming-normalized level
        elif source_harsh:
            penalty = min(14.0, abs(normalized_presence_delta + 1.2) * 5.0)
            score -= penalty
            notes.append(f"excessive normalized presence loss on harsh source {normalized_presence_delta:+.2f} dB")
        else:
            penalty = min(18.0, abs(normalized_presence_delta) * 6.0)
            score -= penalty
            notes.append(f"normalized presence loss {normalized_presence_delta:+.2f} dB")
    elif normalized_presence_delta > 0.1:
        score += min(5.0, normalized_presence_delta * 2.0)

    if 0.25 <= normalized_low_mid_delta <= 1.8:
        score += min(5.0, normalized_low_mid_delta * 1.8)
    elif normalized_low_mid_delta > 2.6:
        penalty = min(10.0, (normalized_low_mid_delta - 2.6) * 3.0)
        score -= penalty
        notes.append(f"normalized low-mid excess {normalized_low_mid_delta:+.2f} dB")

    if normalized_air_delta > 0.3:
        penalty = min(14.0, normalized_air_delta * 4.0)
        score -= penalty
        notes.append(f"normalized air/harshness lift {normalized_air_delta:+.2f} dB")

    if crest_reduction > 1.6:
        penalty = min(20.0, (crest_reduction - 1.6) * 5.0)
        score -= penalty
        notes.append(f"crest reduced {crest_reduction:+.2f} dB")

    if loud_window_crest_delta < -1.0:
        penalty = min(18.0, abs(loud_window_crest_delta + 1.0) * 6.0)
        score -= penalty
        notes.append(f"loud-section crest reduced {loud_window_crest_delta:+.2f} dB")
    elif loud_window_crest_delta > -0.3:
        score += min(3.0, (loud_window_crest_delta + 0.3) * 1.5)

    if candidate_metrics["loud_window_crest_db"] < 5.2:
        penalty = min(16.0, (5.2 - candidate_metrics["loud_window_crest_db"]) * 4.0)
        score -= penalty
        notes.append(f"loud-section crest low {candidate_metrics['loud_window_crest_db']:.2f} dB")

    if candidate_metrics["true_peak_dbfs"] > -0.8:
        score -= 12.0
        notes.append(f"true peak too high {candidate_metrics['true_peak_dbfs']:.2f} dBFS")

    # The peak ceiling guard causes a structural miss on all candidates equally when pushing loud
    # targets. Only penalize misses beyond 2.0 dB to avoid uniform punishment that doesn't
    # differentiate between candidates.
    target_miss = abs(candidate_metrics["lufs"] - target_lufs)
    if target_miss > 2.0:
        score -= min(8.0, (target_miss - 2.0) * 2.0)
        notes.append(f"target miss {target_miss:.2f} dB")
    elif target_miss > 0.5:
        score -= min(2.0, target_miss * 0.5)

    if 0.1 <= lufs_gain <= 2.5:
        score += min(4.0, lufs_gain * 1.5)
    elif lufs_gain > 3.0:
        score -= min(10.0, (lufs_gain - 3.0) * 3.0)
        notes.append(f"too much loudness gain {lufs_gain:+.2f} dB")

    if streaming_turn_down_db > 2.5:
        penalty = min(5.0, (streaming_turn_down_db - 2.5) * 0.8)
        score -= penalty
        notes.append(f"streaming turn-down risk {streaming_turn_down_db:.2f} dB")
    elif streaming_turn_down_db <= 0.5 and target_lufs <= STREAMING_REFERENCE_LUFS + 0.5:
        score += 3.0

    commercial = _commercial_pop_score(source_metrics, candidate_metrics) * 3.0
    score += commercial
    if abs(commercial) >= 1.0:
        notes.append(f"commercial pop score {commercial:+.1f}")

    harshness = _harshness_adjustment(source_metrics, candidate_metrics)
    score += harshness
    if abs(harshness) >= 1.0:
        notes.append(f"source harshness adjustment {harshness:+.1f}")

    audible_polish = _audible_polish_score(source_metrics, candidate_metrics)
    score += audible_polish
    if abs(audible_polish) >= 1.0:
        notes.append(f"audible polish score {audible_polish:+.1f}")

    musical, musical_notes = _musical_restoration_score(source_metrics, candidate_metrics)
    score += musical
    if abs(musical) >= 1.0:
        notes.append(f"musical restoration score {musical:+.1f}")
    notes.extend(musical_notes)

    return float(round(score, 3)), notes


def _creative_audibility_bonus(source_metrics: dict[str, float], candidate_metrics: dict[str, float]) -> tuple[float, list[str]]:
    """Reward creative candidates for making audible, controlled moves."""
    notes: list[str] = []
    low_mid = abs(_normalized_band_delta(source_metrics, candidate_metrics, "low_mid_db"))
    vocal = abs(_normalized_band_delta(source_metrics, candidate_metrics, "vocal_presence_db"))
    width = abs(candidate_metrics["side_to_mid_db"] - source_metrics["side_to_mid_db"])
    artifact_drop = max(0.0, source_metrics.get("artifact_index", 0.0) - candidate_metrics.get("artifact_index", 0.0))
    punch = max(0.0, candidate_metrics["punch_to_mud_db"] - source_metrics["punch_to_mud_db"])
    audible_move = low_mid + vocal + width + artifact_drop + punch

    bonus = min(14.0, max(0.0, audible_move - 1.2) * 2.2)
    penalty = 0.0
    if candidate_metrics["loud_window_crest_db"] < 4.8:
        penalty += min(8.0, (4.8 - candidate_metrics["loud_window_crest_db"]) * 4.0)
    if candidate_metrics["true_peak_dbfs"] > -0.6:
        penalty += 8.0
    if bonus >= 1.0:
        notes.append(f"creative audibility bonus {bonus:+.1f}")
    if penalty >= 1.0:
        notes.append(f"creative safety penalty {-penalty:+.1f}")
    return float(bonus - penalty), notes


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


def _candidate_passes_release_guards(source_metrics: dict[str, float], candidate: dict[str, Any]) -> bool:
    if candidate["name"] == "original":
        return True
    metrics = candidate["metrics"]
    settings = candidate.get("settings") or {}
    creative = bool(settings.get("creative_mode"))
    presence_floor = -2.8 if creative else -1.6
    side_floor = -2.2 if creative else -1.6
    corr_ceiling = 0.18 if creative else 0.12
    sub_ceiling = 3.5 if creative else 2.4
    hf_ceiling = 0.06 if creative else 0.03
    artifact_ceiling = 2.8 if creative else 1.5
    high_corr_floor = -0.32 if creative else -0.25
    if metrics["presence_db"] - source_metrics["presence_db"] < presence_floor:
        return False
    if metrics["side_to_mid_db"] - source_metrics["side_to_mid_db"] < side_floor:
        return False
    if metrics["stereo_correlation"] - source_metrics["stereo_correlation"] > corr_ceiling:
        return False
    if metrics["sub_db"] - source_metrics["sub_db"] > sub_ceiling:
        return False
    if metrics["hf_ratio"] - source_metrics["hf_ratio"] > hf_ceiling:
        return False
    if metrics.get("artifact_index", 0.0) - source_metrics.get("artifact_index", 0.0) > artifact_ceiling:
        return False
    if metrics.get("high_band_correlation", 1.0) < high_corr_floor:
        return False
    if not creative and _source_is_harsh(source_metrics) and metrics["air_db"] - source_metrics["air_db"] > -0.2:
        return False
    if (
        source_metrics["loud_window_crest_db"] >= 6.0
        and metrics["loud_window_crest_db"] - source_metrics["loud_window_crest_db"] < -1.8
    ):
        return False
    return True


def _best_candidate(source_metrics: dict[str, float], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    processed = [c for c in candidates if c["name"] != "original"]
    passing_processed = [c for c in processed if _candidate_passes_release_guards(source_metrics, c)]
    if passing_processed:
        return max(passing_processed, key=lambda c: c["score"])
    # All processed candidates failed guards — emergency fallback includes original
    passing_all = [c for c in candidates if _candidate_passes_release_guards(source_metrics, c)]
    return max(passing_all or candidates, key=lambda c: c["score"])


def _apply_taste_and_intent(
    candidates: list[dict[str, Any]],
    ranker: TasteRanker,
    intent: Any,
) -> None:
    if ranker.available:
        for candidate in candidates:
            taste = ranker.score(candidate) * 3.0
            candidate["score"] = float(round(candidate["score"] + taste, 3))
            candidate["taste_score"] = float(round(taste, 3))
            if abs(taste) >= 0.5:
                candidate["score_notes"].append(f"taste ranker {taste:+.2f}")
    apply_intent_score_bias(candidates, intent)


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
        try:
            from ..history.db import HistoryDB
            db = HistoryDB()
            run_id = db.save_run(report)
            db.close()
            report["history_run_id"] = run_id
            print(f"  [ai-master] Run saved to history DB (id={run_id}). "
                  f"To record your preference: master.py prefer {run_id} <candidate_name>")
        except Exception as exc:
            print(f"  [ai-master] WARNING: could not save to history DB: {exc}")

        html_out = json_out.with_suffix(".html") if json_out else out_dir / "ai-mastering-report.html"
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

    try:
        from ..history.db import HistoryDB
        db = HistoryDB()
        run_id = db.save_run(report)
        db.close()
        report["history_run_id"] = run_id
        print(f"  [ai-master] Run saved to history DB (id={run_id}). "
              f"To record your preference: master.py prefer {run_id} <candidate_name>")
    except Exception as exc:
        print(f"  [ai-master] WARNING: could not save to history DB: {exc}")

    html_out = json_out.with_suffix(".html") if json_out else out_dir / "ai-mastering-report.html"
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
