"""Deterministic comment-to-mastering intent mapping.

This layer makes the free-form style/comment string operational without
depending on an LLM. The mapping is intentionally explicit and auditable:
matched terms become intent tags, tags become bounded setting overrides and
score biases, and the final report records the result.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .settings import MasteringSettings


@dataclass(frozen=True)
class CommentIntent:
    raw_comment: str
    tags: list[str] = field(default_factory=list)
    matched_terms: dict[str, list[str]] = field(default_factory=dict)
    global_overrides: dict[str, Any] = field(default_factory=dict)
    candidate_overrides: dict[str, dict[str, Any]] = field(default_factory=dict)
    score_bias: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


TERM_GROUPS: dict[str, list[str]] = {
    "dynamic_guard": [
        "less squashed",
        "too squashed",
        "overly squashed",
        "over compressed",
        "over-compressed",
        "overcompressed",
        "too compressed",
        "less compressed",
        "more dynamic",
        "preserve dynamics",
        "avoid squashing",
        "loudest part",
        "loudest section",
        "chorus",
        "drop",
    ],
    "deharsh": [
        "harsh",
        "brittle",
        "shimmer",
        "digital shimmer",
        "sibilant",
        "sibilance",
        "glassy",
        "piercing",
        "sharp high",
        "painful high",
        "cleaner high",
        "de harsh",
        "de-harsh",
    ],
    "bright_open": [
        "bright",
        "open",
        "airy",
        "air",
        "chainsmokers",
        "edm",
        "pop edm",
        "modern pop",
        "release ready",
        "finished pop",
    ],
    "dark_muffled": [
        "muffled",
        "dark",
        "dull",
        "veiled",
        "blanket",
        "not open",
        "lost presence",
        "presence pulled back",
    ],
    "wide_stereo": [
        "wide",
        "wider",
        "stereo",
        "image",
        "spacious",
        "bigger",
        "less narrow",
        "narrower",
        "narrow",
    ],
    "punch_warm": [
        "punch",
        "punchy",
        "warm",
        "warmer",
        "low mid",
        "low-mid",
        "body",
        "weight",
        "bass",
        "sub",
        "kick",
        "analog",
        "analogue",
        "tape",
        "vintage",
        "organic",
        "harmonic",
        "less digital",
        "not digital",
    ],
    "clean_preserve": [
        "clean",
        "transparent",
        "natural",
        "preserve",
        "preserve original",
        "like original",
        "original sounds better",
        "subtle",
        "minimal",
    ],
    "loud_dense": [
        "loud",
        "louder",
        "perceived loudness",
        "perceivedly loud",
        "same volume",
        "competitive",
        "density",
        "dense",
        "finished",
        "polished",
    ],
    "streaming": [
        "streaming",
        "streaming service",
        "streaming services",
        "spotify",
        "apple music",
        "youtube",
        "normalization",
        "normalized",
        "lufs",
    ],
    "vocal_forward": [
        "vocal",
        "vocals",
        "voice",
        "lyrics",
        "forward",
        "presence",
        "emotional",
        "immediate",
    ],
}


def parse_comment_intent(comment: str) -> CommentIntent:
    text = _normalize(comment)
    matched_terms: dict[str, list[str]] = {}
    tags: list[str] = []
    for tag, terms in TERM_GROUPS.items():
        matches = _matched(text, terms)
        if matches:
            tags.append(tag)
            matched_terms[tag] = matches

    global_overrides: dict[str, Any] = {}
    candidate_overrides: dict[str, dict[str, Any]] = {}
    score_bias: dict[str, float] = {}
    notes: list[str] = []

    def global_set(values: dict[str, Any]) -> None:
        global_overrides.update(values)

    def candidate_set(name: str, values: dict[str, Any]) -> None:
        candidate_overrides.setdefault(name, {}).update(values)

    def bias(name: str, value: float) -> None:
        score_bias[name] = round(score_bias.get(name, 0.0) + value, 3)

    if "bright_open" in tags:
        global_set({
            "source_match_presence_max_db": 1.8,
            "source_match_side_max_db": 2.4,
            "ozone_imager_band_2_width_percent": 5.0,
            "ozone_imager_band_3_width_percent": 8.0,
            "ozone_imager_band_4_width_percent": 11.0,
        })
        candidate_set("bright_open_edm", {
            "gullfoss_recover": 7.0,
            "gullfoss_tame": 8.0,
            "gullfoss_brighten": 1.0,
            "bax_high_shelf_db": 0.2,
        })
        bias("streaming_loud_open", 3.0)
        bias("streaming_polish_plus", 4.0)
        bias("bright_open_edm", 5.0)
        bias("musical_restore", 4.0)
        bias("dynamic_punch_image", 3.0)
        bias("preserve_open", 2.0)
        notes.append("bright/open comment: favor open EDM candidate and wider high bands")

    if "streaming" in tags:
        global_set({
            "streaming_profile_enabled": True,
            "streaming_reference_lufs": -14.0,
            "streaming_normal_target_ceiling_dbfs": -1.0,
            "streaming_loud_target_ceiling_dbfs": -2.0,
            "loud_section_guard_enabled": True,
            "loud_section_min_crest_db": 6.4,
            "loud_section_max_crest_loss_db": 0.65,
            "hf_guard_enabled": True,
            "hf_guard_ratio_threshold": 0.22,
            "hf_guard_air_to_presence_db": 0.3,
            "hf_guard_max_reduction_db": 1.4,
        })
        bias("streaming_loud_open", 6.0)
        bias("streaming_polish_plus", 8.0)
        bias("punch_warm_dynamic", 3.0)
        bias("inflator_weiss_density", -2.0)
        notes.append("streaming comment: optimize normalized playback loudness, headroom, and chorus crest")

    if "dark_muffled" in tags:
        global_set({
            "soothe_depth_scale": 0.65,
            "soothe1_mix": 22.0,
            "soothe2_depth_scale": 0.05,
            "soothe2_mix": 10.0,
            "multipass_macro_cap": 5.0,
            "gullfoss_tame": 4.0,
            "gullfoss_brighten": 2.0,
            "source_match_presence_max_db": 2.0,
        })
        candidate_set("bright_open_edm", {
            "gullfoss_recover": 8.0,
            "gullfoss_brighten": 3.0,
            "bax_high_shelf_db": 0.45,
        })
        bias("bright_open_edm", 7.0)
        bias("deharsh_gullfoss", -5.0)
        bias("controlled_shimmer", -3.0)
        notes.append("muffled/dark comment: reduce de-harshing pressure and restore presence")

    if "deharsh" in tags:
        global_set({
            "multipass_macro_cap": 16.0,
            "gullfoss_tame": 12.0,
            "gullfoss_brighten": -1.0,
            # Don't lower tape on harsh sources — saturation is part of the fix.
            "tape_color_scale": 1.0,
            "hf_guard_enabled": True,
            "hf_guard_max_reduction_db": 1.8,
        })
        candidate_set("controlled_shimmer", {
            "gullfoss_recover": 5.0,
            "gullfoss_tame": 17.0,
            "gullfoss_brighten": -1.5,
            "multipass_macro_cap": 18.0,
        })
        candidate_set("deharsh_gullfoss", {
            "gullfoss_recover": 3.0,
            "gullfoss_tame": 22.0,
            "gullfoss_brighten": -2.5,
            "multipass_macro_cap": 20.0,
        })
        candidate_set("analog_warm_punch", {
            "gullfoss_tame": 11.0,
            "multipass_macro_cap": 16.0,
            "hf_guard_max_reduction_db": 1.0,
        })
        candidate_set("ai_artifact_repair", {
            "gullfoss_tame": 24.0,
            "multipass_macro_cap": 23.0,
            "hf_guard_max_reduction_db": 2.3,
        })
        candidate_set("bright_open_edm", {
            "gullfoss_tame": 11.0,
            "gullfoss_brighten": 0.2,
        })
        bias("streaming_loud_open", 4.0)
        bias("streaming_polish_plus", 3.0)
        bias("analog_warm_punch", 6.0)
        bias("musical_restore", 6.0)
        bias("ai_artifact_repair", 8.0)
        bias("deharsh_gullfoss", 7.0)
        bias("controlled_shimmer", 5.0)
        notes.append("harsh high-end comment: bias tape-led analog warmth alongside Gullfoss/Multipass de-harshing")

    if "wide_stereo" in tags:
        global_set({
            "bx_digital_enabled": True,
            "bx_stereo_width": 104.0,
            "ozone_imager_band_2_width_percent": 7.0,
            "ozone_imager_band_3_width_percent": 11.0,
            "ozone_imager_band_4_width_percent": 14.0,
            "source_match_side_max_db": 2.5,
        })
        bias("bright_open_edm", 4.0)
        bias("dynamic_punch_image", 5.0)
        bias("musical_restore", 4.0)
        bias("preserve_open", 3.0)
        notes.append("wide/stereo comment: enable width-preserving stages and bias open candidates")

    if "punch_warm" in tags:
        global_set({
            "bax_enabled": True,
            "bax_low_shelf_db": 0.35,
            "low_end_focus_enabled": True,
            "low_end_focus_contrast": 7.0,
            "low_end_focus_gain_db": 0.1,
            "tape_color_scale": 1.1,
            "source_match_sub_trim_max_db": 1.4,
        })
        candidate_set("punch_warm", {
            "bax_low_shelf_db": 0.55,
            "low_end_focus_contrast": 12.0,
            "low_end_focus_gain_db": 0.25,
            "tape_color_scale": 1.2,
        })
        candidate_set("punch_warm_dynamic", {
            "bax_low_shelf_db": 0.45,
            "low_end_focus_contrast": 8.0,
            "low_end_focus_gain_db": 0.1,
        })
        candidate_set("analog_warm_punch", {
            "tape_color_scale": 1.4,
            "tape_color_offset": 0.5,
            "gullfoss_recover": 8.0,
            "bax_high_shelf_db": 0.15,
        })
        candidate_set("musical_restore", {
            "tape_color_scale": 1.4,
            "tape_color_offset": 0.6,
            "low_end_focus_contrast": 14.0,
            "bax_low_shelf_db": 0.45,
        })
        candidate_set("dynamic_punch_image", {
            "low_end_focus_contrast": 20.0,
            "low_end_focus_gain_db": 0.3,
            "loud_section_min_crest_db": 7.3,
        })
        bias("musical_restore", 9.0)
        bias("dynamic_punch_image", 7.0)
        bias("analog_warm_punch", 8.0)
        bias("punch_warm", 6.0)
        bias("punch_warm_dynamic", 5.0)
        notes.append("analog/warm comment: favor tape-led harmonic saturation candidate and low-mid warmth")

    if "dynamic_guard" in tags:
        global_set({
            "loud_section_guard_enabled": True,
            "loud_section_min_crest_db": 6.8,
            "loud_section_max_crest_loss_db": 0.55,
            "alpha_threshold_offset": 1.2,
            "alpha_ratio": 1.1,
            "ozone_threshold": -0.8,
        })
        candidate_set("bright_open_edm", {
            "inflator_effect": 5.0,
            "inflator_curve": 1.0,
            "inflator_output_gain": -0.6,
        })
        candidate_set("punch_warm", {
            "inflator_effect": 4.0,
            "inflator_curve": 0.0,
            "inflator_output_gain": -0.6,
        })
        candidate_set("inflator_weiss_density", {
            "inflator_effect": 7.0,
            "weiss_amount": 18.0,
            "weiss_style": "Transparent",
        })
        bias("punch_warm_dynamic", 9.0)
        bias("dynamic_punch_image", 9.0)
        bias("ai_artifact_repair", 4.0)
        bias("preserve_open", 4.0)
        bias("original", 2.0)
        bias("inflator_weiss_density", -6.0)
        notes.append("less-squashed comment: stricter loud-section crest guard and lower density bias")

    if "clean_preserve" in tags:
        global_set({
            "soothe_depth_scale": 0.65,
            "soothe1_mix": 20.0,
            "soothe2_depth_scale": 0.04,
            "soothe2_mix": 10.0,
            "multipass_macro_cap": 5.0,
            "alpha_threshold_offset": 1.2,
            "tape_color_scale": 0.75,
            "inflator_enabled": False,
            "source_match_presence_max_db": 2.0,
            "source_match_side_max_db": 2.5,
        })
        bias("original", 5.0)
        bias("preserve_open", 7.0)
        bias("inflator_weiss_density", -5.0)
        notes.append("clean/preserve comment: lower processing depth and favor original/preserve")

    if "loud_dense" in tags and "dynamic_guard" not in tags:
        global_set({
            "inflator_enabled": True,
            "inflator_effect": 7.0,
            "inflator_curve": 1.0,
            "inflator_output_gain": -0.5,
            "ozone_threshold": -0.9,
            "loud_section_min_crest_db": 6.3,
            "loud_section_max_crest_loss_db": 0.7,
        })
        bias("streaming_loud_open", 4.0)
        bias("streaming_polish_plus", 9.0)
        bias("musical_restore", 5.0)
        bias("inflator_weiss_density", 3.0)
        bias("bright_open_edm", 3.0)
        notes.append("loud/dense comment: favor perceived density without pushing raw LUFS")

    if "vocal_forward" in tags:
        global_set({
            "source_match_presence_max_db": 2.0,
            "gullfoss_recover": 6.0,
            "gullfoss_tame": 8.0,
            "gullfoss_brighten": 0.4,
            "bax_high_shelf_db": 0.15,
        })
        bias("streaming_loud_open", 2.0)
        bias("streaming_polish_plus", 3.0)
        bias("bright_open_edm", 4.0)
        bias("musical_restore", 4.0)
        bias("dynamic_punch_image", 2.0)
        bias("preserve_open", 3.0)
        notes.append("vocal-forward comment: preserve/restore presence and air")

    if not tags:
        notes.append("no deterministic comment terms matched; using neutral candidate settings")

    return CommentIntent(
        raw_comment=comment,
        tags=tags,
        matched_terms=matched_terms,
        global_overrides=global_overrides,
        candidate_overrides=candidate_overrides,
        score_bias=score_bias,
        notes=notes,
    )


def apply_intent_to_settings(
    settings_list: list[MasteringSettings],
    intent: CommentIntent,
) -> list[MasteringSettings]:
    from .settings import bounded_settings

    if not intent.global_overrides and not intent.candidate_overrides:
        return settings_list

    adjusted: list[MasteringSettings] = []
    for settings in settings_list:
        overrides = dict(intent.global_overrides)
        overrides.update(intent.candidate_overrides.get(settings.name, {}))
        if overrides:
            adjusted.append(
                bounded_settings(
                    settings,
                    settings.name,
                    f"{settings.description} | comment intent: {', '.join(intent.tags) or 'neutral'}",
                    overrides,
                )
            )
        else:
            adjusted.append(settings)
    return adjusted


def apply_intent_score_bias(candidates: list[dict[str, Any]], intent: CommentIntent) -> None:
    for candidate in candidates:
        bias = intent.score_bias.get(candidate.get("name", ""), 0.0)
        if not bias:
            continue
        candidate["score"] = float(round(float(candidate.get("score", 0.0)) + bias, 3))
        candidate["intent_score_bias"] = bias
        candidate.setdefault("score_notes", []).append(f"comment intent {bias:+.1f}")


def _normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[_/]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _matched(text: str, terms: list[str]) -> list[str]:
    found = []
    for term in terms:
        pattern = r"(?<![a-z0-9])" + re.escape(term.lower()) + r"(?![a-z0-9])"
        if re.search(pattern, text):
            found.append(term)
    return found
