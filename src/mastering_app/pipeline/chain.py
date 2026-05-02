"""Mastering chain — staged per-plugin signal analysis."""
from __future__ import annotations

from typing import Any
import numpy as np
from pathlib import Path
from pedalboard import Pedalboard, load_plugin

from ..audio.corrective_eq import EqMove, apply_corrective_eq, build_corrective_eq_plan
from ..audio.analysis import (
    measure_band_db,
    measure_integrated_lufs,
    measure_hf_ratio,
    measure_spectral_flatness,
    measure_crest_factor,
    measure_loudest_window,
    measure_stereo_correlation,
    resolve_loud_section_crest_floor,
    scale_soothe_depth,
    scale_multipass_macro,
    scale_alpha_threshold,
    scale_tape_drive,
)
from ..paths import PRESETS_DIR
from .settings import DEFAULT_SETTINGS, MasteringSettings

PRESETS = PRESETS_DIR
VST3 = Path('C:/Program Files/Common Files/VST3')

# Cache plugin instances across process() calls. Pedalboard resets DSP state per audio
# buffer, so the same plugin object can be reused safely. Each candidate still sets its
# own parameters via _try_set() before every _apply() call.
_PLUGIN_CACHE: dict[tuple[str, str | None], Any] = {}

# ── VST3 install paths (update if plugin is installed in a non-standard location) ──
PLUGIN_PATHS: dict[str, Path] = {
    'proq3':        VST3 / 'FabFilter Pro-Q 3.vst3',
    'veq_mg4':      VST3 / 'AA_VEQ-MG4+.vst3',
    'soothe2':      VST3 / 'soothe2_x64.vst3',
    'multipass':    VST3 / 'Kilohearts/Multipass.vst3',
    'alpha_master': VST3 / 'elysia alpha master.vst3',
    'tape':         VST3 / 'Tape.vst3/Contents/x86_64-win/Tape.vst3',
    'gullfoss_master': VST3 / 'Gullfoss Master.vst3',
    'ozone_low_end_focus': VST3 / 'iZotope/Ozone 9 Low End Focus.vst3',
    'ozone_imager': VST3 / 'iZotope/Ozone 9 Imager.vst3',
    'oxford_inflator': VST3 / 'Oxford Inflator Native.vst3/Contents/x86_64-win/Oxford Inflator Native.vst3',
    'weiss_mm1':    VST3 / 'Weiss MM-1 Mastering Maximizer.vst3/Contents/x86_64-win/Weiss MM-1 Mastering Maximizer.vst3',
    'bx_digital_v3': VST3 / 'bx_digital V3.vst3',
    'dangerous_bax_master': VST3 / 'Dangerous BAX EQ Master.vst3',
    'ozone9':       VST3 / 'iZotope/Ozone 9.vst3',
}

