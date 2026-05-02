"""Audio preparation utilities for local model inference."""
from __future__ import annotations

from math import gcd
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import signal as scipy_signal


SUPPORTED_AUDIO_EXTS = {".wav", ".aif", ".aiff", ".flac", ".mp3", ".m4a"}


def load_audio(path: str | Path) -> tuple[np.ndarray, int]:
    audio, sr = sf.read(str(path), dtype="float32", always_2d=True)
    return audio.T, sr


def mono_clip(audio: np.ndarray, sr: int, seconds: float) -> np.ndarray:
    mono = audio.mean(axis=0) if audio.ndim > 1 else audio
    samples = int(seconds * sr)
    if samples <= 0 or mono.shape[-1] <= samples:
        return mono.astype(np.float32, copy=False)

    hop = max(sr, samples // 4)
    best_start = 0
    best_rms = -1.0
    for start in range(0, mono.shape[-1] - samples, hop):
        segment = mono[start:start + samples]
        rms = float(np.sqrt(np.mean(segment ** 2)))
        if rms > best_rms:
            best_rms = rms
            best_start = start
    return mono[best_start:best_start + samples].astype(np.float32, copy=False)


def resample_mono(audio: np.ndarray, sr: int, target_sr: int, seconds: float) -> np.ndarray:
    clip = mono_clip(audio, sr, seconds)
    if sr == target_sr:
        return clip
    factor = gcd(sr, target_sr)
    return scipy_signal.resample_poly(clip, target_sr // factor, sr // factor).astype(np.float32, copy=False)


def iter_reference_audio(reference_dir: Path | None) -> list[Path]:
    if reference_dir is None or not reference_dir.exists():
        return []
    return sorted(
        path
        for path in reference_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_AUDIO_EXTS
    )

