from __future__ import annotations

import numpy as np

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
from .render import STREAMING_REFERENCE_LUFS


def window_crest_stats(audio: np.ndarray, sr: int) -> dict[str, float]:
    loud_section = measure_loudest_window(audio, sr, seconds=8.0)
    return {
        "loud_window_crest_db": loud_section["crest_db"],
        "loud_window_rms_dbfs": loud_section["rms_dbfs"],
        "loud_section_start_seconds": loud_section["start_seconds"],
        "loud_section_end_seconds": loud_section["end_seconds"],
        "loud_section_peak_dbfs": loud_section["peak_dbfs"],
    }


def collect_metrics(audio: np.ndarray, sr: int) -> dict[str, float]:
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
    metrics.update(window_crest_stats(audio, sr))
    return metrics


def source_is_harsh(metrics: dict[str, float]) -> bool:
    return (
        metrics["hf_ratio"] > 0.22
        or metrics["air_to_presence_db"] > 0.35
        or metrics["upper_to_presence_db"] > 1.8
    )


def streaming_gain_db(metrics: dict[str, float]) -> float:
    """Pessimistic down-only normalization gain for playback comparison."""
    return min(0.0, STREAMING_REFERENCE_LUFS - metrics["lufs"])


def normalized_band_delta(
    source_metrics: dict[str, float],
    candidate_metrics: dict[str, float],
    key: str,
) -> float:
    return (
        candidate_metrics[key]
        + streaming_gain_db(candidate_metrics)
        - source_metrics[key]
        - streaming_gain_db(source_metrics)
    )
