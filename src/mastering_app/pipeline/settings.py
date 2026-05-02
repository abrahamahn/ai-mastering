"""Bounded mastering settings used by deterministic and AI-assisted renders."""
from __future__ import annotations

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
    proq_shape_enabled: bool = True
    proq_warmth_db: float = 0.0
    proq_punch_db: float = 0.0
    proq_presence_db: float = 0.0
    proq_air_db: float = 0.0
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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


DEFAULT_SETTINGS = MasteringSettings()


SETTING_BOUNDS: dict[str, tuple[float, float]] = {
    "internal_chain_lufs": (-18.0, -12.0),
    "streaming_reference_lufs": (-18.0, -10.0),
    "streaming_loud_target_ceiling_dbfs": (-3.0, -1.0),
    "streaming_normal_target_ceiling_dbfs": (-2.0, -0.8),
    "proq_warmth_db": (-1.0, 1.2),
    "proq_punch_db": (-1.0, 1.2),
    "proq_presence_db": (-1.5, 1.5),
    "proq_air_db": (-2.0, 1.2),
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
}

BOOLEAN_SETTINGS = {
    "corrective_eq_enabled",
    "streaming_profile_enabled",
    "proq_preset",
    "proq_shape_enabled",
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


def candidate_settings(style: str) -> list[MasteringSettings]:
    style_note = style.strip() or "modern pop / EDM"
    base = replace(DEFAULT_SETTINGS, description=f"Suno AI mastering pillars for {style_note}")
    return [
        bounded_settings(
            base,
            "balanced_pillars",
            "balanced master: tame Suno glare, add width, low-mid warmth, and dynamic punch",
            {
                "internal_chain_lufs": -14.7,
                "proq_warmth_db": 0.25,
                "proq_punch_db": 0.15,
                "proq_presence_db": 0.05,
                "proq_air_db": -0.15,
                "soothe_depth_scale": 0.95,
                "soothe1_mix": 30.0,
                "soothe2_depth_scale": 0.10,
                "soothe2_mix": 18.0,
                "multipass_macro_cap": 14.0,
                "alpha_ratio": 1.1,
                "alpha_threshold_offset": 0.5,
                "tape_color_scale": 1.15,
                "tape_color_offset": 0.2,
                "gullfoss_recover": 5.0,
                "gullfoss_tame": 10.0,
                "gullfoss_brighten": -0.2,
                "bax_enabled": True,
                "bax_low_shelf_db": 0.25,
                "bax_high_shelf_db": 0.05,
                "low_end_focus_enabled": True,
                "low_end_focus_contrast": 7.0,
                "low_end_focus_gain_db": 0.1,
                "bx_digital_enabled": True,
                "bx_stereo_width": 103.0,
                "bx_mono_maker_enabled": True,
                "bx_mono_maker_hz": 85.0,
                "ozone_imager_band_2_width_percent": 5.0,
                "ozone_imager_band_3_width_percent": 8.0,
                "ozone_imager_band_4_width_percent": 10.0,
                "hf_guard_max_reduction_db": 1.2,
                "loud_section_min_crest_db": 6.8,
                "loud_section_max_crest_loss_db": 0.55,
                "source_match_enabled": False,
            },
        ),
        bounded_settings(
            base,
            "warm_analog",
            "warm analog: stronger low-mid body, tape color, controlled highs, and relaxed width",
            {
                "internal_chain_lufs": -14.8,
                "proq_warmth_db": 0.55,
                "proq_punch_db": 0.25,
                "proq_presence_db": -0.05,
                "proq_air_db": -0.25,
                "soothe_depth_scale": 0.88,
                "soothe1_mix": 28.0,
                "soothe2_depth_scale": 0.09,
                "soothe2_mix": 16.0,
                "multipass_macro_cap": 12.0,
                "alpha_ratio": 1.1,
                "alpha_threshold_offset": 0.8,
                "tape_color_scale": 1.35,
                "tape_color_offset": 0.45,
                "tape_color_min": 2.0,
                "tape_color_max": 4.2,
                "gullfoss_recover": 7.0,
                "gullfoss_tame": 9.0,
                "gullfoss_brighten": 0.2,
                "bax_enabled": True,
                "bax_low_shelf_db": 0.45,
                "bax_high_shelf_db": 0.05,
                "low_end_focus_enabled": True,
                "low_end_focus_contrast": 9.0,
                "low_end_focus_gain_db": 0.15,
                "bx_digital_enabled": True,
                "bx_mono_maker_enabled": True,
                "bx_mono_maker_hz": 90.0,
                "ozone_imager_band_2_width_percent": 3.0,
                "ozone_imager_band_3_width_percent": 6.0,
                "ozone_imager_band_4_width_percent": 8.0,
                "hf_guard_max_reduction_db": 0.9,
                "loud_section_min_crest_db": 6.7,
                "loud_section_max_crest_loss_db": 0.55,
                "source_match_enabled": False,
            },
        ),
        bounded_settings(
            base,
            "bright_open",
            "bright open: more presence and stereo image with high-end guardrails",
            {
                "internal_chain_lufs": -14.6,
                "proq_warmth_db": 0.15,
                "proq_punch_db": 0.10,
                "proq_presence_db": 0.45,
                "proq_air_db": 0.25,
                "soothe_depth_scale": 0.75,
                "soothe1_mix": 22.0,
                "soothe2_depth_scale": 0.05,
                "soothe2_mix": 10.0,
                "multipass_macro_cap": 10.0,
                "alpha_ratio": 1.1,
                "alpha_threshold_offset": 0.8,
                "tape_color_scale": 1.0,
                "tape_color_offset": 0.2,
                "gullfoss_recover": 7.0,
                "gullfoss_tame": 8.0,
                "gullfoss_brighten": 0.8,
                "bax_enabled": True,
                "bax_low_shelf_db": 0.10,
                "bax_high_shelf_db": 0.25,
                "bx_digital_enabled": True,
                "bx_stereo_width": 105.0,
                "low_end_focus_enabled": True,
                "low_end_focus_contrast": 5.0,
                "low_end_focus_gain_db": 0.0,
                "inflator_enabled": False,
                "ozone_imager_band_2_width_percent": 8.0,
                "ozone_imager_band_3_width_percent": 14.0,
                "ozone_imager_band_4_width_percent": 16.0,
                "hf_guard_ratio_threshold": 0.25,
                "hf_guard_max_reduction_db": 0.7,
                "loud_section_min_crest_db": 6.8,
                "loud_section_max_crest_loss_db": 0.5,
                "source_match_enabled": False,
            },
        ),
        bounded_settings(
            base,
            "deharsh_repair",
            "deharsh repair: stronger Suno high-end distortion control without dulling the low mids",
            {
                "internal_chain_lufs": -15.1,
                "proq_warmth_db": 0.25,
                "proq_punch_db": 0.0,
                "proq_presence_db": -0.15,
                "proq_air_db": -0.65,
                "soothe_depth_scale": 1.15,
                "soothe1_mix": 42.0,
                "soothe2_depth_scale": 0.16,
                "soothe2_mix": 24.0,
                "multipass_macro_cap": 20.0,
                "alpha_ratio": 1.1,
                "alpha_threshold_offset": 1.0,
                "tape_color_scale": 1.15,
                "tape_color_offset": 0.15,
                "gullfoss_recover": 4.0,
                "gullfoss_tame": 18.0,
                "gullfoss_brighten": -1.6,
                "gullfoss_boost_db": -0.2,
                "inflator_enabled": False,
                "bx_digital_enabled": True,
                "bx_stereo_width": 101.0,
                "ozone_imager_band_2_width_percent": 2.0,
                "ozone_imager_band_3_width_percent": 4.0,
                "ozone_imager_band_4_width_percent": 4.0,
                "hf_guard_frequency_hz": 7500.0,
                "hf_guard_air_to_presence_db": 0.0,
                "hf_guard_max_reduction_db": 2.2,
                "loud_section_min_crest_db": 7.0,
                "loud_section_max_crest_loss_db": 0.45,
                "source_match_enabled": False,
            },
        ),
        bounded_settings(
            base,
            "punch_forward",
            "punch forward: stronger kick/sub impact and energy while preserving chorus crest",
            {
                "internal_chain_lufs": -14.6,
                "proq_warmth_db": 0.35,
                "proq_punch_db": 0.50,
                "proq_presence_db": 0.10,
                "proq_air_db": -0.10,
                "soothe_depth_scale": 0.9,
                "soothe1_mix": 28.0,
                "soothe2_depth_scale": 0.08,
                "soothe2_mix": 15.0,
                "multipass_macro_cap": 14.0,
                "alpha_ratio": 1.12,
                "alpha_threshold_offset": 0.2,
                "tape_color_scale": 1.2,
                "tape_color_offset": 0.3,
                "gullfoss_recover": 5.0,
                "gullfoss_tame": 10.0,
                "gullfoss_brighten": -0.1,
                "bax_enabled": True,
                "bax_low_shelf_db": 0.4,
                "low_end_focus_enabled": True,
                "low_end_focus_contrast": 16.0,
                "low_end_focus_gain_db": 0.3,
                "bx_digital_enabled": True,
                "bx_stereo_width": 104.0,
                "bx_mono_maker_enabled": True,
                "bx_mono_maker_hz": 85.0,
                "inflator_enabled": True,
                "inflator_effect": 8.0,
                "inflator_curve": 1.0,
                "inflator_output_gain": -0.6,
                "ozone_imager_band_2_width_percent": 6.0,
                "ozone_imager_band_3_width_percent": 10.0,
                "ozone_imager_band_4_width_percent": 14.0,
                "loud_section_min_crest_db": 6.7,
                "loud_section_max_crest_loss_db": 0.55,
                "source_match_enabled": False,
            },
        ),
    ]
