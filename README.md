# Source-Aware Suno Mastering

Standalone mastering pipeline for Suno-generated music. The app renders one original reference plus five bounded mastered candidates, scores them against the source, and writes the selected master plus JSON/HTML reports.

The current goal is intentionally narrow:

1. Tame brittle Suno high-end distortion.
2. Improve stereo imaging without phasey side-high artifacts.
3. Add analog-style low-mid warmth.
4. Preserve or improve dynamic punch.

Local CLAP/MERT scoring can be used as a secondary judge. Deterministic audio metrics and release guards remain the primary selector.

## Quick Run

```bash
./master.sh /mnt/c/Production/music/Submission/song.wav
```

Defaults:

1. `./master.sh` masters the newest source WAV in `/mnt/c/Production/music/Submission`.
2. Output goes to `<input folder>/masters/<basename>_<timestamp>`.
3. `--jobs N` renders candidates in parallel; the launcher defaults to `2`.
4. `--fast` disables optional CLAP/MERT scoring for faster offline tests.
5. The default target is `-14 LUFS`, or `MASTERING_PRIMARY_LUFS` when set.

Fast test mode:

```bash
MASTERING_TEST=1
MASTERING_TEST_MODE=loudest
MASTERING_TEST_SECONDS=30
./master.sh --fast /mnt/c/Production/music/Submission/song.wav
```

Use `--no-test` for a full-song render when test mode is enabled.

## Candidate Catalog

`ai-render` now renders five purposeful candidates:

1. `balanced_pillars`: balanced de-harshing, width, warmth, and punch.
2. `warm_analog`: stronger low-mid body, tape color, and controlled highs.
3. `bright_open`: more presence and stereo image with high-end guardrails.
4. `deharsh_repair`: stronger Suno shimmer/fizz control.
5. `punch_forward`: stronger kick/sub impact and perceived energy while preserving crest.

The unprocessed `original` is always included as a reference and fallback.

## Chain Shape

The processing chain is kept focused:

1. Corrective EQ plus candidate-specific Pro-Q shape moves.
2. Gullfoss Master for bounded recovery/taming.
3. VEQ-MG4+ and BAX for analog low-mid color where enabled.
4. bx_digital and Ozone Imager for conservative stereo imaging.
5. soothe2 and Multipass for high-end resonance and shimmer control.
6. Ozone Low End Focus and Oxford Inflator only on candidates that need punch/density.
7. elysia alpha master and Softube Tape for subtle glue and harmonic color.
8. Streaming HF guard after color stages.
9. Loudest-section guard and Ozone/Weiss final limiting.

Candidate differences are mainly driven by bounded Pro-Q shape values:

```text
proq_punch_db
proq_warmth_db
proq_presence_db
proq_air_db
```

This keeps the catalog audible and understandable instead of creating many near-identical outputs.

## Scoring

Selection combines:

1. Deterministic metrics against the source.
2. A pillar score for de-harshing, width, warmth, and punch.
3. Deterministic comment-intent bias.
4. Optional CLAP style delta.
5. Optional MERT content preservation and reference similarity.

Release guards reject candidates that lose too much presence, narrow the image, raise sub/HF artifacts too much, damage high-band correlation, clip peak headroom, or collapse loud-section crest. If all processed candidates fail, the original can remain the selected result.

## Local Models

Install optional model dependencies:

```bash
./scripts/windows/install-local-models.sh
```

Check or download models:

```bash
./scripts/windows/models-check.sh --download
```

Useful settings:

```bash
MASTERING_LOCAL_MODELS=1
MASTERING_LOCAL_MODELS_OFFLINE=0
MASTERING_MODEL_DEVICE=auto
MASTERING_CLAP=1
MASTERING_CLAP_MODEL=laion/larger_clap_music
MASTERING_MERT=1
MASTERING_MERT_MODEL=m-a-p/MERT-v1-95M
MASTERING_REFERENCE_DIR=/mnt/c/path/to/reference-masters
```

Disable local model scoring:

```bash
MASTERING_LOCAL_MODELS=0
python master.py ai-render ... --no-local-models
```

## Configuration

Copy the local template:

```bash
cp .env.example .env.local
```

Base settings:

```bash
WINDOWS_PYTHON=python.exe
MASTERING_JOBS=2
MASTERING_LOCAL_MODELS=1
MASTERING_REFERENCE_DIR=
```

Machine-specific paths and secrets belong in `.env.local`.

## Outputs

Each candidate run writes:

```text
<basename>_ai_original.wav
<basename>_ai_<candidate>.wav
<basename>_ai_best.wav
ai-mastering-report.json
ai-mastering-report.html
```

Open the HTML report to inspect candidate audio, chain stages, active modules, score notes, and metric deltas.

## Direct Commands

```bash
./scripts/windows/ai-render.sh /mnt/c/path/to/song.wav /mnt/c/path/to/output song -14
./scripts/windows/check.sh
./scripts/windows/discover.sh soothe2
python master.py --help
PYTHONPATH=src python -m mastering_app --help
```

## Limits

This is not a replacement for human mastering judgment. The model scores are aids, not authorities, and VST parameter names can vary by plugin version. Windows VST3 rendering requires Windows Python and installed plugin licenses.
