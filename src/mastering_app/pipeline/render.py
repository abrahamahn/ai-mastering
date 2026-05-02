from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

from ..audio.analysis import (
    measure_integrated_lufs,
    measure_loudest_window,
    measure_sample_peak_dbfs,
    measure_side_to_mid_db,
    measure_stereo_correlation,
    measure_true_peak_dbfs,
    resolve_loud_section_crest_floor,
)
from .chain import process
from .settings import DEFAULT_SETTINGS, MasteringSettings
from ..audio.source_match import restore_source_balance

TRUE_PEAK_CEILING_DBFS = -1.0
LOUD_MASTER_TRUE_PEAK_CEILING_DBFS = -2.0
STREAMING_REFERENCE_LUFS = -14.0
LUFS_TOLERANCE_DB = 0.25
MAX_POLISH_PRESERVE_LUFS = -12.0
LOUD_SECTION_SECONDS = 8.0
LOUD_SECTION_MIN_CREST_DB = 5.8
LOUD_SECTION_MAX_CREST_LOSS_DB = 1.0


def parse_targets(raw: str) -> list[float]:
    targets: list[float] = []
    for part in raw.split(','):
        value = float(part.strip())
        if value >= 0 or value < -30:
            raise ValueError(f"Invalid LUFS target: {value}")
        if value not in targets:
            targets.append(value)
    if not targets:
        raise ValueError("At least one LUFS target is required")
    return targets


def _target_label(target_lufs: float) -> str:
    text = f"{target_lufs:g}".replace('-', 'minus_').replace('.', '_')
    return text


def _gain(audio: np.ndarray, db: float) -> np.ndarray:
    return audio * (10.0 ** (db / 20.0))


def _streaming_peak_ceiling(target_lufs: float) -> float:
    """Use safer headroom for masters intentionally louder than normalization."""
    return LOUD_MASTER_TRUE_PEAK_CEILING_DBFS if target_lufs > STREAMING_REFERENCE_LUFS else TRUE_PEAK_CEILING_DBFS


def _resolve_effective_target(requested_lufs: float, source_lufs: float) -> tuple[float, str | None]:
    """Avoid making already-finished sources quieter in the default polish path."""
    if source_lufs <= requested_lufs:
        return requested_lufs, None

    preserved = min(source_lufs, MAX_POLISH_PRESERVE_LUFS)
    if preserved > requested_lufs:
        return preserved, (
            f"requested {requested_lufs:.1f} LUFS would reduce loudness; "
            f"using streaming-aware polish target {preserved:.1f} LUFS"
        )
    return requested_lufs, None


def _stereo_metrics(audio: np.ndarray) -> dict[str, float]:
    return {
        "stereo_correlation": measure_stereo_correlation(audio),
        "side_to_mid_db": measure_side_to_mid_db(audio),
    }


