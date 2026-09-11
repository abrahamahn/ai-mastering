#!/usr/bin/env python3
"""Compatibility entry point for the standalone mastering app.

This wrapper keeps the standalone CLI stable while adapting integration-only
flags used by abe-website. The core CLI remains in mastering_app.cli.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Callable


def _compat_path(value: str | os.PathLike[str]) -> Path:
    """Accept WSL /mnt/<drive> paths when executed by Windows Python."""
    text = str(value).strip()
    normalized = text.replace("\\", "/")
    if os.name == "nt" and normalized.lower().startswith("/mnt/") and len(normalized) >= 7:
        drive = normalized[5]
        if drive.isalpha() and normalized[6] == "/":
            return Path(f"{drive.upper()}:/{normalized[7:]}")
    return Path(text)


def _prepare_ai_render_args(argv: list[str]) -> list[str]:
    """Translate abe-website compatibility flags into runtime settings."""
    candidate_count: int | None = None
    source_mode: str | None = None
    cleaned: list[str] = []
    index = 0

    while index < len(argv):
        arg = argv[index]

        if arg == "--candidate-count":
            if index + 1 >= len(argv):
                raise ValueError("--candidate-count requires a value")
            raw_value = argv[index + 1]
            index += 2
            try:
                candidate_count = int(raw_value)
            except ValueError as exc:
                raise ValueError("--candidate-count must be an integer from 1 to 5") from exc
            continue

        if arg.startswith("--candidate-count="):
            raw_value = arg.split("=", 1)[1]
            try:
                candidate_count = int(raw_value)
            except ValueError as exc:
                raise ValueError("--candidate-count must be an integer from 1 to 5") from exc
            index += 1
            continue

        if arg == "--mode":
            if index + 1 >= len(argv):
                raise ValueError("--mode requires a value")
            source_mode = argv[index + 1].strip().lower()
            index += 2
            continue

        if arg.startswith("--mode="):
            source_mode = arg.split("=", 1)[1].strip().lower()
            index += 1
            continue

        cleaned.append(arg)
        index += 1

    if candidate_count is not None:
        if candidate_count < 1 or candidate_count > 5:
            raise ValueError("--candidate-count must be between 1 and 5")
        os.environ["MASTERING_CANDIDATE_COUNT"] = str(candidate_count)

    if source_mode is not None:
        if source_mode not in {"suno", "engineer"}:
            raise ValueError("--mode must be either 'suno' or 'engineer'")
        os.environ["MASTERING_SOURCE_MODE"] = source_mode
        if source_mode == "engineer":
            cleaned = _rewrite_engineer_style(cleaned)

    return cleaned


def _rewrite_engineer_style(argv: list[str]) -> list[str]:
    """Avoid feeding the Suno-specific default intent into engineer mode."""
    rewritten = list(argv)
    for index, arg in enumerate(rewritten):
        if arg == "--style" and index + 1 < len(rewritten):
            rewritten[index + 1] = _engineer_style(rewritten[index + 1])
        elif arg.startswith("--style="):
            rewritten[index] = f"--style={_engineer_style(arg.split('=', 1)[1])}"
    return rewritten


def _engineer_style(style: str) -> str:
    if "suno" not in style.lower():
        return style
    return re.sub(
        r"tame\s+suno\s+ai\s+high-end\s+distortion",
        "transparent full-range tonal polish",
        style,
        flags=re.IGNORECASE,
    )


def _install_ai_render_compat() -> None:
    """Apply integration runtime settings without changing the standalone CLI API."""
    raw_count = os.environ.get("MASTERING_CANDIDATE_COUNT")
    if raw_count is None:
        return

    candidate_count = max(1, min(5, int(raw_count)))
    from mastering_app.pipeline import ai_master

    original_candidate_settings = ai_master.candidate_settings

    def limited_candidate_settings(style: str):
        return original_candidate_settings(style)[:candidate_count]

    ai_master.candidate_settings = limited_candidate_settings


def _candidate_path(candidate: dict[str, object]) -> Path | None:
    raw = candidate.get("path") or candidate.get("wav_path")
    if not isinstance(raw, str) or not raw.strip():
        return None
    return _compat_path(raw)


def _normalized_path(path: Path) -> str:
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path.absolute()
    text = str(resolved)
    return text.lower() if os.name == "nt" else text


def _choose_from_report(
    report_path: Path,
    output_path: Path,
    *,
    clean: bool = False,
    interactive: bool = True,
    input_fn: Callable[[str], str] = input,
) -> str:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    raw_candidates = report.get("candidates")
    if not isinstance(raw_candidates, list) or not raw_candidates:
        raise ValueError(f"No mastering candidates found in report: {report_path}")

    candidates: list[dict[str, object]] = []
    for raw_candidate in raw_candidates:
        if not isinstance(raw_candidate, dict):
            continue
        path = _candidate_path(raw_candidate)
        if path is not None and path.is_file():
            candidates.append(raw_candidate)

    if not candidates:
        raise FileNotFoundError(f"No candidate WAV files from the report still exist: {report_path}")

    best_name = str(report.get("best_candidate") or "")
    default_index = next(
        (index for index, candidate in enumerate(candidates) if str(candidate.get("name") or "") == best_name),
        0,
    )

    print("\nAvailable mastering candidates:")
    for index, candidate in enumerate(candidates, start=1):
        name = str(candidate.get("name") or f"candidate-{index}")
        score = candidate.get("score")
        score_text = f" | score {float(score):.1f}" if isinstance(score, (int, float)) else ""
        marker = " | model best" if name == best_name else ""
        print(f"  {index}. {name}{score_text}{marker}")

    selected_index = default_index
    if interactive:
        default_name = str(candidates[default_index].get("name") or "model best")
        raw_choice = input_fn(
            f"Choose final master [1-{len(candidates)}] "
            f"(Enter = {default_index + 1}, {default_name}): "
        ).strip()
        if raw_choice:
            if raw_choice.isdigit():
                numeric = int(raw_choice)
                if numeric < 1 or numeric > len(candidates):
                    raise ValueError(f"Selection must be between 1 and {len(candidates)}")
                selected_index = numeric - 1
            else:
                matching_index = next(
                    (
                        index
                        for index, candidate in enumerate(candidates)
                        if str(candidate.get("name") or "").lower() == raw_choice.lower()
                    ),
                    None,
                )
                if matching_index is None:
                    names = ", ".join(str(candidate.get("name") or "") for candidate in candidates)
                    raise ValueError(f"Unknown candidate '{raw_choice}'. Available: {names}")
                selected_index = matching_index
    else:
        print(
            f"[choose] Non-interactive input; using model best/default: "
            f"{str(candidates[selected_index].get('name') or selected_index + 1)}"
        )

    selected = candidates[selected_index]
    selected_name = str(selected.get("name") or f"candidate-{selected_index + 1}")
    selected_path = _candidate_path(selected)
    if selected_path is None or not selected_path.is_file():
        raise FileNotFoundError(f"Selected mastering candidate not found: {selected_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(selected_path, output_path)
    print(f"[choose] Selected {selected_name} -> {output_path}")

    if clean:
        keep = {_normalized_path(selected_path)}
        input_raw = report.get("input")
        if isinstance(input_raw, str) and input_raw.strip():
            source_path = _compat_path(input_raw)
            if source_path.is_file():
                keep.add(_normalized_path(source_path))

        removed = 0
        for candidate in candidates:
            path = _candidate_path(candidate)
            if path is None or _normalized_path(path) in keep:
                continue
            if path.exists():
                path.unlink()
                removed += 1

        best_path_raw = report.get("best_path")
        if isinstance(best_path_raw, str) and best_path_raw.strip():
            best_path = _compat_path(best_path_raw)
            if _normalized_path(best_path) not in keep and best_path.exists():
                best_path.unlink()
                removed += 1
        print(f"[choose] Cleaned {removed} intermediate WAV file(s).")

    return selected_name


def _run_choose(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(
        prog="master.py choose",
        description="Choose a final WAV from an AI mastering report",
    )
    parser.add_argument("--report", required=True, help="Path to ai-mastering-report.json")
    parser.add_argument("--out", required=True, help="Destination WAV path")
    parser.add_argument("--clean", action="store_true", help="Delete non-selected candidate WAVs after copying")
    args = parser.parse_args(argv)

    report_path = _compat_path(args.report)
    output_path = _compat_path(args.out)
    if not report_path.is_file():
        parser.error(f"report not found: {report_path}")

    _choose_from_report(
        report_path,
        output_path,
        clean=args.clean,
        interactive=sys.stdin.isatty(),
    )


def main() -> None:
    command = sys.argv[1] if len(sys.argv) >= 2 else None

    if command == "choose":
        _run_choose(sys.argv[2:])
        return

    if command == "ai-render":
        try:
            sys.argv = [sys.argv[0], sys.argv[1], *_prepare_ai_render_args(sys.argv[2:])]
        except ValueError as exc:
            print(f"master.py: error: {exc}", file=sys.stderr)
            raise SystemExit(2) from exc

    src = Path(__file__).resolve().parent / "src"
    sys.path.insert(0, str(src))

    if command == "ai-render":
        _install_ai_render_compat()

    from mastering_app.cli import main as cli_main

    cli_main()


if __name__ == "__main__":
    main()
