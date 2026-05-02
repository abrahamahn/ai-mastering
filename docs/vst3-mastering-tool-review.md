# VST3 Mastering Tool Review

## Summary

The current mastering chain uses only a narrow subset of the installed VST3 library:

```text
Pro-Q 3 -> VEQ-MG4+ -> soothe2 x2 -> Multipass -> elysia alpha master -> Tape -> Ozone 9
```

That chain is reasonable, but the installed library includes several mastering-specific tools that can address the exact Suno failure modes more directly:

1. Brittle digital high end: `Gullfoss Master`, `spiff`, `Ozone 9 Spectral Shaper`, `TDR Nova`, `soothe2`, `smartEQ2`.
2. Weak pop low-end punch: `Ozone 9 Low End Focus`, `bx_digital V3`, `Dangerous BAX EQ Master`, `Oxford Inflator Native`, `Newfangled Saturate`, `Spectre`.
3. Loudness and density without flat limiting: `Oxford Inflator Native`, `Weiss MM-1 Mastering Maximizer`, `Ozone 9 Maximizer`, `Newfangled Saturate`.
4. Stereo and translation control: `bx_digital V3`, `MSED`, `Ozone 9 Imager`, `Correlometer`, `MetricAB`, `Insight 2`, `Youlean Loudness Meter 2`, `SPAN`, `TDR Prism`.

The best next step is not to make a single longer fixed chain. The better architecture is to add these as optional, bounded candidate modules and let the current scoring system choose when they help.

## Highest-Value Additions

Implementation status:

The first-pass chain expansion adds `Gullfoss Master`, `Oxford Inflator Native`, `Weiss MM-1 Mastering Maximizer`, `bx_digital V3`, `Dangerous BAX EQ Master`, and `Ozone 9 Low End Focus` as optional bounded candidate modules. They are intentionally not all enabled in the default path.

### 1. Gullfoss Master

Role: intelligent spectral balancing and high-end harshness cleanup.

Why it matters:

Suno material often has unstable upper-mid and high-frequency density. `Gullfoss Master` is a better fit than broad EQ when the problem is distributed harshness rather than one or two resonant peaks.

Recommended use:

1. Add as a candidate-only stage after corrective EQ and before analog color.
2. Use very low amounts.
3. Reject if presence or stereo width drops.

Risk:

Too much Gullfoss can make a song feel “auto-corrected,” flatter, or less emotionally forward.

Priority: very high.

### 2. Oxford Inflator Native

Role: perceived loudness, density, and forwardness without relying only on limiter gain.

Why it matters:

For pop/EDM, Inflator can increase perceived loudness and harmonic density while preserving punch better than pushing Ozone harder.

Recommended use:

1. Add as a pre-limiter density candidate.
2. Use subtle effect/curve settings.
3. Compare against `Tape` and `Newfangled Saturate`; do not stack all of them by default.

Risk:

Can add edge or congestion if used after already-bright material.

Priority: very high.

### 3. Weiss MM-1 Mastering Maximizer

Role: alternate final loudness stage.

Why it matters:

`Weiss MM-1` can be tested as an alternate final maximizer to Ozone. It may give a different loudness/clarity tradeoff.

Recommended use:

1. Use as candidate final limiter/maximizer.
2. Compare against Ozone 9 Maximizer.
3. Let true peak, crest, and local model scores decide.

Risk:

Can over-densify if target LUFS is too aggressive.

Priority: high.

### 4. bx_digital V3

Role: M/S EQ, low-end mono control, mastering tone shaping.

Why it matters:

The current chain has source-match width restoration, but it does not have a dedicated mastering-grade M/S EQ stage. `bx_digital V3` is a strong candidate for low-end mono management and subtle side/top shaping.

Recommended use:

1. Use for low-end mono tightening if sub-side energy is high.
2. Use subtle side high-shelf only if candidate loses openness.
3. Avoid broad mid cuts unless analysis confirms buildup.

Risk:

Poor M/S moves can narrow the master or weaken the drop.

Priority: high.

### 5. Dangerous BAX EQ Master

Role: broad low/high shelves and mastering polish.

Why it matters:

BAX-style EQ is a good fit for subtle low-end weight and top-end openness, especially when Pro-Q-style surgical EQ is too clinical.

Recommended use:

1. Add low shelf candidate for pop low-end support.
2. Add high shelf candidate only when harshness metrics are safe.
3. Use before final limiter.

Risk:

Can worsen sub excess or make brittle highs worse if used without guards.

Priority: high.

## Strong Secondary Candidates

### Ozone 9 Module Plugins

Installed module plugins include:

```text
Ozone 9 Dynamic EQ
Ozone 9 Dynamics
Ozone 9 Equalizer
Ozone 9 Exciter
Ozone 9 Imager
Ozone 9 Low End Focus
Ozone 9 Maximizer
Ozone 9 Spectral Shaper
Ozone 9 Vintage Compressor
Ozone 9 Vintage EQ
Ozone 9 Vintage Limiter
Ozone 9 Vintage Tape
```

Recommended use:

1. Prefer individual Ozone module plugins over full `Ozone 9.vst3`.
2. Use `Low End Focus` as a candidate for weak sub/low-bass punch.
3. Use `Spectral Shaper` as a candidate for digital shimmer.
4. Use `Imager` only with strict correlation and mono guards.
5. Keep `Maximizer` as one final-limiter option.

Risk:

Full Ozone presets can easily narrow or darken the source. Individual modules are easier to constrain.

Priority: high.

### TDR Kotelnikov

