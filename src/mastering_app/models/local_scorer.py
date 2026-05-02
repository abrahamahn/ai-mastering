"""Combine optional local model scores with deterministic mastering metrics."""
from __future__ import annotations

from dataclasses import replace
from typing import Any

import numpy as np

from .audio import load_audio
from .clap_style import ClapStyleScorer
from .config import LocalModelConfig, config_from_env
from .mert_similarity import MertSimilarityScorer, cosine_similarity


def apply_local_model_scores(
    candidates: list[dict[str, Any]],
    source_audio: np.ndarray,
    sr: int,
    style: str,
    enabled: bool | None,
) -> dict[str, Any]:
    config = config_from_env(enabled)
    if not config.enabled:
        _reset_candidate_scores(candidates)
        return {"enabled": False, "reason": "local model scoring disabled"}

    report: dict[str, Any] = {
        "enabled": True,
        "device": config.device,
        "clap": {"enabled": config.clap_enabled, "model": config.clap_model},
        "mert": {"enabled": config.mert_enabled, "model": config.mert_model, "reference_count": 0},
    }
    _reset_candidate_scores(candidates)

    if config.clap_enabled:
        try:
            clap_report = _apply_clap_scores(candidates, source_audio, sr, style, config)
            report["clap"].update(clap_report)
        except Exception as exc:
            report["clap"].update({"enabled": False, "error": str(exc)})

    if config.mert_enabled:
        try:
            mert_report = _apply_mert_scores(candidates, source_audio, sr, config)
            report["mert"].update(mert_report)
        except Exception as exc:
            report["mert"].update({"enabled": False, "error": str(exc)})

    for candidate in candidates:
        candidate["score"] = float(round(candidate["score"], 3))

    return report


def check_local_model_stack(download: bool = False) -> dict[str, Any]:
    config = replace(config_from_env(True), local_files_only=not download)
    dummy = np.zeros((1, 24000), dtype=np.float32)
    report: dict[str, Any] = {
        "download": download,
        "clap": {"model": config.clap_model},
        "mert": {"model": config.mert_model},
    }

    try:
        clap = ClapStyleScorer(config)
        report["clap"]["similarity"] = clap.style_similarity(dummy, 24000, "bright open pop EDM")
        report["clap"]["ok"] = True
    except Exception as exc:
        report["clap"]["ok"] = False
        report["clap"]["error"] = str(exc)

    try:
        mert = MertSimilarityScorer(config)
        embedding = mert.embed(dummy, 24000)
        report["mert"]["embedding_dim"] = int(embedding.shape[0])
        report["mert"]["ok"] = True
    except Exception as exc:
        report["mert"]["ok"] = False
        report["mert"]["error"] = str(exc)

    return report


def _reset_candidate_scores(candidates: list[dict[str, Any]]) -> None:
    for candidate in candidates:
        metric_score = float(candidate.get("metric_score", candidate.get("score", 0.0)))
        candidate["metric_score"] = metric_score
        candidate["score"] = metric_score
        candidate["local_model_scores"] = {}
        candidate["score_notes"] = list(candidate.get("metric_score_notes", candidate.get("score_notes", [])))


def _apply_clap_scores(
    candidates: list[dict[str, Any]],
    source_audio: np.ndarray,
    sr: int,
    style: str,
    config: LocalModelConfig,
) -> dict[str, Any]:
    scorer = ClapStyleScorer(config)
    source_similarity = scorer.style_similarity(source_audio, sr, style)

    for candidate in candidates:
        if candidate["name"] == "original":
            audio = source_audio
            candidate_sr = sr
        else:
            audio, candidate_sr = load_audio(candidate["path"])
        similarity = source_similarity if candidate["name"] == "original" else scorer.style_similarity(audio, candidate_sr, style)
        delta = similarity - source_similarity
        adjustment = float(np.clip(delta * config.clap_weight, -10.0, 10.0))
        candidate["score"] += adjustment
        candidate["local_model_scores"]["clap_style_similarity"] = similarity
        candidate["local_model_scores"]["clap_style_delta"] = delta
        candidate["local_model_scores"]["clap_score_adjustment"] = adjustment
        if abs(adjustment) >= 0.5:
            candidate["score_notes"].append(f"CLAP style {delta:+.3f} ({adjustment:+.1f})")

    return {"source_similarity": source_similarity}


def _apply_mert_scores(
    candidates: list[dict[str, Any]],
    source_audio: np.ndarray,
    sr: int,
    config: LocalModelConfig,
) -> dict[str, Any]:
    scorer = MertSimilarityScorer(config)
    source_embedding = scorer.embed(source_audio, sr)
    source_reference_similarity = scorer.reference_similarity(source_embedding)

    for candidate in candidates:
        if candidate["name"] == "original":
            embedding = source_embedding
        else:
            audio, candidate_sr = load_audio(candidate["path"])
            embedding = scorer.embed(audio, candidate_sr)

        preservation = cosine_similarity(source_embedding, embedding)
        creative = bool((candidate.get("settings") or {}).get("creative_mode"))
        preservation_floor = 0.88 if creative else 0.92
        if candidate["name"] == "original":
            preservation_adjustment = 0.0
        elif preservation < preservation_floor:
            # Hard guardrail: content damaged too much by processing. Creative candidates
            # get a lower floor because intentional tone/color changes should not be
            # punished as heavily as accidental content drift.
            preservation_adjustment = -7.0 if creative else -12.0
        else:
            # Small bonus for closeness once past guardrail; original no longer wins by default
            preservation_adjustment = float(np.clip((preservation - 0.90) * 10.0, 0.0, 2.0))
        reference_similarity = scorer.reference_similarity(embedding)
        reference_adjustment = 0.0
        if reference_similarity is not None and source_reference_similarity is not None:
            reference_delta = reference_similarity - source_reference_similarity
            reference_adjustment = float(np.clip(reference_delta * config.mert_reference_weight, -8.0, 8.0))
        else:
            reference_delta = 0.0

        candidate["score"] += preservation_adjustment + reference_adjustment
        candidate["local_model_scores"]["mert_content_preservation"] = preservation
        candidate["local_model_scores"]["mert_preservation_adjustment"] = preservation_adjustment
        candidate["local_model_scores"]["mert_reference_similarity"] = reference_similarity
        candidate["local_model_scores"]["mert_reference_delta"] = reference_delta
        candidate["local_model_scores"]["mert_reference_adjustment"] = reference_adjustment
        if abs(preservation_adjustment) >= 0.5:
            candidate["score_notes"].append(
                f"MERT preservation {preservation:.3f} ({preservation_adjustment:+.1f})"
            )
        if abs(reference_adjustment) >= 0.5:
            candidate["score_notes"].append(
                f"MERT reference {reference_delta:+.3f} ({reference_adjustment:+.1f})"
            )

    return {
        "source_reference_similarity": source_reference_similarity,
        "reference_count": scorer.reference_count(),
    }
