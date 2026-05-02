"""Bounded mastering settings used by deterministic and AI-assisted renders."""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass, replace
from typing import Any

import numpy as np


@dataclass(frozen=True)
class MasteringSettings:
    name: str = "default"
    description: str = "streaming-normalized source-preserving polish"
    internal_chain_lufs: float = -14.8
    streaming_profile_enabled: bool = True
    streaming_reference_lufs: float = -14.0
    streaming_loud_target_ceiling_dbfs: float = -2.0
    streaming_normal_target_ceiling_dbfs: float = -1.0
    corrective_eq_enabled: bool = True
    proq_preset: bool = False
    soothe_depth_scale: float = 1.05
    soothe1_mix: float = 36.0
    soothe2_depth_scale: float = 0.14
    soothe2_mix: float = 22.0
    multipass_macro_cap: float = 18.0
    alpha_threshold_offset: float = 0.0
    alpha_threshold_min: float = 5.0
    alpha_threshold_max: float = 12.0
    alpha_ratio: float = 1.1
    tape_color_scale: float = 1.0
    tape_color_offset: float = 0.0
    tape_color_min: float = 1.4
    tape_color_max: float = 3.2
    tape_speed: str = "30 IPS"
    gullfoss_enabled: bool = True
    gullfoss_recover: float = 4.0
    gullfoss_tame: float = 8.0
    gullfoss_brighten: float = -0.5
    gullfoss_boost_db: float = 0.0
    gullfoss_bias: float = 0.0
    bax_enabled: bool = False
    bax_low_shelf_db: float = 0.0
    bax_high_shelf_db: float = 0.0
    bx_digital_enabled: bool = False
    bx_stereo_width: float = 100.0
    bx_mono_maker_enabled: bool = False
    bx_mono_maker_hz: float = 20.0
    low_end_focus_enabled: bool = False
    low_end_focus_contrast: float = 0.0
    low_end_focus_gain_db: float = 0.0
    low_end_focus_region_low_hz: float = 20.0
    low_end_focus_region_high_hz: float = 250.0
    low_end_focus_mode: str = "Punchy"
    inflator_enabled: bool = False
    inflator_effect: float = 0.0
    inflator_curve: float = 0.0
    inflator_input_gain: float = 0.0
    inflator_output_gain: float = 0.0
    inflator_clip_0db: bool = False
    ozone_imager_enabled: bool = True
    ozone_imager_band_1_width_percent: float = 0.0
    ozone_imager_band_2_width_percent: float = 4.0
    ozone_imager_band_3_width_percent: float = 6.0
    ozone_imager_band_4_width_percent: float = 8.0
    ozone_imager_width_scale: float = 1.0
    ozone_imager_stereoizer_enabled: bool = False
    ozone_imager_stereoizer_delay_ms: float = 6.0
    final_limiter: str = "ozone9"
    weiss_amount: float = 35.0
    weiss_limiter_gain_db: float = 0.0
    weiss_out_trim_dbfs: float = -1.0
    weiss_parallel_mix: float = 100.0
    weiss_style: str = "Punch"
    ozone_threshold: float = -1.0
    ozone_ceiling: float = -1.0
    ozone_bypass_modules: bool = True
    loud_section_guard_enabled: bool = True
    loud_section_seconds: float = 8.0
    loud_section_min_crest_db: float = 6.2
    loud_section_max_crest_loss_db: float = 0.75
    hf_guard_enabled: bool = True
    hf_guard_ratio_threshold: float = 0.22
    hf_guard_air_to_presence_db: float = 0.35
    hf_guard_frequency_hz: float = 9000.0
    hf_guard_max_reduction_db: float = 1.2
    source_match_enabled: bool = True
    source_match_presence_max_db: float = 1.2
    source_match_sub_trim_max_db: float = 1.0
    source_match_side_max_db: float = 1.8
    creative_mode: bool = False
    ms_tone_enabled: bool = False
    ms_mid_warmth_db: float = 0.0
    ms_mid_presence_db: float = 0.0
    ms_side_presence_db: float = 0.0
    ms_side_hf_shelf_db: float = 0.0
    soft_clip_enabled: bool = False
    soft_clip_drive_db: float = 0.0
    soft_clip_mix: float = 0.0
    soft_clip_output_trim_db: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


DEFAULT_SETTINGS = MasteringSettings()