# ── Known parameter names (run `python master.py discover <key>` to verify) ──
# These names are from the Windows VST3 discovery output for this machine.
PARAMS: dict[str, dict[str, str]] = {
    'soothe2': {
        'depth':      'depth',
        'sharpness':  'sharpness',
        'selectivity': 'selectivity',
        'mix':        'mix',
    },
    'multipass': {
        # Macro 1 is the stable automation surface for the saved preset.
        # Map it inside Multipass to the high-band compression/harshness control.
        'hf_macro': 'macro_1',
    },
    'alpha_master': {
        'threshold_1': 'threshold_1_db',
        'threshold_2': 'threshold_2_db',
        'ratio_1':     'ratio_1',
        'ratio_2':     'ratio_2',
    },
    'tape': {
        'color_amount': 'color_amount',
        'noise':        'noise',
        'tape_speed':   'tape_speed',
    },
    'gullfoss_master': {
        'recover': 'recover',
        'tame': 'tame',
        'brighten': 'brighten',
        'boost_db': 'boost_db',
        'bias': 'bias',
        'gain_db': 'gain_db',
        'bypass': 'bypass',
    },
    'dangerous_bax_master': {
        'link': 'link',
        'low_shelf_level_1_db': 'low_shelf_level_1_db',
        'low_shelf_level_2_db': 'low_shelf_level_2_db',
        'high_shelf_level_1_db': 'high_shelf_level_1_db',
        'high_shelf_level_2_db': 'high_shelf_level_2_db',
        'output_level_1_db': 'output_level_1_db',
        'output_level_2_db': 'output_level_2_db',
        'bypass': 'bypass',
    },
    'bx_digital_v3': {
        'modus': 'modus',
        'stereo_width': 'stereo_width',
        'mono_maker_active': 'mono_maker_active',
        'mono_maker_frequency_hz': 'mono_maker_frequency_hz',
        'auto_listen_active': 'auto_listen_active',
        'auto_solo': 'auto_solo',
        'solo_1': 'solo_1',
        'solo_2': 'solo_2',
        'bypass': 'bypass',
    },
    'ozone_low_end_focus': {
        'global_bypass': 'global_bypass',
        'lef_bypass': 'lef_bypass',
        'lef_mid_bypass': 'lef_mid_bypass',
        'lef_side_bypass': 'lef_side_bypass',
        'lef_st_mid_mode': 'lef_st_mid_mode',
        'lef_side_mode': 'lef_side_mode',
        'lef_st_mid_contrast': 'lef_st_mid_contrast',
        'lef_side_contrast': 'lef_side_contrast',
        'lef_st_mid_gain': 'lef_st_mid_gain',
        'lef_side_gain': 'lef_side_gain',
        'lef_st_mid_action_region_low': 'lef_st_mid_action_region_low',
        'lef_st_mid_action_region_high': 'lef_st_mid_action_region_high',
        'lef_side_action_region_low': 'lef_side_action_region_low',
        'lef_side_action_region_high': 'lef_side_action_region_high',
    },
    'ozone_imager': {
        'global_bypass': 'global_bypass',
        'img_bypass': 'img_bypass',
        'img_link_bands': 'img_link_bands',
        'img_band_1_width_percent': 'img_band_1_width_percent',
        'img_band_2_width_percent': 'img_band_2_width_percent',
        'img_band_3_width_percent': 'img_band_3_width_percent',
        'img_band_4_width_percent': 'img_band_4_width_percent',
        'img_enable_stereoizer': 'img_enable_stereoizer',
        'img_stereoizer_delay_ms': 'img_stereoizer_delay_ms',
    },
    'oxford_inflator': {
        'effect': 'effect',
        'curve': 'curve',
        'input_gain': 'input_gain',
        'output_gain': 'output_gain',
        'clip_0db': 'clip_0db',
        'band_split': 'band_split',
        'sonnox_bypass': 'sonnox_bypass',
    },
    'weiss_mm1': {
        'amount': 'amount',
        'bypass': 'bypass',
        'limiter_gain_db': 'limiter_gain_db',
        'out_trim_dbfs': 'out_trim_dbfs',
        'parallel_mix': 'parallel_mix',
        'style': 'style',
    },
    'ozone9': {
        'max_threshold':  'max_threshold',
        'max_ceiling':    'max_ceiling',
        'max_true_peak':  'max_true_peak_limiting',
        'max_link':       'max_link_threshold_and_ceiling',
        'dyn_bypass':     'dyn_bypass',
        'dyneq_bypass':   'dyneq_bypass',
        'exc_bypass':     'exc_bypass',
        'vcomp_bypass':   'vcomp_bypass',
        'veq_bypass':     'veq_bypass',
        'vlm_bypass':     'vlm_bypass',
        'vtape_bypass':   'vtape_bypass',
        'spshpr_bypass':  'spshpr_bypass',
        'mrb_bypass':     'mrb_bypass',
        'match_eq_bypass': 'match_eq_bypass',
        'lef_bypass':     'lef_bypass',
    },
}


def _load(key: str, preset: str | None = None):
    cache_key = (key, preset)
    if cache_key in _PLUGIN_CACHE:
        return _PLUGIN_CACHE[cache_key]
    path = PLUGIN_PATHS[key]
    if not path.exists():
        raise FileNotFoundError(f"VST3 not found: {path}")
    plugin = load_plugin(str(path))
    if preset:
        preset_path = PRESETS / preset
        if preset_path.exists():
            plugin.load_preset(str(preset_path))
        else:
            print(f"  [chain] WARNING: preset not found for {key}: {preset_path.name} (using plugin defaults)")
    _PLUGIN_CACHE[cache_key] = plugin
    return plugin


def _apply(plugin, audio: np.ndarray, sr: int) -> np.ndarray:
    return Pedalboard([plugin])(audio, sr)


