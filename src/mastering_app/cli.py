#!/usr/bin/env python3
"""CLI entry point for the standalone mastering app."""
import argparse
import json
import sys
from pathlib import Path


def cmd_check() -> bool:
    """Verify all VST3 plugins and presets load correctly."""
    from .pipeline.chain import PLUGIN_PATHS, PRESETS, _load
    from .pipeline.settings import candidate_settings

    all_ok = True
    print("Checking VST3 plugins:")
    for key, path in PLUGIN_PATHS.items():
        if not path.exists():
            print(f"  [FAIL] {key}: NOT FOUND at {path}")
            all_ok = False
        else:
            try:
                _load(key)
                print(f"  [OK] {key}")
            except Exception as e:
                print(f"  [FAIL] {key}: {e}")
                all_ok = False

    print("\nChecking presets:")
    for p in sorted(PRESETS.iterdir()):
        if p.suffix == '.vstpreset':
            print(f"  [OK] {p.name}")

    print("\nChecking AI candidate settings:")
    try:
        for settings in candidate_settings("bright open pop EDM"):
            print(f"  [OK] {settings.name}")
    except Exception as e:
        print(f"  [FAIL] candidate settings: {e}")
        all_ok = False

    return all_ok


def cmd_discover(key: str) -> None:
    """Print all parameter names and values for a plugin (for calibration)."""
    from .pipeline.chain import discover_params
    params = discover_params(key)
    print(f"\nParameters for '{key}':")
    for name, value in sorted(params.items()):
        print(f"  {name!r}: {value!r}")


def cmd_master(input_path: str, output_path: str, target_lufs: float) -> None:
    from .pipeline.chain import process
    import soundfile as sf

    in_path = Path(input_path)
    out_path = Path(output_path)

    if not in_path.exists():
        print(f"[master] ERROR: input not found: {in_path}", file=sys.stderr)
        sys.exit(1)

    print(f"[master] Loading {in_path.name}")
    audio, sr = sf.read(str(in_path), dtype='float32', always_2d=True)
    audio = audio.T  # (channels, samples)

    print(f"[master] Chain -> target {target_lufs:.1f} LUFS")
    mastered = process(audio, sr, target_lufs)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out_path), mastered.T, sr, subtype='PCM_24')
    print(f"[master] Written: {out_path.name}")


def cmd_render(input_path: str, out_dir: str, basename: str, targets: str, json_out: str | None) -> None:
    from .pipeline.render import parse_targets, render_targets, write_report

    parsed_targets = parse_targets(targets)
    report = render_targets(Path(input_path), Path(out_dir), basename, parsed_targets)
    write_report(report, Path(json_out) if json_out else None)


def cmd_ai_render(
    input_path: str,
    out_dir: str,
    basename: str,
    target_lufs: float,
    style: str,
    rounds: int,
    use_ai: bool,
    model: str,
    local_models: bool | None,
    json_out: str | None,
) -> None:
    from .pipeline.ai_master import render_ai_master

    render_ai_master(
        Path(input_path),
        Path(out_dir),
        basename,
        target_lufs,
        style,
        rounds,
        use_ai,
        model,
        local_models,
        Path(json_out) if json_out else None,
    )


def cmd_prefer(run_id: int, candidate_name: str, tags: list[str]) -> None:
    from .history.db import HistoryDB
    db = HistoryDB()
    run = db.get_run(run_id)
    if not run:
        print(f"[prefer] No run found with id={run_id}", file=sys.stderr)
        sys.exit(1)
    db.record_preference(run_id, candidate_name, tags or None)
    db.close()
    print(f"[prefer] Recorded: run {run_id} winner={candidate_name}")
    if tags:
        print(f"[prefer] Tags: {', '.join(tags)}")


def cmd_history(limit: int) -> None:
    from .history.db import HistoryDB
    db = HistoryDB()
    rows = db.recent_runs(limit)
    db.close()
    if not rows:
        print("No runs recorded yet.")
        return
    print(f"{'ID':>4}  {'Date':>20}  {'Basename':<40}  {'Model best':<25}  {'You chose'}")
    print("-" * 115)
    for row in rows:
        date = (row.get("run_at") or "")[:19].replace("T", " ")
        print(
            f"{row['id']:>4}  {date:>20}  {(row.get('basename') or ''):<40}  "
            f"{(row.get('model_best') or '—'):<25}  {row.get('user_best') or '—'}"
        )


def cmd_train_ranker() -> None:
    from .history.ranker import train
    result = train()
    print(json.dumps(result, indent=2))


def cmd_html_report(json_path: str, output_path: str | None) -> None:
    from .pipeline.report_html import write_ai_html_report

    path = Path(json_path)
    report = json.loads(path.read_text(encoding="utf-8"))
    out = Path(output_path) if output_path else path.with_suffix(".html")
    write_ai_html_report(report, out)
    print(f"[html-report] Written: {out}")


def cmd_models_check(download: bool) -> None:
    try:
        from .models.local_scorer import check_local_model_stack
    except ImportError as exc:
        print(json.dumps({
            "ok": False,
            "error": f"missing local model dependency: {exc}",
            "hint": "Run ./scripts/windows/install.sh and ./scripts/windows/install-local-models.sh in apps/mastering.",
        }, indent=2))
        return

    print(json.dumps(check_local_model_stack(download=download), indent=2))


