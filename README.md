# Source-Aware AI Mastering for Suno-Generated Pop Music

You can listen to the test demo results here: https://suno.com/playlist/3638a39f-56dc-489c-85e8-87c38df4666c
## Abstract

This project implements a standalone, source-aware mastering system for Suno-generated songs. The core motivation is that AI-generated pop masters often arrive in a partially mastered state, but with recurring release-readiness problems: brittle digital high-end, limited loudness control, and inconsistent low-frequency punch. The system renders multiple bounded mastering candidates, evaluates each candidate against the original source, rejects candidates that become darker/narrower/overcompressed, and selects the best output using deterministic audio metrics plus local CLAP/MERT model scoring.

The pipeline is intentionally conservative. It does not assume that more processing is better. If the original source already outperforms all mastered candidates, the original can remain the selected result.

## 1. Problem Statement

Suno outputs are often musically useful but technically inconsistent for release workflows. The observed flaws this project targets are:

1. Brittle, digital distortion in the high end. Cymbals, vocal air, synth fizz, and upper harmonics can accumulate into a glassy or aliased shimmer that becomes worse after conventional limiting.
2. Limited mastering control. Suno-style exports are commonly treated as fixed-streaming masters, often around a conservative loudness target such as `-14 LUFS`, with no reliable per-song control over final loudness, headroom, or alternate masters.
3. Slightly weak sub and low-bass punch for modern pop. Kick/sub energy can be present but not shaped with the density, impact, and translation expected from commercial pop/EDM references.

The practical challenge is that these issues are not uniform. Some songs need high-frequency cleanup; others already sound open and should not be darkened. Some need more low-end weight; others become muddy if pushed. A fixed preset is therefore insufficient.

## 2. Research Objective

The objective is to build a mastering program that:

1. Detects per-song tonal, loudness, dynamic, and stereo characteristics.
2. Applies bounded plugin processing instead of fixed destructive presets.
3. Generates multiple mastering candidates for different tradeoffs.
4. Compares candidate masters against the original source and optional reference masters.
5. Preserves width, presence, and emotional immediacy when the original is already strong.
6. Supports custom loudness targets while defaulting to streaming-safe `-14 LUFS` and `-12 LUFS` outputs.

## 3. System Overview

The app is a Python mastering pipeline designed to run from WSL while hosting Windows VST3 plugins through Windows Python.

```text
apps/mastering/
  master.py                    # stable CLI wrapper
  presets/                     # VST preset files
  scripts/windows/             # WSL -> Windows helper scripts
  src/mastering_app/
    cli.py                     # argparse commands
    paths.py                   # app-root and preset paths
    audio/                     # deterministic signal analysis and DSP helpers
    models/                    # local CLAP/MERT model scoring
    pipeline/                  # plugin chain, rendering, AI candidate loop
```

Machine-specific paths and secrets belong in `.env.local`. Commit `.env.example`, not `.env.local`.

### Quick Run

Use the root launcher for day-to-day tests:

```bash
./master.sh /mnt/c/Production/music/Submission/abe002_mulholland.wav
```

Defaults:

1. `./master.sh` masters the newest source WAV in `/mnt/c/Production/music/Submission`.
2. Output goes to `<input folder>/masters/<basename>_<timestamp>` to avoid overwriting files that a DAW or Windows may be holding open.
3. The default catalog is now six bolder creative candidates instead of the older conservative 16-candidate set.
4. `MASTERING_LOCAL_MODELS=0` disables optional CLAP/MERT scoring when you want faster offline tests.

Example fast run:

```bash
MASTERING_LOCAL_MODELS=0 MASTERING_JOBS=2 ./master.sh /mnt/c/Production/music/Submission/abe002_mulholland.wav
```

Optional Apollo restoration branch:

```bash
./master.sh --apollo /mnt/c/Production/music/Submission/abe002_mulholland.wav
```

Set the Apollo checkout once in `.env.local`:

```bash
MASTERING_APOLLO_REPO=/mnt/c/path/to/Apollo
```

Use `--fast` if you want to skip optional CLAP/MERT scoring while testing:

```bash
./master.sh --apollo --fast /mnt/c/Production/music/Submission/abe002_mulholland.wav
```