def _gain(audio: np.ndarray, db: float) -> np.ndarray:
    return audio * (10.0 ** (db / 20.0))


def _try_set(plugin, param: str, value: object) -> None:
    """Set a plugin parameter by name; warn on failure instead of crashing."""
    try:
        setattr(plugin, param, value)
    except (AttributeError, TypeError, ValueError) as exc:
        print(
            f"  [chain] WARNING: could not set parameter '{param}' "
            f"on {type(plugin).__name__}: {exc}"
        )


def _streaming_ceiling_for_target(target_lufs: float, settings: MasteringSettings) -> float:
    if not settings.streaming_profile_enabled:
        return settings.ozone_ceiling
    if target_lufs > settings.streaming_reference_lufs:
        return settings.streaming_loud_target_ceiling_dbfs
    return settings.streaming_normal_target_ceiling_dbfs


def _apply_hf_guard(audio: np.ndarray, sr: int, settings: MasteringSettings) -> tuple[np.ndarray, dict[str, float]]:
    """Post-color high-frequency guard for codec/streaming harshness.

    This runs after tape/inflator because those stages can add density and edge
    that was not visible to the initial corrective EQ analysis.
    """
    if not settings.hf_guard_enabled:
        return audio, {
            "hf_ratio": measure_hf_ratio(audio, sr, threshold_hz=8000.0),
            "air_to_presence_db": 0.0,
            "reduction_db": 0.0,
        }

    hf_ratio = measure_hf_ratio(audio, sr, threshold_hz=8000.0)
    air_db = measure_band_db(audio, sr, settings.hf_guard_frequency_hz, min(16000.0, sr * 0.45))
    presence_db = measure_band_db(audio, sr, 2500.0, 7000.0)
    air_to_presence_db = air_db - presence_db
    ratio_pressure = max(0.0, hf_ratio - settings.hf_guard_ratio_threshold) * 7.5
    air_pressure = max(0.0, air_to_presence_db - settings.hf_guard_air_to_presence_db) * 0.22
    reduction_db = float(np.clip(ratio_pressure + air_pressure, 0.0, settings.hf_guard_max_reduction_db))

    if reduction_db < 0.15:
        return audio, {
            "hf_ratio": hf_ratio,
            "air_to_presence_db": air_to_presence_db,
            "reduction_db": 0.0,
        }

    moves = [
        EqMove(
            "high_shelf",
            settings.hf_guard_frequency_hz,
            -reduction_db,
            None,
            "post-color streaming HF guard",
        )
    ]
    return apply_corrective_eq(audio, sr, moves), {
        "hf_ratio": hf_ratio,
        "air_to_presence_db": air_to_presence_db,
        "reduction_db": reduction_db,
    }


def _candidate_eq_shape(settings: MasteringSettings) -> list[EqMove]:
    """Candidate-specific tone moves for the Pro-Q/corrective EQ slot."""
    if not settings.proq_shape_enabled:
        return []

    moves: list[EqMove] = []
    if abs(settings.proq_punch_db) >= 0.05:
        moves.append(EqMove("bell", 95.0, settings.proq_punch_db, 0.9, "candidate punch shape"))
    if abs(settings.proq_warmth_db) >= 0.05:
        moves.append(EqMove("bell", 280.0, settings.proq_warmth_db, 0.85, "candidate low-mid warmth shape"))
    if abs(settings.proq_presence_db) >= 0.05:
        moves.append(EqMove("bell", 2800.0, settings.proq_presence_db, 1.0, "candidate presence shape"))
    if abs(settings.proq_air_db) >= 0.05:
        moves.append(EqMove("high_shelf", settings.hf_guard_frequency_hz, settings.proq_air_db, None, "candidate air shape"))
    return moves


