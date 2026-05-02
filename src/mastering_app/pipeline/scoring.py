from __future__ import annotations

from typing import Any

import numpy as np

from .intent import apply_intent_score_bias
from .metrics import normalized_band_delta, normalized_playback_gain_db, source_is_harsh
from .render import STREAMING_REFERENCE_LUFS
from .targets import TargetProfile, TargetRange


def pillar_mastering_score(
    source_metrics: dict[str, float],
    candidate_metrics: dict[str, float],
) -> tuple[float, list[str]]:
    """Reward the four mastering pillars: de-harshing, width, warmth, and punch."""
    score = 0.0
    notes: list[str] = []

    punch_delta = candidate_metrics["punch_to_mud_db"] - source_metrics["punch_to_mud_db"]
    low_mid_delta = normalized_band_delta(source_metrics, candidate_metrics, "low_mid_db")
    vocal_delta = normalized_band_delta(source_metrics, candidate_metrics, "vocal_presence_db")
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


def _target_value(
    source_metrics: dict[str, float],
    candidate_metrics: dict[str, float],
    target: TargetRange,
) -> float:
    if target.mode == "absolute":
        return float(candidate_metrics[target.metric])
    if target.mode == "normalized_delta":
        return normalized_band_delta(source_metrics, candidate_metrics, target.metric)
    return float(candidate_metrics[target.metric] - source_metrics[target.metric])


def target_profile_score(
    source_metrics: dict[str, float],
    candidate_metrics: dict[str, float],
    profile: TargetProfile,
) -> tuple[float, list[str]]:
    """Score candidate against the selected target outcome, not only the source."""
    score = 0.0
    notes: list[str] = []

    for target in profile.ranges:
        value = _target_value(source_metrics, candidate_metrics, target)
        low = target.low
        high = target.high
        span = max(0.25, high - low)
        label = target.label or target.metric

        if low <= value <= high:
            score += target.weight
            if target.weight >= 6.0:
                notes.append(f"target hit {label} {value:+.2f}")
            continue

        miss = low - value if value < low else value - high
        penalty = min(target.weight * 1.5, (miss / span) * target.weight)
        score -= penalty
        if penalty >= 1.0:
            notes.append(
                f"target miss {label} {value:+.2f} "
                f"(goal {low:+.2f}..{high:+.2f})"
            )

    return float(np.clip(score, -35.0, 60.0)), notes