Apollo is not bundled and is not enabled by default. When enabled, the app renders the normal mastering candidates plus `apollo_restored` and Apollo-fed variants of the main repair/color candidates so restoration is auditioned against the original-source chain instead of silently replacing it.

Set `MASTERING_LEGACY_CANDIDATES=1` if you want to run the older, larger conservative candidate catalog.

## 4. Methods

### 4.1 Deterministic Signal Analysis

The system computes low-level audio descriptors before and after processing:

1. Integrated LUFS.
2. Sample peak and approximate true peak.
3. Crest factor.
4. High-frequency energy ratio.
5. Spectral flatness.
6. Stereo correlation.
7. Side-to-mid energy ratio.
8. Band energy in sub, low-mid, presence, and air regions.
9. Punch-to-mud balance, vocal presence, harsh-to-vocal, and fizz-to-vocal ratios.
10. Band-limited stereo width/correlation for phasey high-frequency artifact detection.
11. Peak-loudness ratio and loudest-section crest for dynamic preservation.
12. An artifact index that combines brittle high-frequency imbalance, side-high excess, high-band crest, and negative high-band correlation.

These metrics are used as release guards. A candidate is penalized or rejected if it loses too much presence, narrows the stereo image, over-raises sub energy, clips true peak, or compresses the source excessively.

### 4.2 Creative Remaster Candidates

The default `ai-render` catalog intentionally uses fewer, more different candidates:

1. `transparent_repair`: conservative deglaze and source-preserving cleanup.
2. `creative_analog`: audible tape, Inflator, M/S warmth/presence, and parallel soft clipping.
3. `wide_open_color`: vocal-forward midrange with wider presence imaging and side-high smoothing.
4. `ai_deglaze`: stronger side-high and phasey-fizz control for brittle AI artifacts.
5. `punch_density`: stronger low-end focus, density, and a Weiss finish.
6. `dynamic_open`: lower-density, more dynamic, open candidate with lighter limiting.

Creative candidates disable source-match rollback and use relaxed release guards so the report can surface audible color options instead of forcing every render back toward the original.

### 4.2 Corrective EQ

The system uses Python DSP for dynamic corrective EQ decisions instead of blindly loading a static Pro-Q preset. The corrective EQ stage detects:

1. Excessive sub buildup requiring high-pass cleanup.
2. Low-mid buildup around `180-420 Hz`.
3. Excessive air-band energy.
4. Narrow resonant peaks requiring high-Q cuts.

The cuts are intentionally capped. The goal is corrective mastering EQ, not mix rescue.

### 4.3 Plugin Chain

The base plugin chain is:

1. Dynamic corrective EQ plus FabFilter Pro-Q 3 as a neutral stage.
2. `Gullfoss Master` as bounded spectral recovery/taming on every processed candidate.
3. `VEQ-MG4+` for low-mid warmth and punch.
4. `soothe2` pass 1 for broad resonance suppression.
5. `soothe2` pass 2 for fine resonance cleanup.
6. `Multipass` for high-frequency shimmer control through a mapped macro.
7. `elysia alpha master` for very subtle glue compression.
8. `Softube Tape` for restrained harmonic density.
9. A post-density streaming HF guard for broad 8-16 kHz de-harshing before widening/limiting.
10. `Ozone 9 Imager` for conservative width preservation before final limiting.
11. A loudest-section guard that caps final drive when the chorus/drop would lose too much crest.
12. `Ozone 9` primarily as final limiter/ceiling control.

Candidate-only optional modules are now available:

1. `Dangerous BAX EQ Master` for broad low/high shelf polish.
2. `bx_digital V3` for width preservation and optional low-end mono management.
3. `Ozone 9 Low End Focus` for controlled pop low-end punch.
4. `Oxford Inflator Native` for perceived loudness and density before limiting.
5. `Weiss MM-1 Mastering Maximizer` as an alternate final maximizer.

Processing values are bounded and source-dependent. The chain is designed to prevent the common failure mode where the mastered output becomes louder but darker, narrower, and less emotionally immediate. Optional modules are not all enabled together; they are tested as candidates and rejected by scoring/guards when they damage the source.

### 4.4 Candidate Search

`ai-render` creates multiple candidates:

