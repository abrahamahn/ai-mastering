"""Source-aware restoration after the plugin polish chain."""
from __future__ import annotations

from typing import Any

import numpy as np
from scipy import signal as scipy_signal

from .analysis import measure_side_to_mid_db


def _band_db(audio: np.ndarray, sr: int, low: float, high: float) -> float:
    mono = audio.mean(axis=0) if audio.ndim > 1 else audio
    nperseg = min(len(mono), 16384)
    freqs, power = scipy_signal.welch(mono, fs=sr, nperseg=nperseg)
    mask = (freqs >= low) & (freqs < high)
    if not np.any(mask):
        return -120.0
    return float(10.0 * np.log10(np.mean(np.maximum(power[mask], 1e-18))))


def _peaking_sos(sr: int, freq: float, q: float, gain_db: float) -> np.ndarray:
    freq = float(np.clip(freq, 20.0, sr * 0.45))
    q = float(np.clip(q, 0.2, 12.0))
    a = 10.0 ** (gain_db / 40.0)
    omega = 2.0 * np.pi * freq / sr
    alpha = np.sin(omega) / (2.0 * q)
    cos_omega = np.cos(omega)

    b0 = 1.0 + alpha * a
    b1 = -2.0 * cos_omega
    b2 = 1.0 - alpha * a
    a0 = 1.0 + alpha / a
    a1 = -2.0 * cos_omega
    a2 = 1.0 - alpha / a

    return np.array([[b0 / a0, b1 / a0, b2 / a0, 1.0, a1 / a0, a2 / a0]], dtype=np.float64)


def _apply_sos(audio: np.ndarray, sos: np.ndarray) -> np.ndarray:
    return scipy_signal.sosfilt(sos, audio.astype(np.float64), axis=-1).astype(np.float32)


def _restore_width(audio: np.ndarray, source: np.ndarray, max_side_gain_db: float) -> tuple[np.ndarray, dict[str, Any]]:
    if audio.ndim < 2 or audio.shape[0] < 2 or source.ndim < 2 or source.shape[0] < 2:
        return audio, {"side_gain_db": 0.0}

    source_side_db = measure_side_to_mid_db(source)
    audio_side_db = measure_side_to_mid_db(audio)
    needed_db = source_side_db - audio_side_db
    side_gain_db = float(np.clip(needed_db, 0.0, max_side_gain_db))
    if side_gain_db <= 0.05:
        return audio, {"side_gain_db": 0.0}

    l, r = audio[0].astype(np.float64), audio[1].astype(np.float64)
    mid = 0.5 * (l + r)
    side = 0.5 * (l - r) * (10.0 ** (side_gain_db / 20.0))
    restored = audio.astype(np.float64, copy=True)
    restored[0] = mid + side
    restored[1] = mid - side
    return restored.astype(np.float32), {"side_gain_db": side_gain_db}


def restore_source_balance(
    audio: np.ndarray,
    source: np.ndarray,
    sr: int,
    presence_max_db: float = 1.2,
    sub_trim_max_db: float = 1.0,
    side_max_db: float = 1.8,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Nudge the polish result back toward the source's presence and width.

    This is intentionally capped. It prevents the chain from making a good
    source darker/narrower while still allowing useful polish to remain.
    """
    result = audio
    moves: list[dict[str, Any]] = []

    source_presence = _band_db(source, sr, 500.0, 3000.0)
    result_presence = _band_db(result, sr, 500.0, 3000.0)
    presence_loss_db = source_presence - result_presence
    if presence_max_db > 0 and presence_loss_db > 0.8:
        gain_db = float(np.clip((presence_loss_db - 0.5) * 0.45, 0.25, presence_max_db))
        result = _apply_sos(result, _peaking_sos(sr, 1600.0, 0.75, gain_db))
        moves.append({"kind": "presence_restore", "frequency_hz": 1600.0, "gain_db": gain_db})

    source_sub = _band_db(source, sr, 25.0, 120.0)
    result_sub = _band_db(result, sr, 25.0, 120.0)
    sub_lift_db = result_sub - source_sub
    if sub_trim_max_db > 0 and sub_lift_db > 1.0:
        gain_db = -float(np.clip((sub_lift_db - 0.6) * 0.35, 0.25, sub_trim_max_db))
        result = _apply_sos(result, _peaking_sos(sr, 75.0, 0.7, gain_db))
        moves.append({"kind": "sub_trim", "frequency_hz": 75.0, "gain_db": gain_db})

    result, width = _restore_width(result, source, side_max_db)
    if width["side_gain_db"] > 0:
        moves.append({"kind": "width_restore", "side_gain_db": width["side_gain_db"]})

    return result, {
        "source_match_moves": moves,
        "presence_loss_db_before_restore": presence_loss_db,
        "sub_lift_db_before_restore": sub_lift_db,
    }