def _match_lufs_with_peak_guard(
    audio: np.ndarray,
    sr: int,
    target_lufs: float,
    source_loud_section_crest_db: float | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    lufs = measure_integrated_lufs(audio, sr)
    true_peak = measure_true_peak_dbfs(audio, sr)
    delta = target_lufs - lufs
    warnings: list[str] = []
    loud_section = measure_loudest_window(audio, sr, LOUD_SECTION_SECONDS)
    true_peak_ceiling = _streaming_peak_ceiling(target_lufs)

    if true_peak > true_peak_ceiling:
        applied = true_peak_ceiling - true_peak
    elif abs(delta) <= LUFS_TOLERANCE_DB:
        applied = 0.0
    elif delta > 0:
        allowed_boost = true_peak_ceiling - true_peak
        applied = float(np.clip(min(delta, allowed_boost), 0.0, 6.0))
    else:
        applied = float(np.clip(delta, -6.0, 0.0))

    if source_loud_section_crest_db is not None and applied > 0.0:
        crest_floor = resolve_loud_section_crest_floor(
            source_loud_section_crest_db,
            LOUD_SECTION_MIN_CREST_DB,
            LOUD_SECTION_MAX_CREST_LOSS_DB,
        )
        max_gain_for_loud_section = true_peak_ceiling - crest_floor - loud_section["rms_dbfs"]
        if applied > max_gain_for_loud_section:
            previous = applied
            applied = float(np.clip(max_gain_for_loud_section, 0.0, applied))
            warnings.append(
                "post-chain gain capped by loud-section guard: "
                f"{previous:+.2f} -> {applied:+.2f} dB "
                f"(loud section {loud_section['start_seconds']:.1f}-{loud_section['end_seconds']:.1f}s)"
            )

    if abs(applied) > 0.01:
        audio = _gain(audio, applied)

    final_lufs = measure_integrated_lufs(audio, sr)
    final_true_peak = measure_true_peak_dbfs(audio, sr)
    final_sample_peak = measure_sample_peak_dbfs(audio)

    if abs(final_lufs - target_lufs) > LUFS_TOLERANCE_DB:
        warnings.append(
            f"LUFS target missed by {final_lufs - target_lufs:+.2f} dB because of peak ceiling guard"
        )
    if final_true_peak > true_peak_ceiling + 0.1:
        warnings.append(f"true peak exceeds ceiling: {final_true_peak:.2f} dBFS")

    return audio, {
        "target_lufs": target_lufs,
        "true_peak_ceiling_dbfs": true_peak_ceiling,
        "pre_guard_lufs": lufs,
        "pre_guard_true_peak_dbfs": true_peak,
        "pre_guard_loud_section": loud_section,
        "guard_gain_db": applied,
        "final_lufs": final_lufs,
        "final_true_peak_dbfs": final_true_peak,
        "final_sample_peak_dbfs": final_sample_peak,
        "warnings": warnings,
    }


def render_targets(
    input_path: Path,
    out_dir: Path,
    basename: str,
    targets: list[float],
    settings: MasteringSettings | None = None,
) -> dict[str, Any]:
    settings = settings or DEFAULT_SETTINGS
    if not input_path.exists():
        raise FileNotFoundError(f"Input WAV not found: {input_path}")

    out_dir.mkdir(parents=True, exist_ok=True)
    original_path = out_dir / f"{basename}_original.wav"
    shutil.copy2(input_path, original_path)

    audio, sr = sf.read(str(input_path), dtype='float32', always_2d=True)
    audio = audio.T
    source_lufs = measure_integrated_lufs(audio, sr)
    source_true_peak = measure_true_peak_dbfs(audio, sr)
    source_sample_peak = measure_sample_peak_dbfs(audio)
    source_stereo = _stereo_metrics(audio)
    source_loud_section = measure_loudest_window(audio, sr, LOUD_SECTION_SECONDS)

    masters: list[dict[str, Any]] = []
    for index, requested_target in enumerate(targets):
        role = "primary" if index == 0 else "alt"
        effective_target, target_note = _resolve_effective_target(requested_target, source_lufs)
        output_name = (
            f"{basename}_mastered.wav"
            if index == 0
            else f"{basename}_mastered_{_target_label(requested_target)}.wav"
        )
        output_path = out_dir / output_name

        if target_note:
            print(f"[master] Rendering {role} target {requested_target:.1f} LUFS -> {effective_target:.1f} LUFS")
        else:
            print(f"[master] Rendering {role} target {effective_target:.1f} LUFS")
        mastered = process(audio.copy(), sr, effective_target, settings=settings)
        if settings.source_match_enabled:
            mastered, source_match = restore_source_balance(
                mastered,
                audio,
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
            source_loud_section["crest_db"],
        )
        mastered_stereo = _stereo_metrics(mastered)
        correlation_delta = mastered_stereo["stereo_correlation"] - source_stereo["stereo_correlation"]
        side_to_mid_delta_db = mastered_stereo["side_to_mid_db"] - source_stereo["side_to_mid_db"]

        if target_note:
            qc["warnings"].append(target_note)
        if effective_target > -8.0:
            qc["warnings"].append(
                "target is louder than -8 LUFS; expect reduced depth, punch, and stereo image"
            )
        if correlation_delta > 0.12:
            qc["warnings"].append(
                f"stereo correlation increased by {correlation_delta:+.2f}; image may be narrower"
            )
        if side_to_mid_delta_db < -1.5:
            qc["warnings"].append(
                f"side/mid energy dropped by {side_to_mid_delta_db:+.2f} dB; image may be narrower"
            )

        sf.write(str(output_path), mastered.T, sr, subtype='PCM_24')
        masters.append({
            "role": role,
            "requested_target_lufs": requested_target,
            "target_lufs": effective_target,
            "path": str(output_path),
            "file": output_name,
            **qc,
            "settings": settings.to_dict(),
            **source_match,
            "input_stereo_correlation": source_stereo["stereo_correlation"],
            "final_stereo_correlation": mastered_stereo["stereo_correlation"],
            "stereo_correlation_delta": correlation_delta,
            "input_side_to_mid_db": source_stereo["side_to_mid_db"],
            "final_side_to_mid_db": mastered_stereo["side_to_mid_db"],
            "side_to_mid_delta_db": side_to_mid_delta_db,
        })

    return {
        "input": str(input_path),
        "out_dir": str(out_dir),
        "basename": basename,
        "original": str(original_path),
        "source_lufs": source_lufs,
        "source_true_peak_dbfs": source_true_peak,
        "source_sample_peak_dbfs": source_sample_peak,
        "source_stereo_correlation": source_stereo["stereo_correlation"],
        "source_side_to_mid_db": source_stereo["side_to_mid_db"],
        "source_loud_section": source_loud_section,
        "masters": masters,
    }


def write_report(report: dict[str, Any], output_path: Path | None) -> None:
    text = json.dumps(report, indent=2)
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding='utf-8')
    print(text)