1. `original`: the unprocessed source reference.
2. `classic_chain`: streaming-safe deterministic non-AI mastering baseline.
3. `streaming_loud_open`: normalized-playback loudness with true-peak-safe de-harshing.
4. `streaming_polish_plus`: more audible streaming polish with punch, width, and harmonic density.
5. `preserve_open`: minimal cleanup, width/presence preservation.
6. `bright_open_edm`: brighter pop/EDM polish without unchecked shimmer.
7. `punch_warm`: low-mid warmth and punch emphasis.
8. `punch_warm_dynamic`: the same warmth direction with less late-section limiting.
9. `controlled_shimmer`: stronger AI-shimmer cleanup.
10. `deharsh_gullfoss`: targeted high-end de-harshing for brittle sources.
11. `analog_warm_punch`: tape-led warmth and low-mid harmonic body.
12. `musical_restore`: tone-first analog color, punch, vocal presence, width, and restrained de-harshing.
13. `ai_artifact_repair`: stronger repair pass for brittle/time-stretched side highs and phasey fizz.
14. `dynamic_punch_image`: low-end punch, wider image, and stricter chorus/drop crest preservation.
15. `inflator_weiss_density`: perceived loudness/density with Weiss MM-1 final limiting.
16. Optional AI-refined candidates when OpenAI audio judging is enabled.

Before rendering, the free-form style/comment is parsed by a deterministic intent mapper. This is not an LLM step. Matched words such as `less squashed`, `harsh`, `wide`, `warm`, `muffled`, `preserve original`, or `vocal forward` produce bounded plugin-setting overrides and score biases. The applied mapping is written into `ai-mastering-report.json` and shown in `ai-mastering-report.html` under `Comment Intent`.

Examples:

1. `less squashed chorus, keep it punchy and warm` tightens the loud-section crest guard, lowers density stages, and biases `punch_warm_dynamic`.
2. `harsh brittle high end, cleaner but still open` increases Gullfoss tame and Multipass HF control while preserving presence.
3. `wide bright open pop EDM like Chainsmokers` biases brighter/open candidates and increases conservative Ozone Imager width.
4. `original sounds better, subtle clean preserve` lowers processing depth and biases `original`/`preserve_open`.

The selected output is written as:

```text
<basename>_ai_best.wav
ai-mastering-report.json
ai-mastering-report.html
```

## 5. Local Models

Local model scoring is enabled by default for `ai-render`.

### 5.1 CLAP Style Matching

Model: `laion/larger_clap_music`

CLAP is used for audio-text similarity. The style prompt, for example `"bright open pop EDM mastering in the style of Chainsmokers"`, is compared against the original and candidate masters. Candidates receive a bounded score adjustment when they better match the target style without violating deterministic release guards.

Purpose:

1. Estimate whether a candidate moved toward the requested sonic direction.
2. Reward bright/open/pop-EDM character when that is the stated target.
3. Avoid relying only on LUFS and spectral metrics.

### 5.2 MERT Music Embeddings

Default model: `m-a-p/MERT-v1-95M`

MERT is used for music-embedding similarity. It serves two purposes:

1. Content preservation: candidate masters should remain close to the original song identity.
2. Reference matching: if `MASTERING_REFERENCE_DIR` is provided, candidates are scored against a folder of reference masters.

This makes the evaluation more musically aware than simple spectral matching.

### 5.3 Reference Master Folder

If a reference folder is configured, the system embeds those files and rewards candidates that move closer to the reference distribution. This is useful for style targets such as modern pop, EDM, or vocal-forward electronic music.

Example:

```bash
MASTERING_REFERENCE_DIR=/mnt/c/path/to/reference-masters
```

## 6. Scoring and Selection

The final score combines:

1. Deterministic metric score.
2. Deterministic comment-intent score bias.
3. CLAP style delta.
4. MERT content-preservation score.
5. MERT reference-similarity delta, if references are available.
6. Penalties for presence loss, stereo narrowing, excessive sub lift, overcompression, target miss, and peak issues.

Release guards override model preference. A model cannot select a candidate that fails the safety checks unless all candidates fail.

Final limiting is also loudest-section aware. The system finds the loudest program window, records its time range, RMS, peak, and crest, and uses that section to cap final trim/limiter drive. This prevents the full-track LUFS target from pushing the chorus or drop into audible collapse.

