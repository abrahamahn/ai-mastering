"""Configuration for optional local audio model scoring."""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class LocalModelConfig:
    enabled: bool = True
    clap_enabled: bool = True
    mert_enabled: bool = True
    local_files_only: bool = False
    device: str = "auto"
    clap_model: str = "laion/larger_clap_music"
    mert_model: str = "m-a-p/MERT-v1-95M"
    reference_dir: Path | None = None
    max_clip_seconds: float = 24.0
    clap_weight: float = 80.0
    mert_preservation_weight: float = 180.0
    mert_reference_weight: float = 110.0


def local_models_enabled_from_env() -> bool:
    return _env_bool("MASTERING_LOCAL_MODELS", True)


def config_from_env(enabled: bool | None = None) -> LocalModelConfig:
    reference_dir = _env_path("MASTERING_REFERENCE_DIR")
    return LocalModelConfig(
        enabled=local_models_enabled_from_env() if enabled is None else enabled,
        clap_enabled=_env_bool("MASTERING_CLAP", True),
        mert_enabled=_env_bool("MASTERING_MERT", True),
        local_files_only=_env_bool("MASTERING_LOCAL_MODELS_OFFLINE", False),
        device=os.environ.get("MASTERING_MODEL_DEVICE", "auto").strip() or "auto",
        clap_model=os.environ.get("MASTERING_CLAP_MODEL", "laion/larger_clap_music").strip(),
        mert_model=os.environ.get("MASTERING_MERT_MODEL", "m-a-p/MERT-v1-95M").strip(),
        reference_dir=reference_dir,
        max_clip_seconds=_env_float("MASTERING_MODEL_CLIP_SECONDS", 24.0),
        clap_weight=_env_float("MASTERING_CLAP_WEIGHT", 80.0),
        mert_preservation_weight=_env_float("MASTERING_MERT_PRESERVATION_WEIGHT", 180.0),
        mert_reference_weight=_env_float("MASTERING_MERT_REFERENCE_WEIGHT", 110.0),
    )


def _env_bool(name: str, fallback: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return fallback
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, fallback: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return fallback
    try:
        return float(raw)
    except ValueError:
        return fallback


def _env_path(name: str) -> Path | None:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return None
    return Path(raw).expanduser()