SETTING_BOUNDS: dict[str, tuple[float, float]] = {
    "internal_chain_lufs": (-18.0, -12.0),
    "streaming_reference_lufs": (-18.0, -10.0),
    "streaming_loud_target_ceiling_dbfs": (-3.0, -1.0),
    "streaming_normal_target_ceiling_dbfs": (-2.0, -0.8),
    "soothe_depth_scale": (0.0, 1.4),
    "soothe1_mix": (0.0, 60.0),
    "soothe2_depth_scale": (0.0, 0.35),
    "soothe2_mix": (0.0, 35.0),
    "multipass_macro_cap": (0.0, 25.0),
    "alpha_threshold_offset": (-2.0, 2.0),
    "alpha_threshold_min": (0.0, 12.0),
    "alpha_threshold_max": (4.0, 20.0),
    "alpha_ratio": (1.1, 1.35),
    "tape_color_scale": (0.6, 1.4),
    "tape_color_offset": (-1.0, 1.0),
    "tape_color_min": (0.0, 3.0),
    "tape_color_max": (1.5, 5.0),
    "gullfoss_recover": (0.0, 25.0),
    "gullfoss_tame": (0.0, 25.0),
    "gullfoss_brighten": (-10.0, 12.0),
    "gullfoss_boost_db": (-1.5, 1.5),
    "gullfoss_bias": (-20.0, 20.0),
    "bax_low_shelf_db": (-1.5, 1.5),
    "bax_high_shelf_db": (-1.5, 1.5),
    "bx_stereo_width": (90.0, 110.0),
    "bx_mono_maker_hz": (20.0, 160.0),
    "low_end_focus_contrast": (-20.0, 35.0),
    "low_end_focus_gain_db": (-1.5, 1.5),
    "low_end_focus_region_low_hz": (20.0, 120.0),
    "low_end_focus_region_high_hz": (120.0, 300.0),
    "inflator_effect": (0.0, 30.0),
    "inflator_curve": (-15.0, 20.0),
    "inflator_input_gain": (-3.0, 3.0),
    "inflator_output_gain": (-3.0, 1.0),
    "ozone_imager_band_1_width_percent": (-10.0, 10.0),
    "ozone_imager_band_2_width_percent": (-20.0, 25.0),
    "ozone_imager_band_3_width_percent": (-20.0, 35.0),
    "ozone_imager_band_4_width_percent": (-20.0, 40.0),
    "ozone_imager_width_scale": (0.0, 1.5),
    "ozone_imager_stereoizer_delay_ms": (4.0, 20.0),
    "weiss_amount": (0.0, 55.0),
    "weiss_limiter_gain_db": (-3.0, 3.0),
    "weiss_out_trim_dbfs": (-2.0, 0.0),
    "weiss_parallel_mix": (50.0, 100.0),
    "ozone_threshold": (-5.0, 0.0),
    "ozone_ceiling": (-2.5, -0.8),
    "loud_section_seconds": (3.0, 20.0),
    "loud_section_min_crest_db": (4.5, 8.0),
    "loud_section_max_crest_loss_db": (0.3, 2.5),
    "hf_guard_ratio_threshold": (0.16, 0.35),
    "hf_guard_air_to_presence_db": (-1.0, 2.0),
    "hf_guard_frequency_hz": (6500.0, 12000.0),
    "hf_guard_max_reduction_db": (0.0, 2.5),
    "source_match_presence_max_db": (0.0, 2.0),
    "source_match_sub_trim_max_db": (0.0, 1.8),
    "source_match_side_max_db": (0.0, 2.5),
    "ms_mid_warmth_db": (-2.0, 2.0),
    "ms_mid_presence_db": (-2.0, 2.0),
    "ms_side_presence_db": (-2.0, 2.0),
    "ms_side_hf_shelf_db": (-4.0, 2.0),
    "soft_clip_drive_db": (0.0, 8.0),
    "soft_clip_mix": (0.0, 100.0),
    "soft_clip_output_trim_db": (-4.0, 0.0),
}

BOOLEAN_SETTINGS = {
    "corrective_eq_enabled",
    "streaming_profile_enabled",
    "proq_preset",
    "gullfoss_enabled",
    "bax_enabled",
    "bx_digital_enabled",
    "bx_mono_maker_enabled",
    "low_end_focus_enabled",
    "inflator_enabled",
    "inflator_clip_0db",
    "ozone_imager_enabled",
    "ozone_imager_stereoizer_enabled",
    "ozone_bypass_modules",
    "loud_section_guard_enabled",
    "hf_guard_enabled",
    "source_match_enabled",
    "creative_mode",
    "ms_tone_enabled",
    "soft_clip_enabled",
}

STRING_SETTINGS = {
    "name",
    "description",
    "tape_speed",
    "low_end_focus_mode",
    "final_limiter",
    "weiss_style",
}

STRING_CHOICES = {
    "tape_speed": {"15 IPS", "30 IPS"},
    "low_end_focus_mode": {"Punchy", "Smooth"},
    "final_limiter": {"ozone9", "weiss_mm1"},
    "weiss_style": {"Transparent", "Loud", "Punch", "Wide", "De-ess"},
}


def bounded_settings(base: MasteringSettings, name: str, description: str, overrides: dict[str, Any]) -> MasteringSettings:
    values = base.to_dict()
    values["name"] = name
    values["description"] = description

    for key, value in overrides.items():
        if key in SETTING_BOUNDS:
            low, high = SETTING_BOUNDS[key]
            values[key] = float(np.clip(float(value), low, high))
        elif key in BOOLEAN_SETTINGS:
            values[key] = bool(value)
        elif key in STRING_CHOICES:
            text = str(value)
            values[key] = text if text in STRING_CHOICES[key] else values[key]

    if values["alpha_threshold_min"] > values["alpha_threshold_max"]:
        values["alpha_threshold_min"], values["alpha_threshold_max"] = (
            values["alpha_threshold_max"],
            values["alpha_threshold_min"],
        )
    if values["tape_color_min"] > values["tape_color_max"]:
        values["tape_color_min"], values["tape_color_max"] = values["tape_color_max"], values["tape_color_min"]
    if values["low_end_focus_region_low_hz"] > values["low_end_focus_region_high_hz"]:
        values["low_end_focus_region_low_hz"], values["low_end_focus_region_high_hz"] = (
            values["low_end_focus_region_high_hz"],
            values["low_end_focus_region_low_hz"],
        )

    return MasteringSettings(**values)


def _use_legacy_candidates() -> bool:
    return os.environ.get("MASTERING_LEGACY_CANDIDATES", "").strip().lower() in {"1", "true", "yes", "on"}