## 7. Findings

Current development findings:

1. Static mastering presets are unreliable for Suno outputs because the source material is already partially processed and varies widely by song.
2. The most common bad master is not simply “too quiet”; it is darker, narrower, and more compressed than the original.
3. Soothe-style resonance suppression must be subtle. Too much cleanup removes presence and emotional immediacy.
4. Ozone-style all-in-one processing can narrow and darken the result if non-limiter modules are left active.
5. Source-matching after plugin processing is useful for restoring presence and stereo width.
6. The original should always be included as a candidate because some Suno exports are already better than a conservative processing chain.
7. Local model scoring is useful as a secondary judge, but deterministic audio guards remain necessary.
8. Mastering-specific plugins such as Gullfoss, Inflator, Weiss, BAX, bx_digital, and Low End Focus are best modeled as bounded candidate modules rather than a single always-on chain.

## 8. Usage

Install base dependencies into Windows Python:

```bash
./scripts/windows/install.sh
```

Install optional local model dependencies:

```bash
./scripts/windows/install-local-models.sh
```

Download/check local models:

```bash
./scripts/windows/models-check.sh --download
```

Render with source-aware AI/local-model selection:

```bash
./scripts/windows/ai-render.sh /mnt/c/path/to/song.wav /mnt/c/path/to/output ai-test -14 "bright open pop EDM mastering in the style of Chainsmokers"
```

Render with an external Apollo restoration candidate:

```bash
./master.sh --apollo /mnt/c/path/to/song.wav
```

Open the generated `ai-mastering-report.html` in the output directory to inspect candidate audio, chain stages, active optional modules, score notes, and metric deltas against the source.

Render deterministic LUFS targets:

```bash
./scripts/windows/render.sh /mnt/c/path/to/song.wav /mnt/c/path/to/output master-test -14,-12
```

Regenerate the visual report from an existing JSON report:

```bash
python master.py html-report /mnt/c/path/to/output/ai-mastering-report.json
```

Inspect plugins:

```bash
./scripts/windows/check.sh
./scripts/windows/discover.sh soothe2
```

Use `./scripts/windows/<command>.sh` directly — the root-level `*-windows.sh` wrappers have been removed.

## 9. Configuration

Safe template:

```bash
cp .env.example .env.local
```

Important settings:

```bash
WINDOWS_PYTHON=python.exe
MASTERING_LOCAL_MODELS=1
MASTERING_LOCAL_MODELS_OFFLINE=0
MASTERING_MODEL_DEVICE=auto
MASTERING_CLAP=1
MASTERING_CLAP_MODEL=laion/larger_clap_music
MASTERING_MERT=1
MASTERING_MERT_MODEL=m-a-p/MERT-v1-95M
MASTERING_REFERENCE_DIR=
```

To disable local model scoring:

```bash
MASTERING_LOCAL_MODELS=0
```

or pass:

```bash
python master.py ai-render ... --no-local-models
```

## 10. Outputs

The report includes:

1. Source metrics.
2. Candidate metrics.
3. Plugin-chain settings.
4. Source-match moves.
5. Deterministic score notes.
6. Local model scoring report.
7. Per-candidate `local_model_scores`.
8. Selected best candidate and output path.
9. A self-contained visual HTML report with local audio players and chain cards.

## 11. Limitations

1. The system is not a replacement for human mastering judgment.
2. CLAP and MERT are scoring aids, not authoritative audio engineers.
3. Reference-folder quality strongly affects reference-similarity scoring.
4. VST parameter names can vary by plugin version and installation.
5. Windows VST3 rendering requires Windows Python and installed plugin licenses.
6. Local model inference can be slow on CPU.

## 12. Future Work

1. Add a curated pop/EDM reference embedding cache.
2. Add per-section analysis for verse/drop/chorus differences.
3. Add more explicit transient punch metrics.
4. Add a low-end translation check against mono and small-speaker simulations.
5. Add automatic A/B clip export for human review.
6. Add learned preference calibration from user choices.
7. Expand candidate modules using the installed VST3 review in `docs/vst3-mastering-tool-review.md`.

## 13. Direct Python Entry Points

```bash
python master.py --help
PYTHONPATH=src python -m mastering_app --help
```
