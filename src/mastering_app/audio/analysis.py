"""Signal analysis helpers — called before each plugin stage."""
import numpy as np
import pyloudnorm as pyln
from scipy import signal as scipy_signal


def _mono(audio: np.ndarray) -> np.ndarray:
    return audio.mean(axis=0) if audio.ndim > 1 else audio


def measure_integrated_lufs(audio: np.ndarray, sr: int) -> float:
    meter = pyln.Meter(sr)
    # pyloudnorm expects (samples, channels)
    data = audio.T if audio.ndim > 1 else audio
    return float(meter.integrated_loudness(data))


def measure_hf_ratio(audio: np.ndarray, sr: int, threshold_hz: float = 8000.0) -> float:
    """Ratio of HF energy (above threshold_hz) to total spectral energy.

    High values (>0.35) indicate harsh, aliased HF content — common in Suno exports.
    Normal mastered music sits around 0.15–0.25.
    """
    mono = _mono(audio)
    freqs = np.fft.rfftfreq(len(mono), d=1.0 / sr)
    magnitude = np.abs(np.fft.rfft(mono))
    hf_energy = float(np.sum(magnitude[freqs >= threshold_hz] ** 2))
    total_energy = float(np.sum(magnitude ** 2))
    return hf_energy / total_energy if total_energy > 0 else 0.0


def measure_band_db(audio: np.ndarray, sr: int, low_hz: float, high_hz: float) -> float:
    """Mean spectral power in a band, expressed as dB.

    Used for broad tonal balance decisions where relative deltas matter more
    than absolute calibrated SPL.
    """
    mono = _mono(audio)
    nperseg = min(len(mono), 16384)
    if nperseg < 1024:
        nperseg = min(len(mono), 1024)
    freqs, power = scipy_signal.welch(mono, fs=sr, nperseg=nperseg)
    mask = (freqs >= low_hz) & (freqs < high_hz)
    if not np.any(mask):
        return -120.0
    return float(10.0 * np.log10(np.mean(np.maximum(power[mask], 1e-18))))


def measure_spectral_flatness(audio: np.ndarray, sr: int) -> float:
    """Wiener entropy: 0 = pure tone / resonant, 1 = white noise / flat.

    Low values (<0.1) mean resonant peaks dominate — soothe2 needs to work harder.
    """
    mono = _mono(audio)
    magnitude = np.abs(np.fft.rfft(mono))
    magnitude = np.maximum(magnitude, 1e-10)
    log_mean = float(np.mean(np.log(magnitude)))
    arith_mean = float(np.mean(magnitude))
    return float(np.exp(log_mean) / arith_mean) if arith_mean > 0 else 0.0


def measure_crest_factor(audio: np.ndarray) -> float:
    """Peak-to-RMS ratio in dB.

    High values (>15 dB) = dynamic transients — elysia can be gentler.
    Low values (<8 dB) = already heavily limited — increase makeup gain.
    """
    peak = float(np.max(np.abs(audio)))
    rms = float(np.sqrt(np.mean(audio ** 2)))
    if rms < 1e-10:
        return 0.0
    return 20.0 * np.log10(peak / rms)