def normalized_playback_score(
    source_metrics: dict[str, float],
    candidate_metrics: dict[str, float],
) -> tuple[float, list[str]]:
    """Score how the master feels after streaming normalization.

    Output LUFS is allowed to vary. This score asks whether the candidate keeps
    musical energy, vocal presence, punch, width, and de-harshing when both the
    source and candidate are auditioned at normalized playback loudness.
    """
    score = 0.0
    notes: list[str] = []

    source_gain = source_metrics.get("streaming_playback_gain_db", normalized_playback_gain_db(source_metrics))
    candidate_gain = candidate_metrics.get("streaming_playback_gain_db", normalized_playback_gain_db(candidate_metrics))

    loud_rms_delta = (
        candidate_metrics["loud_window_rms_dbfs"]
        + candidate_gain
        - source_metrics["loud_window_rms_dbfs"]
        - source_gain
    )
    vocal_delta = normalized_band_delta(source_metrics, candidate_metrics, "vocal_presence_db")
    presence_delta = normalized_band_delta(source_metrics, candidate_metrics, "presence_db")
    harsh_delta = normalized_band_delta(source_metrics, candidate_metrics, "harsh_db")
    fizz_delta = normalized_band_delta(source_metrics, candidate_metrics, "fizz_db")
    punch_delta = normalized_band_delta(source_metrics, candidate_metrics, "punch_db")
    low_mid_delta = normalized_band_delta(source_metrics, candidate_metrics, "low_mid_db")
    punch_to_mud_delta = candidate_metrics["punch_to_mud_db"] - source_metrics["punch_to_mud_db"]
    presence_width_delta = candidate_metrics["presence_side_to_mid_db"] - source_metrics["presence_side_to_mid_db"]
    loud_crest_delta = candidate_metrics["loud_window_crest_db"] - source_metrics["loud_window_crest_db"]
    plr_delta = candidate_metrics["plr_db"] - source_metrics["plr_db"]

    if 0.15 <= loud_rms_delta <= 1.4:
        score += min(5.0, loud_rms_delta * 3.0)
        notes.append(f"normalized chorus energy improved {loud_rms_delta:+.2f} dB")
    elif loud_rms_delta < -0.6:
        score -= min(7.0, abs(loud_rms_delta + 0.6) * 3.0)
        notes.append(f"normalized chorus energy smaller {loud_rms_delta:+.2f} dB")
    elif loud_rms_delta > 2.1:
        score -= min(6.0, (loud_rms_delta - 2.1) * 2.5)
        notes.append(f"normalized chorus may feel over-dense {loud_rms_delta:+.2f} dB")

    if -0.25 <= vocal_delta <= 1.0:
        score += min(5.0, max(0.0, vocal_delta + 0.25) * 2.2)
    elif vocal_delta < -0.65:
        score -= min(9.0, abs(vocal_delta + 0.65) * 4.5)
        notes.append(f"normalized vocal presence lost {vocal_delta:+.2f} dB")

    if presence_delta < -0.8:
        score -= min(7.0, abs(presence_delta + 0.8) * 3.5)
        notes.append(f"normalized mid presence recessed {presence_delta:+.2f} dB")

    if -2.6 <= harsh_delta <= -0.25 and vocal_delta >= -0.65:
        score += min(5.0, abs(harsh_delta) * 1.5)
        notes.append(f"normalized harshness reduced {harsh_delta:+.2f} dB")
    elif harsh_delta > 0.2:
        score -= min(8.0, harsh_delta * 3.0)
        notes.append(f"normalized harshness increased {harsh_delta:+.2f} dB")

    if -3.0 <= fizz_delta <= -0.25 and vocal_delta >= -0.65:
        score += min(5.0, abs(fizz_delta) * 1.3)
        notes.append(f"normalized AI fizz reduced {fizz_delta:+.2f} dB")
    elif fizz_delta > 0.2:
        score -= min(8.0, fizz_delta * 2.8)
        notes.append(f"normalized AI fizz increased {fizz_delta:+.2f} dB")

    if 0.15 <= punch_delta <= 1.6 and punch_to_mud_delta >= -0.2:
        score += min(4.0, punch_delta * 2.0)
    elif punch_delta < -0.5:
        score -= min(5.0, abs(punch_delta + 0.5) * 2.5)
        notes.append(f"normalized punch reduced {punch_delta:+.2f} dB")

    if 0.10 <= low_mid_delta <= 1.4:
        score += min(4.0, low_mid_delta * 1.8)
    elif low_mid_delta > 2.1:
        score -= min(6.0, (low_mid_delta - 2.1) * 3.0)
        notes.append(f"normalized low-mid may feel boxy {low_mid_delta:+.2f} dB")

    if presence_width_delta >= 0.1:
        score += min(3.0, presence_width_delta * 1.2)
    elif presence_width_delta < -0.6:
        score -= min(6.0, abs(presence_width_delta + 0.6) * 3.0)
        notes.append(f"normalized presence image narrowed {presence_width_delta:+.2f} dB")

    if loud_crest_delta < -0.9:
        score -= min(8.0, abs(loud_crest_delta + 0.9) * 4.0)
        notes.append(f"normalized playback loses chorus crest {loud_crest_delta:+.2f} dB")
    elif loud_crest_delta > -0.2:
        score += min(3.0, (loud_crest_delta + 0.2) * 1.2)

    if plr_delta < -1.0:
        score -= min(6.0, abs(plr_delta + 1.0) * 3.0)
        notes.append(f"normalized playback PLR reduced {plr_delta:+.2f} dB")

    return float(np.clip(score, -28.0, 38.0)), notes