def process(audio: np.ndarray, sr: int, target_lufs: float, settings: MasteringSettings | None = None) -> np.ndarray:
    """Run the mastering chain with staged per-plugin analysis.

    audio: (channels, samples) float32
    Returns: (channels, samples) float32
    """

    settings = settings or DEFAULT_SETTINGS
    stage_number = 1

    def stage(message: str) -> None:
        nonlocal stage_number
        print(f"  [{stage_number:02d}] {message}")
        stage_number += 1

    # Keep analog stages at a stable operating level. Final loudness is handled
    # after tone/compression, not by driving the whole chain harder.
    input_lufs = measure_integrated_lufs(audio, sr)
    source_loud_section = measure_loudest_window(audio, sr, settings.loud_section_seconds)
    loud_section_crest_floor = resolve_loud_section_crest_floor(
        source_loud_section["crest_db"],
        settings.loud_section_min_crest_db,
        settings.loud_section_max_crest_loss_db,
    )
    pre_gain_db = float(np.clip(settings.internal_chain_lufs - input_lufs, -12.0, 12.0))
    print(f"  Input LUFS: {input_lufs:.1f} - chain gain: {pre_gain_db:+.1f} dB")
    if settings.loud_section_guard_enabled:
        print(
            "  Loudest section: "
            f"{source_loud_section['start_seconds']:.1f}-{source_loud_section['end_seconds']:.1f}s, "
            f"crest={source_loud_section['crest_db']:.1f} dB -> floor={loud_section_crest_floor:.1f} dB"
        )
    audio = _gain(audio, pre_gain_db)

    # ── Stage 1: Dynamic corrective EQ + Pro-Q 3 ─────────────────────────────
    # FabFilter parameter IDs are not stable enough to automate blindly, so the
    # per-song corrective moves are applied here with channel-linked filters.
    corrective_moves = build_corrective_eq_plan(audio, sr) if settings.corrective_eq_enabled else []
    shape_moves = _candidate_eq_shape(settings)
    eq_moves = [*corrective_moves, *shape_moves]
    stage(f"Dynamic EQ + candidate shape + Pro-Q 3  ({len(eq_moves)} moves)")
    for move in eq_moves:
        if move.kind == "highpass":
            print(f"        {move.kind:10s} {move.frequency_hz:7.0f} Hz  ({move.reason})")
        elif move.q is None:
            print(f"        {move.kind:10s} {move.frequency_hz:7.0f} Hz  {move.gain_db:+.1f} dB  ({move.reason})")
        else:
            print(
                f"        {move.kind:10s} {move.frequency_hz:7.0f} Hz  "
                f"{move.gain_db:+.1f} dB  Q={move.q:.1f}  ({move.reason})"
            )
    audio = apply_corrective_eq(audio, sr, eq_moves)
    proq3 = _load('proq3', 'Pro-Q 3.vstpreset' if settings.proq_preset else None)
    audio = _apply(proq3, audio, sr)

    if settings.gullfoss_enabled:
        stage(
            "Gullfoss Master  "
            f"(recover={settings.gullfoss_recover:.1f}, tame={settings.gullfoss_tame:.1f}, "
            f"brighten={settings.gullfoss_brighten:.1f})"
        )
        gullfoss = _load('gullfoss_master')
        _try_set(gullfoss, PARAMS['gullfoss_master']['bypass'], False)
        _try_set(gullfoss, PARAMS['gullfoss_master']['recover'], settings.gullfoss_recover)
        _try_set(gullfoss, PARAMS['gullfoss_master']['tame'], settings.gullfoss_tame)
        _try_set(gullfoss, PARAMS['gullfoss_master']['brighten'], settings.gullfoss_brighten)
        _try_set(gullfoss, PARAMS['gullfoss_master']['boost_db'], settings.gullfoss_boost_db)
        _try_set(gullfoss, PARAMS['gullfoss_master']['bias'], settings.gullfoss_bias)
        _try_set(gullfoss, PARAMS['gullfoss_master']['gain_db'], 0.0)
        audio = _apply(gullfoss, audio, sr)

    # ── Stage 2: Multipass — early HF artifact trim ──────────────────────────
    # Analyze after corrective EQ/Gullfoss but before broad tone colour, so the
    # fake AI shimmer is controlled before it gets saturated or widened.
    hf_ratio = measure_hf_ratio(audio, sr, threshold_hz=8000.0)
    hf_macro = min(scale_multipass_macro(hf_ratio), settings.multipass_macro_cap)
    stage(f"Multipass  (hf_ratio={hf_ratio:.3f} -> macro_1={hf_macro:.1f}%)")
    mp = _load('multipass', 'Multipass.vstpreset')
    _try_set(mp, PARAMS['multipass']['hf_macro'], hf_macro)
    audio = _apply(mp, audio, sr)

    # ── Stage 3: soothe2 pass 1 — resonance suppression ──────────────────────
    # Analyze after early HF trim: remaining narrowness determines pass depth.
    flatness = measure_spectral_flatness(audio, sr)
    depth = scale_soothe_depth(flatness)
    depth *= settings.soothe_depth_scale
    stage(f"soothe2 pass 1  (flatness={flatness:.3f} -> depth={depth:.2f})")
    s1 = _load('soothe2', 'soothe2-1.vstpreset')
    _try_set(s1, PARAMS['soothe2']['depth'], depth)
    _try_set(s1, PARAMS['soothe2']['mix'], settings.soothe1_mix)
    audio = _apply(s1, audio, sr)

    # ── Stage 4: soothe2 pass 2 — fine resonance pass ────────────────────────
    # Re-analyze AFTER pass 1: remaining resonance determines second-pass depth.
    flatness2 = measure_spectral_flatness(audio, sr)
    depth2 = scale_soothe_depth(flatness2) * settings.soothe2_depth_scale
    stage(f"soothe2 pass 2  (flatness={flatness2:.3f} -> depth={depth2:.2f})")
    s2 = _load('soothe2', 'soothe2-2.vstpreset')
    _try_set(s2, PARAMS['soothe2']['depth'], depth2)
    _try_set(s2, PARAMS['soothe2']['mix'], settings.soothe2_mix)
    audio = _apply(s2, audio, sr)

    # ── Stage 5: VEQ-MG4+ — vintage EQ colour ────────────────────────────────
    # Broad analogue colour happens after cleanup so it adds tone instead of
    # exaggerating resonances and AI edge.
    stage("VEQ-MG4+")
    veq = _load('veq_mg4', 'VEQ-MG4+.vstpreset')
    audio = _apply(veq, audio, sr)

    if settings.bax_enabled:
        stage(
            "Dangerous BAX EQ Master  "
            f"(low={settings.bax_low_shelf_db:+.1f} dB, high={settings.bax_high_shelf_db:+.1f} dB)"
        )
        bax = _load('dangerous_bax_master')
        _try_set(bax, PARAMS['dangerous_bax_master']['bypass'], False)
        _try_set(bax, PARAMS['dangerous_bax_master']['link'], True)
        _try_set(bax, PARAMS['dangerous_bax_master']['low_shelf_level_1_db'], settings.bax_low_shelf_db)
        _try_set(bax, PARAMS['dangerous_bax_master']['low_shelf_level_2_db'], settings.bax_low_shelf_db)
        _try_set(bax, PARAMS['dangerous_bax_master']['high_shelf_level_1_db'], settings.bax_high_shelf_db)
        _try_set(bax, PARAMS['dangerous_bax_master']['high_shelf_level_2_db'], settings.bax_high_shelf_db)
        _try_set(bax, PARAMS['dangerous_bax_master']['output_level_1_db'], 0.0)
        _try_set(bax, PARAMS['dangerous_bax_master']['output_level_2_db'], 0.0)
        audio = _apply(bax, audio, sr)

    if settings.low_end_focus_enabled:
        stage(
            "Ozone Low End Focus  "
            f"(contrast={settings.low_end_focus_contrast:.1f}, gain={settings.low_end_focus_gain_db:+.1f} dB)"
        )
        lef = _load('ozone_low_end_focus')
        _try_set(lef, PARAMS['ozone_low_end_focus']['global_bypass'], False)
        _try_set(lef, PARAMS['ozone_low_end_focus']['lef_bypass'], False)
        _try_set(lef, PARAMS['ozone_low_end_focus']['lef_mid_bypass'], False)
        _try_set(lef, PARAMS['ozone_low_end_focus']['lef_side_bypass'], False)
        _try_set(lef, PARAMS['ozone_low_end_focus']['lef_st_mid_mode'], settings.low_end_focus_mode)
        _try_set(lef, PARAMS['ozone_low_end_focus']['lef_side_mode'], settings.low_end_focus_mode)
        _try_set(lef, PARAMS['ozone_low_end_focus']['lef_st_mid_contrast'], settings.low_end_focus_contrast)
        _try_set(lef, PARAMS['ozone_low_end_focus']['lef_side_contrast'], settings.low_end_focus_contrast)
        _try_set(lef, PARAMS['ozone_low_end_focus']['lef_st_mid_gain'], settings.low_end_focus_gain_db)
        _try_set(lef, PARAMS['ozone_low_end_focus']['lef_side_gain'], settings.low_end_focus_gain_db)
        _try_set(lef, PARAMS['ozone_low_end_focus']['lef_st_mid_action_region_low'], settings.low_end_focus_region_low_hz)
        _try_set(lef, PARAMS['ozone_low_end_focus']['lef_st_mid_action_region_high'], settings.low_end_focus_region_high_hz)
        _try_set(lef, PARAMS['ozone_low_end_focus']['lef_side_action_region_low'], settings.low_end_focus_region_low_hz)
        _try_set(lef, PARAMS['ozone_low_end_focus']['lef_side_action_region_high'], settings.low_end_focus_region_high_hz)
        audio = _apply(lef, audio, sr)

    # ── Stage 6: elysia alpha master — transparent glue compression ───────────
    crest = measure_crest_factor(audio)
    alpha_threshold = float(np.clip(
        scale_alpha_threshold(crest) + settings.alpha_threshold_offset,
        settings.alpha_threshold_min,
        settings.alpha_threshold_max,
    ))
    stage(f"alpha master  (crest={crest:.1f} dB -> threshold={alpha_threshold:.1f} dB)")
    alpha = _load('alpha_master')
    _try_set(alpha, PARAMS['alpha_master']['threshold_1'], alpha_threshold)
    _try_set(alpha, PARAMS['alpha_master']['threshold_2'], alpha_threshold)
    _try_set(alpha, PARAMS['alpha_master']['ratio_1'], settings.alpha_ratio)
    _try_set(alpha, PARAMS['alpha_master']['ratio_2'], settings.alpha_ratio)
    audio = _apply(alpha, audio, sr)

    # ── Stage 7: Softube Tape — saturation/glue ───────────────────────────────
    # Keep it always-on, but trim drive based on remaining dynamics and HF edge.
    crest_post_alpha = measure_crest_factor(audio)
    hf_ratio_post_alpha = measure_hf_ratio(audio, sr, threshold_hz=8000.0)
    tape_drive = float(np.clip(
        scale_tape_drive(crest_post_alpha, hf_ratio_post_alpha) * settings.tape_color_scale
        + settings.tape_color_offset,
        settings.tape_color_min,
        settings.tape_color_max,
    ))
    stage(
        f"Tape  (crest={crest_post_alpha:.1f} dB, "
        f"hf_ratio={hf_ratio_post_alpha:.3f} -> drive={tape_drive:.1f})"
    )
    tape = _load('tape', 'Tape.vstpreset')
    _try_set(tape, PARAMS['tape']['color_amount'], tape_drive)
    _try_set(tape, PARAMS['tape']['noise'], False)
    _try_set(tape, PARAMS['tape']['tape_speed'], settings.tape_speed)
    audio = _apply(tape, audio, sr)

    if settings.inflator_enabled:
        stage(
            "Oxford Inflator  "
            f"(effect={settings.inflator_effect:.1f}, curve={settings.inflator_curve:.1f})"
        )
        inflator = _load('oxford_inflator')
        _try_set(inflator, PARAMS['oxford_inflator']['sonnox_bypass'], False)
        _try_set(inflator, PARAMS['oxford_inflator']['band_split'], False)
        _try_set(inflator, PARAMS['oxford_inflator']['clip_0db'], settings.inflator_clip_0db)
        _try_set(inflator, PARAMS['oxford_inflator']['input_gain'], settings.inflator_input_gain)
        _try_set(inflator, PARAMS['oxford_inflator']['effect'], settings.inflator_effect)
        _try_set(inflator, PARAMS['oxford_inflator']['curve'], settings.inflator_curve)
        _try_set(inflator, PARAMS['oxford_inflator']['output_gain'], settings.inflator_output_gain)
        audio = _apply(inflator, audio, sr)

    hf_guarded, hf_guard = _apply_hf_guard(audio, sr, settings)
    if hf_guard["reduction_db"] > 0.0:
        stage(
            "Streaming HF guard  "
            f"(hf_ratio={hf_guard['hf_ratio']:.3f}, "
            f"air/presence={hf_guard['air_to_presence_db']:+.1f} dB -> "
            f"shelf={-hf_guard['reduction_db']:.1f} dB)"
        )
        audio = hf_guarded
    elif settings.hf_guard_enabled:
        stage(
            "Streaming HF guard  "
            f"(hf_ratio={hf_guard['hf_ratio']:.3f}, "
            f"air/presence={hf_guard['air_to_presence_db']:+.1f} dB -> no cut)"
        )

    if settings.bx_digital_enabled:
        mono_text = (
            f", mono maker={settings.bx_mono_maker_hz:.0f} Hz"
            if settings.bx_mono_maker_enabled
            else ""
        )
        stage(f"bx_digital V3  (width={settings.bx_stereo_width:.1f}%{mono_text})")
        bx = _load('bx_digital_v3')
        _try_set(bx, PARAMS['bx_digital_v3']['bypass'], False)
        _try_set(bx, PARAMS['bx_digital_v3']['auto_listen_active'], False)
        _try_set(bx, PARAMS['bx_digital_v3']['auto_solo'], False)
        _try_set(bx, PARAMS['bx_digital_v3']['solo_1'], False)
        _try_set(bx, PARAMS['bx_digital_v3']['solo_2'], False)
        _try_set(bx, PARAMS['bx_digital_v3']['modus'], 'M/S Master')
        _try_set(bx, PARAMS['bx_digital_v3']['stereo_width'], settings.bx_stereo_width)
        _try_set(bx, PARAMS['bx_digital_v3']['mono_maker_active'], settings.bx_mono_maker_enabled)
        _try_set(bx, PARAMS['bx_digital_v3']['mono_maker_frequency_hz'], f"{settings.bx_mono_maker_hz:.0f}")
        audio = _apply(bx, audio, sr)

    if settings.ozone_imager_enabled:
        correlation = measure_stereo_correlation(audio)
        if correlation < 0.0:
            adaptive_width = 0.0
        elif correlation >= 0.92:
            adaptive_width = 1.0
        elif correlation >= 0.80:
            adaptive_width = 0.8
        elif correlation >= 0.65:
            adaptive_width = 0.55
        else:
            adaptive_width = 0.3
        width_scale = settings.ozone_imager_width_scale * adaptive_width
        band_1_width = settings.ozone_imager_band_1_width_percent * width_scale
        band_2_width = settings.ozone_imager_band_2_width_percent * width_scale
        band_3_width = settings.ozone_imager_band_3_width_percent * width_scale
        band_4_width = settings.ozone_imager_band_4_width_percent * width_scale
        stage(
            "Ozone Imager  "
            f"(corr={correlation:.3f}, widths={band_1_width:+.1f}/"
            f"{band_2_width:+.1f}/{band_3_width:+.1f}/{band_4_width:+.1f}%)"
        )
        imager = _load('ozone_imager')
        _try_set(imager, PARAMS['ozone_imager']['global_bypass'], False)
        _try_set(imager, PARAMS['ozone_imager']['img_bypass'], False)
        _try_set(imager, PARAMS['ozone_imager']['img_link_bands'], False)
        _try_set(imager, PARAMS['ozone_imager']['img_band_1_width_percent'], band_1_width)
        _try_set(imager, PARAMS['ozone_imager']['img_band_2_width_percent'], band_2_width)
        _try_set(imager, PARAMS['ozone_imager']['img_band_3_width_percent'], band_3_width)
        _try_set(imager, PARAMS['ozone_imager']['img_band_4_width_percent'], band_4_width)
        _try_set(
            imager,
            PARAMS['ozone_imager']['img_enable_stereoizer'],
            settings.ozone_imager_stereoizer_enabled,
        )
        _try_set(
            imager,
            PARAMS['ozone_imager']['img_stereoizer_delay_ms'],
            settings.ozone_imager_stereoizer_delay_ms,
        )
        audio = _apply(imager, audio, sr)

    # ── Final limiter/maximizer — LUFS targeting ─────────────────────────────
    # Analyze AFTER tone/density stages: trim to land near target_lufs.
    lufs_pre_limit = measure_integrated_lufs(audio, sr)
    requested_trim_db = float(np.clip(target_lufs - lufs_pre_limit, -6.0, 6.0))
    trim_db = requested_trim_db
    limiter_name = 'Weiss MM-1' if settings.final_limiter == 'weiss_mm1' else 'Ozone 9'
    streaming_ceiling = _streaming_ceiling_for_target(target_lufs, settings)
    limiter_ceiling = (
        min(settings.weiss_out_trim_dbfs, streaming_ceiling)
        if settings.final_limiter == 'weiss_mm1'
        else min(settings.ozone_ceiling, streaming_ceiling)
    )
    trim_guard_reduction = 0.0
    if settings.loud_section_guard_enabled:
        pre_limit_loud_section = measure_loudest_window(audio, sr, settings.loud_section_seconds)
        max_trim_for_loud_section = (
            limiter_ceiling
            - loud_section_crest_floor
            - pre_limit_loud_section["rms_dbfs"]
        )
        if trim_db > max_trim_for_loud_section:
            trim_db = float(np.clip(max_trim_for_loud_section, -6.0, trim_db))
            trim_guard_reduction = requested_trim_db - trim_db
            print(
                "  Loud-section guard capped final trim: "
                f"{requested_trim_db:+.1f} -> {trim_db:+.1f} dB "
                f"(pre-limit loud RMS {pre_limit_loud_section['rms_dbfs']:.1f} dBFS, "
                f"crest floor {loud_section_crest_floor:.1f} dB)"
            )
    if abs(trim_db) > 0.3:
        audio = _gain(audio, trim_db)
        stage(f"{limiter_name} final  (pre-limit LUFS={lufs_pre_limit:.1f}, trim={trim_db:+.1f} dB)")
    else:
        stage(f"{limiter_name} final  (pre-limit LUFS={lufs_pre_limit:.1f}, no trim needed)")
    if settings.final_limiter == 'weiss_mm1':
        weiss = _load('weiss_mm1')
        weiss_amount = settings.weiss_amount
        if settings.loud_section_guard_enabled and trim_guard_reduction > 0.1:
            weiss_amount = max(0.0, settings.weiss_amount - trim_guard_reduction * 8.0)
        _try_set(weiss, PARAMS['weiss_mm1']['bypass'], 'Process')
        _try_set(weiss, PARAMS['weiss_mm1']['style'], settings.weiss_style)
        _try_set(weiss, PARAMS['weiss_mm1']['amount'], weiss_amount)
        _try_set(weiss, PARAMS['weiss_mm1']['limiter_gain_db'], settings.weiss_limiter_gain_db)
        _try_set(weiss, PARAMS['weiss_mm1']['out_trim_dbfs'], limiter_ceiling)
        _try_set(weiss, PARAMS['weiss_mm1']['parallel_mix'], settings.weiss_parallel_mix)
        audio = _apply(weiss, audio, sr)
    else:
        ozone = _load('ozone9', 'Ozone 9.vstpreset')
        if settings.ozone_bypass_modules:
            for module_param in (
                'dyn_bypass',
                'dyneq_bypass',
                'exc_bypass',
                'vcomp_bypass',
                'veq_bypass',
                'vlm_bypass',
                'vtape_bypass',
                'spshpr_bypass',
                'mrb_bypass',
                'match_eq_bypass',
                'lef_bypass',
            ):
                _try_set(ozone, PARAMS['ozone9'][module_param], True)
        _try_set(ozone, PARAMS['ozone9']['max_link'], False)
        _try_set(ozone, PARAMS['ozone9']['max_ceiling'], limiter_ceiling)
        _try_set(ozone, PARAMS['ozone9']['max_true_peak'], True)
        ozone_threshold = settings.ozone_threshold
        if settings.loud_section_guard_enabled and trim_guard_reduction > 0.1:
            ozone_threshold = max(ozone_threshold, -0.8)
        _try_set(ozone, PARAMS['ozone9']['max_threshold'], ozone_threshold)
        audio = _apply(ozone, audio, sr)

    final_lufs = measure_integrated_lufs(audio, sr)
    print(f"  Output LUFS: {final_lufs:.1f} (target: {target_lufs:.1f})")

    return audio


def discover_params(key: str) -> dict[str, object]:
    """Load a plugin and return all its parameter names and current values."""
    plugin = _load(key)
    metadata = {
        'name': getattr(plugin, 'name', ''),
        'version': getattr(plugin, 'version', ''),
        'manufacturer_name': getattr(plugin, 'manufacturer_name', ''),
        'reported_latency_samples': getattr(plugin, 'reported_latency_samples', ''),
    }
    parameter_values = {
        name: getattr(plugin, name)
        for name in getattr(plugin, 'parameters', {}).keys()
    }
    return {**metadata, **parameter_values}
