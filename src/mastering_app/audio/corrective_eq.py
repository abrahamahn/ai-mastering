"""Programmatic corrective EQ driven by per-song spectral analysis."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import signal as scipy_signal


@dataclass(frozen=True)
class EqMove:
    kind: str
    frequency_hz: float
    gain_db: float
    q: float | None
    reason: str


def _mono(audio: np.ndarray) -> np.ndarray:
    return audio.mean(axis=0) if audio.ndim > 1 else audio


def _spectrum(audio: np.ndarray, sr: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mono = _mono(audio)
    nperseg = min(len(mono), 16384)
    if nperseg < 1024:
        nperseg = min(len(mono), 1024)
    freqs, power = scipy_signal.welch(mono, fs=sr, nperseg=nperseg)
    power = np.maximum(power, 1e-18)
    db = 10.0 * np.log10(power)
    return freqs, power, db


def _smooth(values: np.ndarray, bins: int) -> np.ndarray:
    bins = max(3, bins | 1)
    kernel = np.ones(bins, dtype=np.float64) / bins
    return np.convolve(values, kernel, mode="same")


def _band_db(freqs: np.ndarray, power: np.ndarray, low: float, high: float) -> float:
    mask = (freqs >= low) & (freqs < high)
    if not np.any(mask):
        return -120.0
    return float(10.0 * np.log10(np.mean(power[mask]) + 1e-18))


def _peak_frequency(freqs: np.ndarray, power: np.ndarray, low: float, high: float) -> float:
    mask = (freqs >= low) & (freqs < high)
    if not np.any(mask):
        return (low + high) * 0.5
    selected_freqs = freqs[mask]
    selected_power = power[mask]
    return float(selected_freqs[int(np.argmax(selected_power))])


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


def _high_shelf_sos(sr: int, freq: float, gain_db: float, slope: float = 0.8) -> np.ndarray:
    freq = float(np.clip(freq, 1000.0, sr * 0.45))
    a = 10.0 ** (gain_db / 40.0)
    omega = 2.0 * np.pi * freq / sr
    sin_omega = np.sin(omega)
    cos_omega = np.cos(omega)
    alpha = sin_omega / 2.0 * np.sqrt((a + 1.0 / a) * (1.0 / slope - 1.0) + 2.0)
    beta = 2.0 * np.sqrt(a) * alpha

    b0 = a * ((a + 1.0) + (a - 1.0) * cos_omega + beta)
    b1 = -2.0 * a * ((a - 1.0) + (a + 1.0) * cos_omega)
    b2 = a * ((a + 1.0) + (a - 1.0) * cos_omega - beta)
    a0 = (a + 1.0) - (a - 1.0) * cos_omega + beta
    a1 = 2.0 * ((a - 1.0) - (a + 1.0) * cos_omega)
    a2 = (a + 1.0) - (a - 1.0) * cos_omega - beta

    return np.array([[b0 / a0, b1 / a0, b2 / a0, 1.0, a1 / a0, a2 / a0]], dtype=np.float64)


def build_corrective_eq_plan(audio: np.ndarray, sr: int) -> list[EqMove]:
    """Build subtle, channel-linked EQ moves from the source spectrum.

    The goal is corrective mastering EQ, not mix rescue. Moves are intentionally
    capped so this stage does not become the source of muffling or width loss.
    """
    freqs, power, db = _spectrum(audio, sr)
    moves: list[EqMove] = []

    sub_vs_bass = _band_db(freqs, power, 20.0, 55.0) - _band_db(freqs, power, 55.0, 120.0)
    if sub_vs_bass > 4.0:
        moves.append(EqMove("highpass", 28.0, 0.0, None, f"sub energy is {sub_vs_bass:.1f} dB above bass"))

    low_mid_vs_mid = _band_db(freqs, power, 180.0, 420.0) - _band_db(freqs, power, 900.0, 3000.0)
    if low_mid_vs_mid > 8.0:
        freq = _peak_frequency(freqs, power, 180.0, 420.0)
        gain = -float(np.clip((low_mid_vs_mid - 7.0) * 0.16, 0.3, 0.9))
        moves.append(EqMove("bell", freq, gain, 1.1, f"low-mid buildup is {low_mid_vs_mid:.1f} dB above mids"))

    air_vs_presence = _band_db(freqs, power, 8500.0, min(16000.0, sr * 0.45)) - _band_db(
        freqs, power, 2500.0, 7000.0
    )
    if air_vs_presence > 1.0:
        gain = -float(np.clip((air_vs_presence - 1.0) * 0.08, 0.2, 0.6))
        moves.append(EqMove("high_shelf", 9000.0, gain, None, f"air band is {air_vs_presence:.1f} dB above presence"))

    resolution_hz = freqs[1] - freqs[0] if len(freqs) > 1 else 10.0
    smooth_bins = max(7, int(round(180.0 / max(resolution_hz, 1.0))) | 1)
    residual = db - _smooth(db, smooth_bins)
    peak_mask = (freqs >= 250.0) & (freqs <= min(12000.0, sr * 0.45))
    peak_indices = np.flatnonzero(peak_mask)
    if len(peak_indices) > 0:
        distance_bins = max(1, int(round(350.0 / max(resolution_hz, 1.0))))
        peaks, props = scipy_signal.find_peaks(
            residual[peak_indices],
            height=6.5,
            distance=distance_bins,
        )
        if len(peaks) > 0:
            heights = props["peak_heights"]
            strongest = np.argsort(heights)[-3:][::-1]
            for rank in strongest:
                idx = peak_indices[int(peaks[rank])]
                freq = float(freqs[idx])
                prominence = float(heights[rank])
                gain = -float(np.clip((prominence - 5.5) * 0.18, 0.35, 1.3))
                q = float(np.clip(freq / 450.0, 2.0, 7.5))
                moves.append(EqMove("bell", freq, gain, q, f"narrow resonance prominence {prominence:.1f} dB"))

    return moves


def apply_corrective_eq(audio: np.ndarray, sr: int, moves: list[EqMove]) -> np.ndarray:
    if not moves:
        return audio

    processed = audio.astype(np.float64, copy=True)
    for move in moves:
        if move.kind == "highpass":
            sos = scipy_signal.butter(2, move.frequency_hz, btype="highpass", fs=sr, output="sos")
        elif move.kind == "high_shelf":
            sos = _high_shelf_sos(sr, move.frequency_hz, move.gain_db)
        elif move.kind == "bell":
            sos = _peaking_sos(sr, move.frequency_hz, move.q or 1.0, move.gain_db)
        else:
            continue
        processed = scipy_signal.sosfilt(sos, processed, axis=-1)

    return processed.astype(np.float32, copy=False)