def _creative_candidate_settings(base: MasteringSettings) -> list[MasteringSettings]:
    """Fewer, bolder candidates designed for audible tone/dynamics/imaging choices."""
    return [
        bounded_settings(
            base,
            "transparent_repair",
            "transparent repair: reduce AI glass/fizz while preserving the original tonal center",
            {
                "internal_chain_lufs": -14.8,
                "soothe_depth_scale": 0.92,
                "soothe1_mix": 32.0,
                "soothe2_depth_scale": 0.10,
                "soothe2_mix": 18.0,
                "multipass_macro_cap": 15.0,
                "gullfoss_recover": 5.0,
                "gullfoss_tame": 14.0,
                "gullfoss_brighten": -0.6,
                "tape_color_scale": 0.95,
                "hf_guard_max_reduction_db": 1.4,
                "source_match_presence_max_db": 1.8,
                "source_match_side_max_db": 2.3,
            },
        ),
        bounded_settings(
            base,
            "creative_analog",
            "creative analog remaster: audible tape/Inflator density, low-mid color, and softened digital top",
            {
                "creative_mode": True,
                "source_match_enabled": False,
                "internal_chain_lufs": -13.9,
                "soothe_depth_scale": 0.72,
                "soothe1_mix": 24.0,
                "soothe2_depth_scale": 0.05,
                "soothe2_mix": 10.0,
                "multipass_macro_cap": 9.0,
                "alpha_ratio": 1.12,
                "alpha_threshold_offset": 0.7,
                "tape_color_scale": 1.4,
                "tape_color_offset": 0.8,
                "tape_color_min": 2.6,
                "tape_color_max": 5.0,
                "gullfoss_recover": 9.0,
                "gullfoss_tame": 8.0,
                "gullfoss_brighten": 0.2,
                "bax_enabled": True,
                "bax_low_shelf_db": 0.75,
                "bax_high_shelf_db": 0.05,
                "low_end_focus_enabled": True,
                "low_end_focus_contrast": 16.0,
                "low_end_focus_gain_db": 0.35,
                "inflator_enabled": True,
                "inflator_effect": 22.0,
                "inflator_curve": 8.0,
                "inflator_output_gain": -1.6,
                "soft_clip_enabled": True,
                "soft_clip_drive_db": 4.5,
                "soft_clip_mix": 32.0,
                "soft_clip_output_trim_db": -1.2,
                "ms_tone_enabled": True,
                "ms_mid_warmth_db": 0.8,
                "ms_mid_presence_db": 0.45,
                "ms_side_hf_shelf_db": -1.1,
                "bx_digital_enabled": True,
                "bx_stereo_width": 103.0,
                "bx_mono_maker_enabled": True,
                "bx_mono_maker_hz": 95.0,
                "ozone_imager_band_2_width_percent": 5.0,
                "ozone_imager_band_3_width_percent": 8.0,
                "ozone_imager_band_4_width_percent": 6.0,
                "hf_guard_max_reduction_db": 1.1,
                "loud_section_min_crest_db": 6.1,
                "loud_section_max_crest_loss_db": 1.1,
            },
        ),
        bounded_settings(
            base,
            "wide_open_color",
            "wide open color: vocal-forward mid, wider presence image, side-high deglaze",
            {
                "creative_mode": True,
                "source_match_enabled": False,
                "internal_chain_lufs": -14.2,
                "soothe_depth_scale": 0.62,
                "soothe1_mix": 18.0,
                "soothe2_depth_scale": 0.03,
                "soothe2_mix": 8.0,
                "multipass_macro_cap": 5.0,
                "tape_color_scale": 1.0,
                "tape_color_offset": 0.35,
                "gullfoss_recover": 11.0,
                "gullfoss_tame": 5.0,
                "gullfoss_brighten": 1.2,
                "bax_enabled": True,
                "bax_high_shelf_db": 0.45,
                "ms_tone_enabled": True,
                "ms_mid_presence_db": 0.9,
                "ms_side_presence_db": 0.6,
                "ms_side_hf_shelf_db": -0.9,
                "bx_digital_enabled": True,
                "bx_stereo_width": 108.0,
                "bx_mono_maker_enabled": True,
                "bx_mono_maker_hz": 85.0,
                "ozone_imager_band_2_width_percent": 12.0,
                "ozone_imager_band_3_width_percent": 22.0,
                "ozone_imager_band_4_width_percent": 14.0,
                "ozone_imager_width_scale": 1.2,
                "inflator_enabled": True,
                "inflator_effect": 10.0,
                "inflator_curve": 1.0,
                "inflator_output_gain": -0.8,
                "hf_guard_air_to_presence_db": 0.6,
                "hf_guard_max_reduction_db": 0.9,
                "loud_section_min_crest_db": 6.5,
                "loud_section_max_crest_loss_db": 0.75,
            },
        ),
        bounded_settings(
            base,
            "ai_deglaze",
            "AI deglaze: strong side-high smoothing and phase stabilization without low-mid hype",
            {
                "creative_mode": True,
                "source_match_enabled": False,
                "internal_chain_lufs": -15.2,
                "soothe_depth_scale": 1.28,
                "soothe1_mix": 52.0,
                "soothe2_depth_scale": 0.22,
                "soothe2_mix": 30.0,
                "multipass_macro_cap": 24.0,
                "alpha_ratio": 1.1,
                "alpha_threshold_offset": 1.2,
                "tape_color_scale": 1.2,
                "tape_color_offset": 0.35,
                "gullfoss_recover": 3.0,
                "gullfoss_tame": 25.0,
                "gullfoss_brighten": -2.2,
                "gullfoss_boost_db": -0.25,
                "ms_tone_enabled": True,
                "ms_mid_presence_db": 0.3,
                "ms_side_presence_db": -0.4,
                "ms_side_hf_shelf_db": -2.4,
                "bx_digital_enabled": True,
                "bx_stereo_width": 98.0,
                "bx_mono_maker_enabled": True,
                "bx_mono_maker_hz": 120.0,
                "ozone_imager_band_2_width_percent": -2.0,
                "ozone_imager_band_3_width_percent": -6.0,
                "ozone_imager_band_4_width_percent": -10.0,
                "hf_guard_frequency_hz": 7000.0,
                "hf_guard_air_to_presence_db": -0.2,
                "hf_guard_max_reduction_db": 2.5,
                "loud_section_min_crest_db": 7.0,
                "loud_section_max_crest_loss_db": 0.55,
            },
        ),
        bounded_settings(
            base,
            "punch_density",
            "punch density: stronger low-end focus, parallel clip density, and energetic Weiss finish",
            {
                "creative_mode": True,
                "source_match_enabled": False,
                "internal_chain_lufs": -13.4,
                "soothe_depth_scale": 0.76,
                "soothe1_mix": 22.0,
                "soothe2_depth_scale": 0.05,
                "soothe2_mix": 10.0,
                "multipass_macro_cap": 8.0,
                "alpha_ratio": 1.16,
                "alpha_threshold_offset": -0.3,
                "tape_color_scale": 1.25,
                "tape_color_offset": 0.55,
                "gullfoss_recover": 7.0,
                "gullfoss_tame": 7.0,
                "bax_enabled": True,
                "bax_low_shelf_db": 0.95,
                "low_end_focus_enabled": True,
                "low_end_focus_contrast": 28.0,
                "low_end_focus_gain_db": 0.55,
                "inflator_enabled": True,
                "inflator_effect": 26.0,
                "inflator_curve": 6.0,
                "inflator_output_gain": -1.8,
                "soft_clip_enabled": True,
                "soft_clip_drive_db": 5.5,
                "soft_clip_mix": 45.0,
                "soft_clip_output_trim_db": -1.6,
                "ms_tone_enabled": True,
                "ms_mid_warmth_db": 0.65,
                "ms_side_hf_shelf_db": -1.0,
                "bx_digital_enabled": True,
                "bx_stereo_width": 102.0,
                "bx_mono_maker_enabled": True,
                "bx_mono_maker_hz": 110.0,
                "final_limiter": "weiss_mm1",
                "weiss_amount": 34.0,
                "weiss_style": "Punch",
                "weiss_out_trim_dbfs": -1.2,
                "loud_section_min_crest_db": 5.7,
                "loud_section_max_crest_loss_db": 1.35,
            },
        ),
        bounded_settings(
            base,
            "dynamic_open",
            "dynamic open: lowest density, preserved chorus crest, vocal presence, and gentle width",
            {
                "creative_mode": True,
                "source_match_enabled": False,
                "internal_chain_lufs": -15.6,
                "soothe_depth_scale": 0.50,
                "soothe1_mix": 14.0,
                "soothe2_depth_scale": 0.02,
                "soothe2_mix": 6.0,
                "multipass_macro_cap": 3.0,
                "alpha_ratio": 1.1,
                "alpha_threshold_offset": 1.8,
                "tape_color_scale": 0.82,
                "tape_color_offset": 0.15,
                "gullfoss_recover": 8.0,
                "gullfoss_tame": 4.0,
                "gullfoss_brighten": 0.7,
                "ms_tone_enabled": True,
                "ms_mid_presence_db": 0.55,
                "ms_side_presence_db": 0.35,
                "ms_side_hf_shelf_db": -0.7,
                "bx_digital_enabled": True,
                "bx_stereo_width": 105.0,
                "ozone_imager_band_2_width_percent": 6.0,
                "ozone_imager_band_3_width_percent": 10.0,
                "ozone_imager_band_4_width_percent": 6.0,
                "inflator_enabled": False,
                "soft_clip_enabled": False,
                "ozone_threshold": -0.4,
                "hf_guard_max_reduction_db": 0.7,
                "loud_section_min_crest_db": 7.4,
                "loud_section_max_crest_loss_db": 0.35,
            },
        ),
    ]