def main() -> None:
    if len(sys.argv) >= 2 and sys.argv[1] == '--check':
        ok = cmd_check()
        sys.exit(0 if ok else 1)
    if len(sys.argv) >= 3 and sys.argv[1] == '--discover':
        cmd_discover(sys.argv[2])
        return
    if len(sys.argv) >= 3 and sys.argv[1] not in {
        'render',
        'ai-render',
        'single',
        'check',
        'discover',
        'models-check',
        'prefer',
        'history',
        'train-ranker',
        'html-report',
    }:
        legacy = argparse.ArgumentParser(description='Legacy single-file mastering command')
        legacy.add_argument('input')
        legacy.add_argument('output')
        legacy.add_argument('--target-lufs', type=float, default=-14.0, metavar='DB')
        args = legacy.parse_args()
        cmd_master(args.input, args.output, args.target_lufs)
        return

    parser = argparse.ArgumentParser(description='Abe standalone auto-mastering app')
    subcommands = parser.add_subparsers(dest='command')

    render_parser = subcommands.add_parser('render', help='Render one original plus one or more mastered targets')
    render_parser.add_argument('--input', required=True, help='Input WAV path')
    render_parser.add_argument('--out-dir', required=True, help='Output directory')
    render_parser.add_argument('--basename', required=True, help='Release basename for output files')
    render_parser.add_argument('--targets', default='-14,-12', help='Comma-separated LUFS targets, first is primary')
    render_parser.add_argument('--json-out', help='Optional path for machine-readable render report')

    ai_parser = subcommands.add_parser('ai-render', help='Render bounded candidates, optionally ask OpenAI to refine')
    ai_parser.add_argument('--input', required=True, help='Input WAV path')
    ai_parser.add_argument('--out-dir', required=True, help='Output directory')
    ai_parser.add_argument('--basename', required=True, help='Release basename for output files')
    ai_parser.add_argument('--target-lufs', type=float, default=-14.0, help='Candidate loudness target')
    ai_parser.add_argument(
        '--style',
        default='bright open pop EDM mastering in the style of Chainsmokers',
        help='Mastering intent passed to the AI judge',
    )
    ai_parser.add_argument('--rounds', type=int, default=1, help='AI refinement rounds after initial candidates')
    ai_parser.add_argument('--model', default='gpt-audio', help='OpenAI audio-capable model for A/B judging')
    ai_parser.add_argument('--no-ai', action='store_true', help='Disable OpenAI calls and use metric scoring only')
    local_model_group = ai_parser.add_mutually_exclusive_group()
    local_model_group.add_argument(
        '--local-models',
        dest='local_models',
        action='store_true',
        default=None,
        help='Enable local CLAP/MERT scoring; may download/cache models unless offline mode is set',
    )
    local_model_group.add_argument(
        '--no-local-models',
        dest='local_models',
        action='store_false',
        help='Disable local CLAP/MERT scoring even if MASTERING_LOCAL_MODELS=1',
    )
    ai_parser.add_argument('--json-out', help='Optional path for machine-readable AI mastering report')

    single_parser = subcommands.add_parser('single', help='Render one mastered WAV')
    single_parser.add_argument('input', help='Input WAV path')
    single_parser.add_argument('output', help='Output WAV path')
    single_parser.add_argument('--target-lufs', type=float, default=-14.0, metavar='DB')

    subcommands.add_parser('check', help='Verify VST3 plugins and presets load')

    models_parser = subcommands.add_parser('models-check', help='Verify optional local CLAP/MERT model stack')
    models_parser.add_argument(
        '--download',
        action='store_true',
        help='Allow Hugging Face downloads while checking; default only uses local cache',
    )

    discover_parser = subcommands.add_parser('discover', help='Print parameter names for a plugin key')
    discover_parser.add_argument('key')

    prefer_parser = subcommands.add_parser('prefer', help='Record your preferred candidate for a run')
    prefer_parser.add_argument('run_id', type=int, help='Run ID from history DB (shown after ai-render)')
    prefer_parser.add_argument('candidate', help='Candidate name, e.g. ai_punch_warm')
    prefer_parser.add_argument('--tags', default='', help='Comma-separated reason tags, e.g. better_low_end,release_ready')

    history_parser = subcommands.add_parser('history', help='Show recent mastering runs and preferences')
    history_parser.add_argument('--last', type=int, default=10, metavar='N', help='Number of recent runs to show')

    subcommands.add_parser('train-ranker', help='Train taste ranker from preference history')

    html_parser = subcommands.add_parser('html-report', help='Generate visual HTML from an ai-mastering-report JSON file')
    html_parser.add_argument('json', help='Path to ai-mastering-report.json')
    html_parser.add_argument('--out', help='Optional output HTML path')

    args = parser.parse_args()

    if args.command == 'check':
        ok = cmd_check()
        sys.exit(0 if ok else 1)

    if args.command == 'discover':
        cmd_discover(args.key)
        return

    if args.command == 'render':
        cmd_render(args.input, args.out_dir, args.basename, args.targets, args.json_out)
        return

    if args.command == 'ai-render':
        cmd_ai_render(
            args.input,
            args.out_dir,
            args.basename,
            args.target_lufs,
            args.style,
            args.rounds,
            not args.no_ai,
            args.model,
            args.local_models,
            args.json_out,
        )
        return

    if args.command == 'single':
        cmd_master(args.input, args.output, args.target_lufs)
        return

    if args.command == 'models-check':
        cmd_models_check(args.download)
        return

    if args.command == 'prefer':
        tags = [t.strip() for t in args.tags.split(',') if t.strip()] if args.tags else []
        cmd_prefer(args.run_id, args.candidate, tags)
        return

    if args.command == 'history':
        cmd_history(args.last)
        return

    if args.command == 'train-ranker':
        cmd_train_ranker()
        return

    if args.command == 'html-report':
        cmd_html_report(args.json, args.out)
        return

    parser.print_help()
    sys.exit(2)


if __name__ == '__main__':
    main()
