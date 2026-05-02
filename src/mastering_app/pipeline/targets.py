"""Explicit target outcomes for mastering decisions.

Intent should select a musical target. Presets are only different strategies
for reaching that target.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal


TargetMode = Literal["absolute", "delta", "normalized_delta"]


@dataclass(frozen=True)
class TargetRange:
    metric: str
    low: float
    high: float
    weight: float
    mode: TargetMode = "delta"
    label: str = ""

    def to_dict(self) -> dict[str, float | str]:
        return asdict(self)


@dataclass(frozen=True)
class TargetProfile:
    name: str
    description: str
    ranges: tuple[TargetRange, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "description": self.description,
            "ranges": [item.to_dict() for item in self.ranges],
        }


MODERN_POP_OPEN = TargetProfile(
    name="modern_pop_open",
    description=(
        "Open pop/EDM master: preserve vocal presence and width, add musical "
        "low-mid body/punch, reduce Suno glare/fizz, and protect chorus dynamics."
    ),
    ranges=(
        TargetRange("vocal_presence_db", -0.15, 1.00, 5.0, "normalized_delta", "vocal presence"),
        TargetRange("harsh_to_vocal_db", -3.00, -0.45, 7.0, "delta", "harsh/vocal balance"),
        TargetRange("fizz_to_vocal_db", -3.20, -0.45, 7.0, "delta", "AI fizz/vocal balance"),
        TargetRange("low_mid_db", 0.15, 1.20, 4.0, "normalized_delta", "low-mid body"),
        TargetRange("punch_to_mud_db", 0.25, 2.00, 5.0, "delta", "punch over mud"),
        TargetRange("presence_side_to_mid_db", 0.00, 1.50, 4.0, "delta", "presence width"),
        TargetRange("high_side_to_mid_db", -1.20, 0.60, 4.0, "delta", "side-high stability"),
        TargetRange("artifact_index", -5.00, -0.25, 6.0, "delta", "artifact reduction"),
        TargetRange("normalized_loud_window_rms_dbfs", 0.00, 1.30, 4.0, "delta", "normalized chorus energy"),
        TargetRange("loud_window_crest_db", -0.80, 0.80, 5.0, "delta", "chorus/drop crest"),
        TargetRange("plr_db", -0.80, 0.90, 3.0, "delta", "peak-loudness ratio"),
        TargetRange("true_peak_dbfs", -12.0, -0.80, 2.0, "absolute", "true peak safety"),
    ),
)


WARM_ANALOG = TargetProfile(
    name="warm_analog",
    description=(
        "Warmer analog-color master: more low-mid density and smoother sides, "
        "with glare reduction prioritized over extra air."
    ),
    ranges=(
        TargetRange("vocal_presence_db", -0.35, 0.80, 4.0, "normalized_delta", "vocal presence"),
        TargetRange("harsh_to_vocal_db", -3.20, -0.40, 7.0, "delta", "harsh/vocal balance"),
        TargetRange("fizz_to_vocal_db", -3.50, -0.40, 7.0, "delta", "AI fizz/vocal balance"),
        TargetRange("low_mid_db", 0.40, 1.80, 7.0, "normalized_delta", "analog low-mid body"),
        TargetRange("punch_to_mud_db", 0.20, 2.00, 4.0, "delta", "punch over mud"),
        TargetRange("presence_side_to_mid_db", -0.20, 1.00, 3.0, "delta", "presence width"),
        TargetRange("high_side_to_mid_db", -1.50, 0.20, 5.0, "delta", "side-high smoothing"),
        TargetRange("artifact_index", -5.00, -0.30, 6.0, "delta", "artifact reduction"),
        TargetRange("normalized_loud_window_rms_dbfs", -0.10, 1.10, 4.0, "delta", "normalized chorus energy"),
        TargetRange("loud_window_crest_db", -0.70, 0.90, 5.0, "delta", "chorus/drop crest"),
        TargetRange("plr_db", -0.60, 1.20, 3.0, "delta", "peak-loudness ratio"),
        TargetRange("true_peak_dbfs", -12.0, -0.80, 2.0, "absolute", "true peak safety"),
    ),
)


DEHARSH_REPAIR = TargetProfile(
    name="deharsh_repair",
    description=(
        "Repair-first master: reduce brittle AI shimmer and unstable side-highs "
        "without collapsing vocal presence or punch."
    ),
    ranges=(
        TargetRange("vocal_presence_db", -0.60, 0.60, 5.0, "normalized_delta", "vocal presence"),
        TargetRange("harsh_to_vocal_db", -4.00, -0.80, 9.0, "delta", "harsh/vocal balance"),
        TargetRange("fizz_to_vocal_db", -4.50, -0.80, 9.0, "delta", "AI fizz/vocal balance"),
        TargetRange("low_mid_db", 0.00, 1.00, 3.0, "normalized_delta", "low-mid body"),
        TargetRange("punch_to_mud_db", 0.00, 1.80, 3.0, "delta", "punch over mud"),
        TargetRange("presence_side_to_mid_db", -0.40, 0.80, 3.0, "delta", "presence width"),
        TargetRange("high_side_to_mid_db", -2.00, 0.00, 6.0, "delta", "side-high smoothing"),
        TargetRange("artifact_index", -6.00, -0.60, 9.0, "delta", "artifact reduction"),
        TargetRange("normalized_loud_window_rms_dbfs", -0.20, 0.90, 3.0, "delta", "normalized chorus energy"),
        TargetRange("loud_window_crest_db", -0.50, 1.00, 5.0, "delta", "chorus/drop crest"),
        TargetRange("plr_db", -0.40, 1.20, 3.0, "delta", "peak-loudness ratio"),
        TargetRange("true_peak_dbfs", -12.0, -0.80, 2.0, "absolute", "true peak safety"),
    ),
)


PUNCH_FORWARD = TargetProfile(
    name="punch_forward",
    description=(
        "Punch-forward master: improve kick/sub punch and perceived energy while "
        "keeping high-end artifacts and loud-section crest controlled."
    ),
    ranges=(
        TargetRange("vocal_presence_db", -0.20, 0.90, 4.0, "normalized_delta", "vocal presence"),
        TargetRange("harsh_to_vocal_db", -2.50, -0.30, 6.0, "delta", "harsh/vocal balance"),
        TargetRange("fizz_to_vocal_db", -2.80, -0.30, 6.0, "delta", "AI fizz/vocal balance"),
        TargetRange("low_mid_db", 0.20, 1.40, 4.0, "normalized_delta", "low-mid body"),
        TargetRange("punch_to_mud_db", 0.70, 2.60, 8.0, "delta", "punch over mud"),
        TargetRange("presence_side_to_mid_db", 0.00, 1.20, 3.0, "delta", "presence width"),
        TargetRange("high_side_to_mid_db", -1.00, 0.50, 4.0, "delta", "side-high stability"),
        TargetRange("artifact_index", -5.00, -0.25, 5.0, "delta", "artifact reduction"),
        TargetRange("normalized_loud_window_rms_dbfs", 0.20, 1.60, 6.0, "delta", "normalized chorus energy"),
        TargetRange("loud_window_crest_db", -0.80, 0.60, 6.0, "delta", "chorus/drop crest"),
        TargetRange("plr_db", -0.70, 0.80, 4.0, "delta", "peak-loudness ratio"),
        TargetRange("true_peak_dbfs", -12.0, -0.80, 2.0, "absolute", "true peak safety"),
    ),
)


CLEAN_PRESERVE = TargetProfile(
    name="clean_preserve",
    description=(
        "Minimal polish target: preserve the source character while trimming harshness, "
        "fizz, and unsafe peaks."
    ),
    ranges=(
        TargetRange("vocal_presence_db", -0.30, 0.50, 5.0, "normalized_delta", "vocal presence"),
        TargetRange("harsh_to_vocal_db", -2.00, -0.20, 6.0, "delta", "harsh/vocal balance"),
        TargetRange("fizz_to_vocal_db", -2.30, -0.20, 6.0, "delta", "AI fizz/vocal balance"),
        TargetRange("low_mid_db", -0.10, 0.80, 3.0, "normalized_delta", "low-mid body"),
        TargetRange("punch_to_mud_db", -0.10, 1.20, 3.0, "delta", "punch over mud"),
        TargetRange("presence_side_to_mid_db", -0.30, 0.80, 3.0, "delta", "presence width"),
        TargetRange("high_side_to_mid_db", -1.00, 0.30, 4.0, "delta", "side-high stability"),
        TargetRange("artifact_index", -4.00, -0.20, 5.0, "delta", "artifact reduction"),
        TargetRange("normalized_loud_window_rms_dbfs", -0.20, 0.80, 3.0, "delta", "normalized chorus energy"),
        TargetRange("loud_window_crest_db", -0.40, 0.80, 6.0, "delta", "chorus/drop crest"),
        TargetRange("plr_db", -0.30, 1.00, 4.0, "delta", "peak-loudness ratio"),
        TargetRange("true_peak_dbfs", -12.0, -0.80, 2.0, "absolute", "true peak safety"),
    ),
)


PROFILES = {
    profile.name: profile
    for profile in (
        MODERN_POP_OPEN,
        WARM_ANALOG,
        DEHARSH_REPAIR,
        PUNCH_FORWARD,
        CLEAN_PRESERVE,
    )
}


def select_target_profile(tags: list[str]) -> TargetProfile:
    tag_set = set(tags)
    if "clean_preserve" in tag_set:
        return CLEAN_PRESERVE
    if "deharsh" in tag_set and "bright_open" not in tag_set:
        return DEHARSH_REPAIR
    if "punch_warm" in tag_set and ("loud_dense" in tag_set or "dynamic_guard" in tag_set):
        return PUNCH_FORWARD
    if "punch_warm" in tag_set:
        return WARM_ANALOG
    return MODERN_POP_OPEN