def candidate_settings(style: str) -> list[MasteringSettings]:
    style_note = style.strip() or "modern pop / EDM"
    base = replace(DEFAULT_SETTINGS, description=f"source-preserving polish for {style_note}")
    if not _use_legacy_candidates():
        return _creative_candidate_settings(base)
    return [
        bounded_settings(
            base,
            "classic_chain",
            "streaming-safe deterministic chain baseline with universal de-shimmering",
            {},
        ),
        bounded_settings(
            base,
            "streaming_loud_open",
            "normalized-playback loudness, open width, true-peak-safe de-harshing",
            {
                "internal_chain_lufs": -14.6,
                "soothe_depth_scale": 0.9,
                "soothe1_mix": 30.0,
                "soothe2_depth_scale": 0.1,
                "soothe2_mix": 18.0,
                "multipass_macro_cap": 14.0,
                "gullfoss_recover": 5.0,
                "gullfoss_tame": 10.0,
                "gullfoss_brighten": -0.2,
                "low_end_focus_enabled": True,
                "low_end_focus_contrast": 5.0,
                "low_end_focus_gain_db": 0.0,
                "bx_digital_enabled": True,
                "bx_stereo_width": 102.0,
                "ozone_imager_band_2_width_percent": 4.0,
                "ozone_imager_band_3_width_percent": 7.0,
                "ozone_imager_band_4_width_percent": 8.0,
                "inflator_enabled": True,
                "inflator_effect": 6.0,
                "inflator_curve": 0.0,
                "inflator_output_gain": -0.4,
                "ozone_threshold": -0.8,
                "loud_section_min_crest_db": 6.4,
                "loud_section_max_crest_loss_db": 0.65,
                "source_match_presence_max_db": 1.8,
                "source_match_side_max_db": 2.4,
            },
        ),
        bounded_settings(
            base,
            "streaming_polish_plus",
            "more audible streaming polish: punch, width, density, and controlled high-end",
            {
                "internal_chain_lufs": -14.2,
                "soothe_depth_scale": 0.95,
                "soothe1_mix": 32.0,
                "soothe2_depth_scale": 0.12,
                "soothe2_mix": 20.0,
                "multipass_macro_cap": 16.0,
                "alpha_ratio": 1.12,
                "alpha_threshold_offset": -0.2,
                "tape_color_scale": 1.25,
                "tape_color_offset": 0.25,
                "gullfoss_recover": 6.0,
                "gullfoss_tame": 12.0,
                "gullfoss_brighten": 0.1,
                "bax_enabled": True,
                "bax_low_shelf_db": 0.55,
                "bax_high_shelf_db": 0.1,
                "low_end_focus_enabled": True,
                "low_end_focus_contrast": 14.0,
                "low_end_focus_gain_db": 0.25,
                "bx_digital_enabled": True,
                "bx_stereo_width": 105.0,
                "bx_mono_maker_enabled": True,
                "bx_mono_maker_hz": 80.0,
                "ozone_imager_band_2_width_percent": 7.0,
                "ozone_imager_band_3_width_percent": 12.0,
                "ozone_imager_band_4_width_percent": 14.0,
                "inflator_enabled": True,
                "inflator_effect": 14.0,
                "inflator_curve": 3.0,
                "inflator_output_gain": -0.8,
                "ozone_threshold": -1.2,
                "hf_guard_air_to_presence_db": 0.2,
                "hf_guard_max_reduction_db": 1.8,
                "loud_section_min_crest_db": 6.1,
                "loud_section_max_crest_loss_db": 0.85,
                "source_match_sub_trim_max_db": 0.5,
                "source_match_presence_max_db": 1.5,
                "source_match_side_max_db": 2.5,
            },
        ),
        bounded_settings(
            base,
            "preserve_open",
            "minimal cleanup, preserve width and source presence",
            {
                "internal_chain_lufs": -14.4,
                "soothe_depth_scale": 0.78,
                "soothe1_mix": 24.0,
                "soothe2_depth_scale": 0.07,
                "soothe2_mix": 14.0,
                "multipass_macro_cap": 9.0,
                "alpha_ratio": 1.1,
                "alpha_threshold_offset": 1.0,
                "tape_color_scale": 0.8,
                "gullfoss_recover": 3.5,
                "gullfoss_tame": 7.0,
                "gullfoss_brighten": -0.2,
                "bx_digital_enabled": True,
                "bx_stereo_width": 102.0,
                "ozone_imager_band_2_width_percent": 3.0,
                "ozone_imager_band_3_width_percent": 4.0,
                "ozone_imager_band_4_width_percent": 5.0,
                "source_match_presence_max_db": 1.6,
                "source_match_side_max_db": 2.2,
            },
        ),
        bounded_settings(
            base,
            "bright_open_edm",
            "bright, wide pop-EDM polish with streaming-safe shimmer control",
            {
                "internal_chain_lufs": -14.5,
                "soothe_depth_scale": 0.88,
                "soothe1_mix": 30.0,
                "soothe2_depth_scale": 0.1,
                "soothe2_mix": 17.0,
                "multipass_macro_cap": 12.0,
                "alpha_ratio": 1.1,
                "alpha_threshold_offset": 0.5,
                "tape_color_scale": 0.9,
                "gullfoss_enabled": True,
                "gullfoss_recover": 6.0,
                "gullfoss_tame": 9.0,
                "gullfoss_brighten": 0.8,
                "bx_digital_enabled": True,
                "bx_stereo_width": 103.0,
                "ozone_imager_band_2_width_percent": 6.0,
                "ozone_imager_band_3_width_percent": 9.0,
                "ozone_imager_band_4_width_percent": 12.0,
                "inflator_enabled": True,
                "inflator_effect": 7.0,
                "inflator_curve": 1.5,
                "inflator_output_gain": -0.4,
                "loud_section_min_crest_db": 6.4,
                "loud_section_max_crest_loss_db": 0.65,
                "source_match_presence_max_db": 2.0,
                "source_match_side_max_db": 2.5,
            },
        ),
        bounded_settings(
            base,
            "punch_warm",
            "slightly warmer low-mid punch without darkening the source",
            {
                "internal_chain_lufs": -14.8,
                "soothe_depth_scale": 0.86,
                "soothe1_mix": 28.0,
                "soothe2_depth_scale": 0.09,
                "soothe2_mix": 16.0,
                "multipass_macro_cap": 12.0,
                "alpha_ratio": 1.1,
                "tape_color_scale": 1.15,
                "tape_color_offset": 0.2,
                "gullfoss_recover": 4.0,
                "gullfoss_tame": 9.0,
                "gullfoss_brighten": -0.2,
                "bax_enabled": True,
                "bax_low_shelf_db": 0.4,
                "bax_high_shelf_db": 0.2,
                "low_end_focus_enabled": True,
                "low_end_focus_contrast": 10.0,
                "low_end_focus_gain_db": 0.2,
                "bx_digital_enabled": True,
                "bx_mono_maker_enabled": True,
                "bx_mono_maker_hz": 90.0,
                "ozone_imager_band_2_width_percent": 3.0,
                "ozone_imager_band_3_width_percent": 5.0,
                "ozone_imager_band_4_width_percent": 6.0,
                "inflator_enabled": True,
                "inflator_effect": 6.0,
                "inflator_curve": 0.5,
                "inflator_output_gain": -0.5,
                "loud_section_min_crest_db": 6.5,
                "loud_section_max_crest_loss_db": 0.6,
                "source_match_sub_trim_max_db": 1.4,
                "source_match_presence_max_db": 1.6,
            },
        ),
        bounded_settings(
            base,
            "punch_warm_dynamic",
            "low-mid warmth like punch_warm with less late-section limiting and density",
            {
                "internal_chain_lufs": -15.2,
                "soothe_depth_scale": 0.68,
                "soothe1_mix": 22.0,
                "soothe2_depth_scale": 0.05,
                "soothe2_mix": 12.0,
                "multipass_macro_cap": 10.0,
                "alpha_ratio": 1.1,
                "alpha_threshold_offset": 1.0,
                "tape_color_scale": 0.9,
                "tape_color_offset": 0.1,
                "gullfoss_recover": 3.0,
                "gullfoss_tame": 8.0,
                "gullfoss_brighten": -0.4,
                "bax_enabled": True,
                "bax_low_shelf_db": 0.35,
                "bax_high_shelf_db": 0.1,
                "low_end_focus_enabled": True,
                "low_end_focus_contrast": 5.0,
                "low_end_focus_gain_db": 0.0,
                "bx_digital_enabled": True,
                "bx_mono_maker_enabled": True,
                "bx_mono_maker_hz": 75.0,
                "ozone_imager_band_2_width_percent": 2.0,
                "ozone_imager_band_3_width_percent": 4.0,
                "ozone_imager_band_4_width_percent": 5.0,
                "inflator_enabled": False,
                "ozone_threshold": -1.0,
                "loud_section_min_crest_db": 6.8,
                "loud_section_max_crest_loss_db": 0.5,
                "source_match_sub_trim_max_db": 1.2,
                "source_match_presence_max_db": 1.6,
                "source_match_side_max_db": 2.2,
            },
        ),
        bounded_settings(
            base,
            "controlled_shimmer",
            "more cleanup for brittle AI shimmer while protecting presence",
            {
                "internal_chain_lufs": -15.0,
                "soothe_depth_scale": 1.1,
                "soothe1_mix": 42.0,
                "soothe2_depth_scale": 0.14,
                "soothe2_mix": 22.0,
                "multipass_macro_cap": 20.0,
                "alpha_ratio": 1.1,
                # Higher tape than before: saturation converts shimmer into harmonic texture
                # rather than just cutting — preserves energy while removing digital edge.
                "tape_color_scale": 1.1,
                "gullfoss_enabled": True,
                "gullfoss_recover": 5.0,
                "gullfoss_tame": 14.0,
                "gullfoss_brighten": -1.0,
                "hf_guard_max_reduction_db": 1.8,
                "ozone_imager_band_2_width_percent": 2.0,
                "ozone_imager_band_3_width_percent": 4.0,
                "ozone_imager_band_4_width_percent": 5.0,
                "inflator_enabled": False,
                "source_match_presence_max_db": 2.0,
                "source_match_side_max_db": 2.2,
            },
        ),
        bounded_settings(
            base,
            "deharsh_gullfoss",
            "targeted high-end de-harshing with tape warmth — reduces shimmer without darkening",
            {
                "internal_chain_lufs": -15.0,
                "soothe_depth_scale": 0.95,
                "soothe1_mix": 34.0,
                "soothe2_depth_scale": 0.11,
                "soothe2_mix": 18.0,
                "multipass_macro_cap": 18.0,
                "alpha_ratio": 1.1,
                # Was 0.7 — far too low: was cutting with Gullfoss but not replacing with warmth.
                # Now 0.95 so tape saturation contributes alongside the Gullfoss taming.
                "tape_color_scale": 0.95,
                "gullfoss_enabled": True,
                "gullfoss_recover": 4.0,
                "gullfoss_tame": 18.0,
                # Was -3.0 (aggressive darkening). Reduced now that tape handles more of the work.
                "gullfoss_brighten": -1.8,
                "gullfoss_boost_db": -0.2,
                "hf_guard_max_reduction_db": 1.8,
                "inflator_enabled": False,
                "bax_enabled": False,
                "ozone_imager_band_2_width_percent": 2.0,
                "ozone_imager_band_3_width_percent": 3.0,
                "ozone_imager_band_4_width_percent": 4.0,
                "source_match_presence_max_db": 1.4,
                "source_match_side_max_db": 2.4,
            },
        ),
        bounded_settings(
            base,
            "analog_warm_punch",
            "tape-led analog warmth: harmonic saturation converts digital shimmer to texture, high energy preserved",
            {
                "internal_chain_lufs": -14.6,
                "soothe_depth_scale": 0.88,
                "soothe1_mix": 28.0,
                "soothe2_depth_scale": 0.09,
                "soothe2_mix": 16.0,
                # Moderate HF compression — compresses, doesn't cut.
                "multipass_macro_cap": 13.0,
                "alpha_ratio": 1.12,
                "alpha_threshold_offset": 0.2,
                # Core of this preset: heavy tape drive generates even harmonics in the HF zone,
                # transforming brittle digital overtones into organic texture without shelving them away.
                # tape_speed stays 30 IPS (default) for extended HF response.
                "tape_color_scale": 1.35,
                "tape_color_offset": 0.4,
                "tape_color_min": 2.0,
                "tape_color_max": 4.2,
                # Gullfoss weighted toward recovery (bring out musical content) over taming.
                # Slight positive brighten to offset any warmth-induced dullness from saturation.
                "gullfoss_recover": 7.0,
                "gullfoss_tame": 9.0,
                "gullfoss_brighten": 0.5,
                "bax_enabled": True,
                "bax_low_shelf_db": 0.25,
                # Adds a whisper of air back to counterbalance tape warmth — keeps presence without shimmer.
                "bax_high_shelf_db": 0.12,
                "bx_digital_enabled": True,
                "bx_stereo_width": 103.0,
                "low_end_focus_enabled": True,
                "low_end_focus_contrast": 8.0,
                "low_end_focus_gain_db": 0.1,
                "inflator_enabled": False,
                "ozone_imager_band_2_width_percent": 5.0,
                "ozone_imager_band_3_width_percent": 8.0,
                "ozone_imager_band_4_width_percent": 10.0,
                # Lighter HF guard — tape handles harshness; the guard is safety net only.
                "hf_guard_max_reduction_db": 0.8,
                "loud_section_min_crest_db": 6.4,
                "loud_section_max_crest_loss_db": 0.65,
                "source_match_presence_max_db": 1.8,
                "source_match_side_max_db": 2.3,
            },
        ),
        bounded_settings(
            base,
            "musical_restore",
            "tone-first musical restoration: analog color, punch, vocal presence, width, and restrained de-harshing",
            {
                "internal_chain_lufs": -14.4,
                "soothe_depth_scale": 0.76,
                "soothe1_mix": 24.0,
                "soothe2_depth_scale": 0.06,
                "soothe2_mix": 12.0,
                "multipass_macro_cap": 11.0,
                "alpha_ratio": 1.12,
                "alpha_threshold_offset": 0.6,
                "tape_color_scale": 1.4,
                "tape_color_offset": 0.55,
                "tape_color_min": 2.2,
                "tape_color_max": 4.6,
                "gullfoss_recover": 8.0,
                "gullfoss_tame": 9.0,
                "gullfoss_brighten": 0.35,
                "bax_enabled": True,
                "bax_low_shelf_db": 0.35,
                "bax_high_shelf_db": 0.18,
                "low_end_focus_enabled": True,
                "low_end_focus_contrast": 12.0,
                "low_end_focus_gain_db": 0.2,
                "bx_digital_enabled": True,
                "bx_stereo_width": 105.0,
                "bx_mono_maker_enabled": True,
                "bx_mono_maker_hz": 85.0,
                "ozone_imager_band_2_width_percent": 7.0,
                "ozone_imager_band_3_width_percent": 12.0,
                "ozone_imager_band_4_width_percent": 15.0,
                "inflator_enabled": False,
                "hf_guard_max_reduction_db": 0.9,
                "loud_section_min_crest_db": 6.7,
                "loud_section_max_crest_loss_db": 0.55,
                "source_match_sub_trim_max_db": 0.25,
                "source_match_presence_max_db": 2.0,
                "source_match_side_max_db": 2.5,
            },
        ),
        bounded_settings(
            base,
            "ai_artifact_repair",
            "AI artifact repair: reduce brittle/time-stretched side highs and phasey fizz while keeping the mid alive",
            {
                "internal_chain_lufs": -15.2,
                "soothe_depth_scale": 1.18,
                "soothe1_mix": 46.0,
                "soothe2_depth_scale": 0.18,
                "soothe2_mix": 26.0,
                "multipass_macro_cap": 22.0,
                "alpha_ratio": 1.1,
                "alpha_threshold_offset": 1.0,
                "tape_color_scale": 1.12,
                "tape_color_offset": 0.2,
                "gullfoss_recover": 4.0,
                "gullfoss_tame": 22.0,
                "gullfoss_brighten": -1.6,
                "gullfoss_boost_db": -0.2,
                "bx_digital_enabled": True,
                "bx_stereo_width": 101.0,
                "bx_mono_maker_enabled": True,
                "bx_mono_maker_hz": 105.0,
                "ozone_imager_band_2_width_percent": 2.0,
                "ozone_imager_band_3_width_percent": 4.0,
                "ozone_imager_band_4_width_percent": 3.0,
                "inflator_enabled": False,
                "hf_guard_frequency_hz": 7500.0,
                "hf_guard_air_to_presence_db": 0.0,
                "hf_guard_max_reduction_db": 2.2,
                "loud_section_min_crest_db": 6.9,
                "loud_section_max_crest_loss_db": 0.45,
                "source_match_presence_max_db": 2.0,
                "source_match_side_max_db": 2.5,
            },
        ),
        bounded_settings(
            base,
            "dynamic_punch_image",
            "dynamic punch and image: stronger low-end shape, wider mids/highs, and stricter chorus crest preservation",
            {
                "internal_chain_lufs": -15.0,
                "soothe_depth_scale": 0.62,
                "soothe1_mix": 18.0,
                "soothe2_depth_scale": 0.04,
                "soothe2_mix": 9.0,
                "multipass_macro_cap": 7.0,
                "alpha_ratio": 1.1,
                "alpha_threshold_offset": 1.5,
                "tape_color_scale": 1.05,
                "tape_color_offset": 0.25,
                "gullfoss_recover": 7.0,
                "gullfoss_tame": 6.0,
                "gullfoss_brighten": 0.3,
                "bax_enabled": True,
                "bax_low_shelf_db": 0.45,
                "bax_high_shelf_db": 0.08,
                "low_end_focus_enabled": True,
                "low_end_focus_contrast": 18.0,
                "low_end_focus_gain_db": 0.25,
                "bx_digital_enabled": True,
                "bx_stereo_width": 106.0,
                "bx_mono_maker_enabled": True,
                "bx_mono_maker_hz": 95.0,
                "ozone_imager_band_2_width_percent": 8.0,
                "ozone_imager_band_3_width_percent": 14.0,
                "ozone_imager_band_4_width_percent": 16.0,
                "inflator_enabled": False,
                "ozone_threshold": -0.6,
                "hf_guard_max_reduction_db": 0.8,
                "loud_section_min_crest_db": 7.2,
                "loud_section_max_crest_loss_db": 0.35,
                "source_match_sub_trim_max_db": 0.2,
                "source_match_presence_max_db": 2.0,
                "source_match_side_max_db": 2.5,
            },
        ),
        bounded_settings(
            base,
            "inflator_weiss_density",
            "perceived loudness and density with Weiss as alternate final maximizer",
            {
                "internal_chain_lufs": -14.7,
                "soothe_depth_scale": 0.82,
                "soothe1_mix": 26.0,
                "soothe2_depth_scale": 0.08,
                "soothe2_mix": 15.0,
                "multipass_macro_cap": 11.0,
                "alpha_ratio": 1.1,
                "tape_color_scale": 0.75,
                "gullfoss_recover": 4.0,
                "gullfoss_tame": 9.0,
                "gullfoss_brighten": -0.2,
                "inflator_enabled": True,
                "inflator_effect": 10.0,
                "inflator_curve": 2.0,
                "inflator_output_gain": -0.7,
                "final_limiter": "weiss_mm1",
                "weiss_amount": 22.0,
                "weiss_style": "Punch",
                "weiss_out_trim_dbfs": -1.0,
                "loud_section_min_crest_db": 6.4,
                "loud_section_max_crest_loss_db": 0.65,
                "ozone_imager_band_2_width_percent": 3.0,
                "ozone_imager_band_3_width_percent": 5.0,
                "ozone_imager_band_4_width_percent": 7.0,
                "source_match_presence_max_db": 2.0,
                "source_match_side_max_db": 2.5,
            },
        ),
        bounded_settings(
            base,
            "emotional_vocal",
            "emotional/vocal-forward: minimal shimmer control, forward presence, light glue, preserved dynamics",
            {
                "internal_chain_lufs": -14.4,
                "soothe_depth_scale": 0.65,
                "soothe1_mix": 20.0,
                "soothe2_depth_scale": 0.05,
                "soothe2_mix": 12.0,
                "multipass_macro_cap": 7.0,
                "alpha_ratio": 1.1,
                "alpha_threshold_offset": 1.2,
                "tape_color_scale": 0.75,
                "gullfoss_recover": 5.0,
                "gullfoss_tame": 6.0,
                "gullfoss_brighten": 0.6,
                "inflator_enabled": False,
                "bx_digital_enabled": True,
                "bx_stereo_width": 101.0,
                "ozone_imager_band_2_width_percent": 3.0,
                "ozone_imager_band_3_width_percent": 5.0,
                "ozone_imager_band_4_width_percent": 6.0,
                "source_match_presence_max_db": 2.0,
                "source_match_side_max_db": 2.2,
                "loud_section_min_crest_db": 7.0,
                "loud_section_max_crest_loss_db": 0.4,
            },
        ),
        bounded_settings(
            base,
            "tight_competitive",
            "tight/competitive pop-EDM: dense and punchy, Weiss maximizer, mono-maker bass, streaming-loud",
            {
                "internal_chain_lufs": -14.2,
                "soothe_depth_scale": 0.9,
                "soothe1_mix": 28.0,
                "multipass_macro_cap": 14.0,
                "alpha_ratio": 1.15,
                "alpha_threshold_offset": -0.3,
                "tape_color_scale": 1.2,
                "tape_color_offset": 0.3,
                "gullfoss_recover": 5.0,
                "gullfoss_tame": 11.0,
                "bax_enabled": True,
                "bax_low_shelf_db": 0.5,
                "low_end_focus_enabled": True,
                "low_end_focus_contrast": 16.0,
                "low_end_focus_gain_db": 0.3,
                "bx_digital_enabled": True,
                "bx_stereo_width": 104.0,
                "bx_mono_maker_enabled": True,
                "bx_mono_maker_hz": 85.0,
                "inflator_enabled": True,
                "inflator_effect": 16.0,
                "inflator_curve": 4.0,
                "inflator_output_gain": -1.0,
                "final_limiter": "weiss_mm1",
                "weiss_amount": 30.0,
                "weiss_style": "Loud",
                "weiss_out_trim_dbfs": -1.0,
                "ozone_imager_band_2_width_percent": 6.0,
                "ozone_imager_band_3_width_percent": 10.0,
                "ozone_imager_band_4_width_percent": 14.0,
                "loud_section_min_crest_db": 6.0,
                "loud_section_max_crest_loss_db": 0.85,
                "source_match_presence_max_db": 1.6,
                "source_match_side_max_db": 2.5,
            },
        ),
    ]
