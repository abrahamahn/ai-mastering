"""Optional Apollo restoration wrapper.

Apollo is intentionally integrated as an external, opt-in process. The
mastering app does not vendor Apollo or assume its dependencies are installed;
it shells out to a local checkout and auditions the restored output as another
candidate source.
"""
from __future__ import annotations

import os
import shlex
import subprocess
import time
from pathlib import Path
from typing import Any


TRUE_VALUES = {"1", "true", "yes", "on"}


def apollo_enabled(cli_value: bool | None) -> bool:
    if cli_value is not None:
        return bool(cli_value)
    return os.environ.get("MASTERING_APOLLO", "").strip().lower() in TRUE_VALUES


def restore_with_apollo(
    input_path: Path,
    out_dir: Path,
    basename: str,
    cli_enabled: bool | None = None,
) -> tuple[Path | None, dict[str, Any]]:
    """Run Apollo if enabled and return the restored WAV path plus a report."""
    enabled = apollo_enabled(cli_enabled)
    report: dict[str, Any] = {
        "enabled": enabled,
        "engine": "apollo",
        "ok": False,
    }
    if not enabled:
        report["reason"] = "disabled"
        return None, report

    repo_text = os.environ.get("MASTERING_APOLLO_REPO", "").strip()
    if not repo_text:
        report.update({
            "error": "MASTERING_APOLLO_REPO is not set",
            "hint": "Set MASTERING_APOLLO_REPO to a local Apollo checkout, or disable MASTERING_APOLLO.",
        })
        return None, report

    repo = _path_arg(repo_text)
    report["repo"] = str(repo)
    if not repo.exists():
        report.update({
            "error": f"Apollo repo not found: {repo}",
            "hint": "Clone/install Apollo locally, then set MASTERING_APOLLO_REPO to that folder.",
        })
        return None, report

    output_path = out_dir / f"{basename}_apollo_restored.wav"
    command = _build_command(repo, _path_arg(input_path), _path_arg(output_path))
    report["command"] = _redacted_command(command)
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=str(repo),
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        report.update({"error": str(exc), "hint": "Check MASTERING_APOLLO_PYTHON or MASTERING_APOLLO_COMMAND."})
        return None, report
    except Exception as exc:
        report["error"] = str(exc)
        return None, report

    report["elapsed_seconds"] = round(time.monotonic() - started, 3)
    report["returncode"] = completed.returncode
    if completed.stdout.strip():
        report["stdout_tail"] = completed.stdout.strip()[-2000:]
    if completed.stderr.strip():
        report["stderr_tail"] = completed.stderr.strip()[-2000:]

    if completed.returncode != 0:
        report["error"] = f"Apollo exited with code {completed.returncode}"
        return None, report
    if not output_path.exists():
        report.update({
            "error": f"Apollo finished but did not write expected output: {output_path}",
            "hint": "Set MASTERING_APOLLO_COMMAND if your Apollo checkout uses different CLI arguments.",
        })
        return None, report

    report.update({
        "ok": True,
        "path": str(output_path),
    })
    return output_path, report


def _build_command(repo: Path, input_path: Path, output_path: Path) -> list[str]:
    template = os.environ.get("MASTERING_APOLLO_COMMAND", "").strip()
    if template:
        command_text = template.format(
            repo=_shell_path(repo),
            input=_shell_path(input_path),
            output=_shell_path(output_path),
        )
        command = shlex.split(command_text, posix=True)
    else:
        python = os.environ.get("MASTERING_APOLLO_PYTHON", "python").strip() or "python"
        script = _path_arg(os.environ.get("MASTERING_APOLLO_SCRIPT", str(repo / "inference.py")))
        if not script.is_absolute():
            script = repo / script
        command = [
            python,
            str(script),
            "--in_wav",
            str(input_path),
            "--out_wav",
            str(output_path),
        ]

    extra = os.environ.get("MASTERING_APOLLO_ARGS", "").strip()
    if extra:
        command.extend(shlex.split(extra, posix=True))
    return command


def _path_arg(value: str | Path) -> Path:
    text = str(value).strip()
    normalized = text.replace("\\", "/")
    if os.name == "nt" and normalized.lower().startswith("/mnt/") and len(normalized) >= 7:
        drive = normalized[5]
        if drive.isalpha() and normalized[6] == "/":
            return Path(f"{drive.upper()}:/{normalized[7:]}")
    return Path(text)


def _shell_path(path: Path) -> str:
    return str(path).replace("\\", "/")


def _redacted_command(command: list[str]) -> list[str]:
    redacted: list[str] = []
    for item in command:
        if "token" in item.lower() or "key" in item.lower():
            redacted.append("<redacted>")
        else:
            redacted.append(item)
    return redacted