def score_candidate(
    source_metrics: dict[str, float],
    candidate_metrics: dict[str, float],
    target_lufs: float,
    target_profile: TargetProfile | None = None,
) -> tuple[float, list[str]]:
    score = 100.0
    notes: list[str] = []
    source_harsh = source_is_harsh(source_metrics)

    presence_delta = candidate_metrics["presence_db"] - source_metrics["presence_db"]
    side_delta = candidate_metrics["side_to_mid_db"] - source_metrics["side_to_mid_db"]
    corr_delta = candidate_metrics["stereo_correlation"] - source_metrics["stereo_correlation"]
    sub_delta = candidate_metrics["sub_db"] - source_metrics["sub_db"]
    crest_reduction = source_metrics["crest_factor_db"] - candidate_metrics["crest_factor_db"]
    loud_window_crest_delta = candidate_metrics["loud_window_crest_db"] - source_metrics["loud_window_crest_db"]
    lufs_gain = candidate_metrics["lufs"] - source_metrics["lufs"]
    streaming_turn_down_db = max(0.0, candidate_metrics["lufs"] - STREAMING_REFERENCE_LUFS)
    normalized_presence_delta = normalized_band_delta(source_metrics, candidate_metrics, "presence_db")
    normalized_low_mid_delta = normalized_band_delta(source_metrics, candidate_metrics, "low_mid_db")
    normalized_air_delta = normalized_band_delta(source_metrics, candidate_metrics, "air_db")

    if presence_delta < -0.4:
        if source_harsh and presence_delta >= -1.5:
            pass
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

    if normalized_presence_delta < -0.6:
        if source_harsh and normalized_presence_delta >= -1.2:
            pass
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

    pillar_score, pillar_notes = pillar_mastering_score(source_metrics, candidate_metrics)
    score += pillar_score
    if abs(pillar_score) >= 1.0:
        notes.append(f"pillar mastering score {pillar_score:+.1f}")
    notes.extend(pillar_notes)

    if target_profile is not None:
        target_score, target_notes = target_profile_score(source_metrics, candidate_metrics, target_profile)
        score += target_score
        if abs(target_score) >= 1.0:
            notes.append(f"target profile {target_profile.name} {target_score:+.1f}")
        notes.extend(target_notes)

    playback_score, playback_notes = normalized_playback_score(source_metrics, candidate_metrics)
    score += playback_score
    if abs(playback_score) >= 1.0:
        notes.append(f"normalized playback score {playback_score:+.1f}")
    notes.extend(playback_notes)

    return float(round(score, 3)), notes


def candidate_passes_release_guards(source_metrics: dict[str, float], candidate: dict[str, Any]) -> bool:
    if candidate["name"] == "original":
        return True
    metrics = candidate["metrics"]
    if metrics["presence_db"] - source_metrics["presence_db"] < -1.6:
        return False
    if metrics["side_to_mid_db"] - source_metrics["side_to_mid_db"] < -1.6:
        return False
    if metrics["stereo_correlation"] - source_metrics["stereo_correlation"] > 0.12:
        return False
    if metrics["sub_db"] - source_metrics["sub_db"] > 2.4:
        return False
    if metrics["hf_ratio"] - source_metrics["hf_ratio"] > 0.03:
        return False
    if metrics.get("artifact_index", 0.0) - source_metrics.get("artifact_index", 0.0) > 1.5:
        return False
    if metrics.get("high_band_correlation", 1.0) < -0.25:
        return False
    if source_is_harsh(source_metrics) and metrics["air_db"] - source_metrics["air_db"] > -0.2:
        return False
    if (
        source_metrics["loud_window_crest_db"] >= 6.0
        and metrics["loud_window_crest_db"] - source_metrics["loud_window_crest_db"] < -1.8
    ):
        return False
    return True


def best_candidate(source_metrics: dict[str, float], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    processed = [c for c in candidates if c["name"] != "original"]
    passing_processed = [c for c in processed if candidate_passes_release_guards(source_metrics, c)]
    if passing_processed:
        return max(passing_processed, key=lambda c: c["score"])
    passing_all = [c for c in candidates if candidate_passes_release_guards(source_metrics, c)]
    return max(passing_all or candidates, key=lambda c: c["score"])


def apply_intent_bias(candidates: list[dict[str, Any]], intent: Any) -> None:
    apply_intent_score_bias(candidates, intent)