def measure_loudest_window(audio: np.ndarray, sr: int, seconds: float = 8.0) -> dict[str, float]:
    """Return RMS/peak/crest stats for the loudest program window.

    Mastering failures often happen in the loudest chorus/drop, while full-track
    LUFS still looks acceptable. This helper identifies that section so limiter
    drive can be capped against the part most likely to collapse.
    """
    mono = _mono(audio)
    if len(mono) == 0:
        return {
            "start_seconds": 0.0,
            "end_seconds": 0.0,
            "rms_dbfs": -120.0,
            "peak_dbfs": -120.0,
            "crest_db": 0.0,
        }

    window = max(1, min(len(mono), int(seconds * sr)))
    hop = max(1, window // 4)
    best_start = 0
    best_rms = -1.0

    for start in range(0, max(1, len(mono) - window + 1), hop):
        segment = mono[start:start + window]
        rms = float(np.sqrt(np.mean(segment ** 2)))
        if rms > best_rms:
            best_rms = rms
            best_start = start

    segment = mono[best_start:best_start + window]
    rms = float(np.sqrt(np.mean(segment ** 2)))
    peak = float(np.max(np.abs(segment)))
    rms_dbfs = float(20.0 * np.log10(max(rms, 1e-10)))
    peak_dbfs = float(20.0 * np.log10(max(peak, 1e-10)))
    crest_db = float(peak_dbfs - rms_dbfs) if rms > 1e-10 else 0.0

    return {
        "start_seconds": float(best_start / sr),
        "end_seconds": float((best_start + window) / sr),
        "rms_dbfs": rms_dbfs,
        "peak_dbfs": peak_dbfs,
        "crest_db": crest_db,
    }


def resolve_loud_section_crest_floor(
    source_crest_db: float,
    min_crest_db: float = 5.8,
    max_crest_loss_db: float = 1.0,
) -> float:
    """Choose the minimum acceptable crest for the loudest section.

    If the source is already very dense, preserve it rather than forcing an
    unrealistic crest. Otherwise allow only a small amount of mastering
    compression relative to the loudest source window.
    """
    if source_crest_db <= 0.0:
        return min_crest_db
    if source_crest_db < min_crest_db:
        return max(4.5, source_crest_db - min(0.3, max_crest_loss_db))
    return max(min_crest_db, source_crest_db - max_crest_loss_db)


def measure_sample_peak_dbfs(audio: np.ndarray) -> float:
    peak = float(np.max(np.abs(audio)))
    if peak < 1e-10:
        return -120.0
    return float(20.0 * np.log10(peak))


def measure_true_peak_dbfs(audio: np.ndarray, oversample: int = 4) -> float:
    """Approximate true peak by oversampling each channel before peak detection."""
    if oversample <= 1:
        return measure_sample_peak_dbfs(audio)

    channels = audio if audio.ndim > 1 else audio.reshape(1, -1)
    peaks: list[float] = []
    for channel in channels:
        oversampled = scipy_signal.resample_poly(channel, oversample, 1)
        peaks.append(float(np.max(np.abs(oversampled))))

    peak = max(peaks) if peaks else 0.0
    if peak < 1e-10:
        return -120.0
    return float(20.0 * np.log10(peak))


def measure_stereo_correlation(audio: np.ndarray) -> float:
    """Pearson correlation between L and R channels (-1 to 1).

    Near 1.0 = mono-ish (can safely widen).
    Near 0.0 = healthy stereo.
    Negative = phase issues (narrow before limiting).
    """
    if audio.ndim < 2 or audio.shape[0] < 2:
        return 1.0
    l, r = audio[0], audio[1]
    corr = np.corrcoef(l, r)
    return float(corr[0, 1])


def measure_side_to_mid_db(audio: np.ndarray) -> float:
    """Mid/side width indicator in dB.

    More negative values mean less side energy relative to the mid channel.
    A large drop after mastering usually means the stereo image narrowed.
    """
    if audio.ndim < 2 or audio.shape[0] < 2:
        return -120.0
    l, r = audio[0], audio[1]
    mid = 0.5 * (l + r)
    side = 0.5 * (l - r)
    mid_rms = float(np.sqrt(np.mean(mid ** 2)))
    side_rms = float(np.sqrt(np.mean(side ** 2)))
    if mid_rms < 1e-10 or side_rms < 1e-10:
        return -120.0
    return float(20.0 * np.log10(side_rms / mid_rms))


def detect_resonant_peaks(
    audio: np.ndarray, sr: int, n_peaks: int = 5, min_hz: float = 200.0
) -> list[tuple[float, float]]:
    """Detect top N resonant frequency peaks above min_hz.

    Returns list of (frequency_hz, magnitude_db) sorted by prominence.
    Used to inform Pro-Q 3 dynamic notch placement.
    """
    mono = _mono(audio)
    # Use a 1-second window for frequency resolution
    window_size = min(len(mono), sr)
    freqs = np.fft.rfftfreq(window_size, d=1.0 / sr)
    magnitude = np.abs(np.fft.rfft(mono[:window_size]))
    magnitude_db = 20.0 * np.log10(np.maximum(magnitude, 1e-10))

    valid = freqs >= min_hz
    freqs_v = freqs[valid]
    mag_v = magnitude_db[valid]

    peaks, _ = scipy_signal.find_peaks(mag_v, height=-60.0, distance=int(sr / 2000))
    if len(peaks) == 0:
        return []

    top = np.argsort(mag_v[peaks])[-n_peaks:][::-1]
    return [(float(freqs_v[peaks[i]]), float(mag_v[peaks[i]])) for i in top]


# ── Scaling helpers ──────────────────────────────────────────────────────────

def scale_soothe_depth(spectral_flatness: float) -> float:
    """Map spectral flatness to soothe2 depth in dB.

    soothe2 exposes depth as an audio-range value, not a 0-100 percent
    control. Keep this conservative for full-program mastering.

    flatness 0.05 (very resonant) -> 2.0 dB
    flatness 0.30 (already smooth) -> 0.35 dB
    """
    return float(np.clip(2.0 - (spectral_flatness - 0.05) * 6.6, 0.35, 2.0))


def scale_multipass_macro(hf_ratio: float) -> float:
    """Map HF ratio to Multipass Macro 1 amount (0-100).

    Multipass does not expose the nested effect controls through stable
    parameter names. Macro 1 should be mapped in the preset to HF control.

    hf_ratio 0.24 (bright)   -> 0%
    hf_ratio 0.42 (shimmery) -> 15%
    """
    return float(np.clip((hf_ratio - 0.24) / 0.18 * 15.0, 0.0, 15.0))


def scale_imager_width(correlation: float) -> float:
    """Map stereo correlation → Ozone Imager width (0.0–2.0).

    correlation 0.9 (near-mono) → width 1.4 (widen)
    correlation 0.3 (wide)      → width 0.9 (subtle)
    negative                    → width 0.7 (narrow to fix phase)
    """
    if correlation < 0:
        return 0.7
    return float(np.clip(1.4 - (correlation - 0.3) * 0.7, 0.7, 1.6))


def scale_alpha_threshold(crest_factor: float) -> float:
    """Map crest factor to elysia alpha master threshold in dB.

    Lower crest factor means the source is already dense, so the compressor
    should stay lighter. Higher crest factor allows slightly deeper glue.
    """
    return float(np.clip(10.0 - max(0.0, crest_factor - 9.0) * 0.45, 5.0, 12.0))


def scale_tape_drive(crest_factor: float, hf_ratio: float) -> float:
    """Map dynamics and HF hardness to Softube Tape color_amount (0-10).

    Suno material tends to be dense and bright already, so keep the drive
    modest and only push a little harder when the source is still spiky.
    """
    base = 1.8 + max(0.0, crest_factor - 8.0) * 0.08 + max(0.0, hf_ratio - 0.22) * 2.0
    return float(np.clip(base, 1.8, 3.2))