Role: transparent mastering compression.

Why it matters:

Good alternative to `elysia alpha master` for transparent, low-artifact glue.

Recommended use:

1. Add as an alternate glue compressor candidate.
2. Use low ratio and minimal gain reduction.
3. Score against alpha master.

Risk:

Compression is not always needed for Suno masters.

Priority: medium-high.

### TDR Nova

Role: dynamic EQ / de-harsh / low-mid control.

Why it matters:

Useful when Pro-Q automation is limited or when dynamic attenuation is needed for upper mids and harshness.

Recommended use:

1. Candidate de-harsh band in upper mids.
2. Candidate low-mid dynamic control.
3. Keep moves subtle.

Risk:

Can sound dull if it reduces presence bands too much.

Priority: medium-high.

### spiff

Role: transient/resonance shaping.

Why it matters:

Can reduce clicky digital spikes or emphasize punch depending on settings.

Recommended use:

1. Candidate for brittle transient cleanup.
2. Candidate for punch enhancement if low-end transients are weak.

Risk:

Can produce obvious artifacts if pushed.

Priority: medium.

### Newfangled Saturate

Role: clipping/saturation for density and peak management.

Why it matters:

Can add loudness and density before final limiting.

Recommended use:

1. Candidate pre-limiter peak control.
2. Compare against Oxford Inflator and Tape.

Risk:

Can harden the high end.

Priority: medium.

### Spectre

Role: EQ-shaped saturation.

Why it matters:

Potentially useful for adding low-mid punch or air harmonics without broad EQ.

Recommended use:

1. Candidate low-mid harmonic enhancement.
2. Candidate controlled air enhancement only if source is not brittle.

Risk:

Can worsen harshness if used in upper bands.

Priority: medium.

## Monitoring and Evaluation Tools

These should not be part of the processing chain, but they are valuable for validation:

1. `ADPTR MetricAB`: reference A/B workflow.
2. `Youlean Loudness Meter 2`: LUFS and true peak validation.
3. `Insight 2`: metering and loudness.
4. `SPAN`: spectrum sanity check.
5. `TDR Prism`: spectral comparison.
6. `Correlometer`: stereo correlation.
7. `SPL HawkEye`: metering.
8. `WaveObserver`: oscilloscope-style inspection.
9. `Tonal Balance Control 2`: tonal reference guidance.

Recommended use:

Use these as offline/manual validation tools. For automation, keep Python metrics and local model scoring as the machine-readable evaluators.

## Tools to Avoid in Full-Program Mastering by Default

These are useful creatively, but risky in an automated mastering chain:

1. Heavy distortion tools: `Decapitator`, `DevilLocDeluxe`, `SausageFattener`, `OTT`, `Beat Slammer`, `SP950`, `SketchCassette II`, `SuperVHS`.
2. Modulation/time effects: chorus, flanger, phaser, delays, reverbs.
3. Vocal/instrument-specific tools: `Nectar`, `VocalSynth`, `Melodyne`, `RX Breath Control`.
4. Creative stereo wideners: `MicroShift`, `Wider`, `StereoSavage`, `AIRStereoWidth`.

These can be great in production or stem processing, but they are too risky for automated full-mix mastering unless used in a specialized candidate with strict rejection guards.

## Recommended Candidate Architecture

The current chain should evolve from one fixed chain into a modular candidate system.

### Candidate Family A: Preserve/Open

Purpose: avoid damaging already-good Suno masters.

Potential modules:

1. Corrective EQ.
2. Very light `Gullfoss Master`.
3. Very light `elysia alpha master` or no compressor.
4. `Ozone 9 Maximizer` or `Weiss MM-1`.

### Candidate Family B: Bright Pop/EDM

Purpose: open, wide, forward commercial pop.

Potential modules:

1. Corrective EQ.
2. `Dangerous BAX EQ Master`.
3. `Oxford Inflator Native`.
4. Light `Tape` or no tape.
5. `Ozone 9 Maximizer`.

### Candidate Family C: Punch/Warm

Purpose: more low-mid and sub impact.

Potential modules:

1. Corrective EQ.
2. `Ozone 9 Low End Focus`.
3. `VEQ-MG4+`.
4. `Spectre` or `Oxford Inflator`.
5. `Weiss MM-1`.

### Candidate Family D: Shimmer Control

Purpose: reduce brittle AI high-end.

Potential modules:

1. Corrective EQ.
2. `soothe2`.
3. `Gullfoss Master`.
4. `spiff` or `Ozone 9 Spectral Shaper`.
5. Conservative limiter.

## Recommended Implementation Order

1. Add an inventory/discovery layer for more plugins.
2. Add `Gullfoss Master` as a bounded optional stage.
3. Add `Oxford Inflator Native` as a density candidate.
4. Add `Weiss MM-1` as an alternate final limiter.
5. Add `Dangerous BAX EQ Master` and/or `bx_digital V3` for mastering tone shaping.
6. Add `Ozone 9 Low End Focus` for weak low-end candidates.
7. Add `Ozone 9 Spectral Shaper` or `spiff` for brittle high-end candidates.
8. Expand reports to include which modules were active for each candidate.

## Practical Recommendation

The next two plugins to integrate should be:

1. `Gullfoss Master`, because it directly targets the brittle/high-end spectral imbalance issue.
2. `Oxford Inflator Native`, because it targets perceived loudness and pop density without simply pushing a limiter harder.

After that, add `Weiss MM-1` as an alternate final loudness stage and `Ozone 9 Low End Focus` for low-end punch candidates.
