"""MERT music embedding scoring for content preservation and reference matching."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from .audio import iter_reference_audio, load_audio, resample_mono
from .config import LocalModelConfig


class MertSimilarityScorer:
    def __init__(self, config: LocalModelConfig) -> None:
        self.config = config
        self._torch: Any | None = None
        self._model: Any | None = None
        self._processor: Any | None = None
        self._device = "cpu"
        self._reference_embeddings: list[np.ndarray] | None = None

    def load(self) -> None:
        try:
            import torch
            from transformers import AutoModel, Wav2Vec2FeatureExtractor
        except ImportError as exc:
            raise RuntimeError("install torch and transformers to enable MERT scoring") from exc

        self._torch = torch
        self._device = _resolve_device(torch, self.config.device)
        self._processor = Wav2Vec2FeatureExtractor.from_pretrained(
            self.config.mert_model,
            trust_remote_code=True,
            local_files_only=self.config.local_files_only,
        )
        self._model = AutoModel.from_pretrained(
            self.config.mert_model,
            trust_remote_code=True,
            local_files_only=self.config.local_files_only,
        ).to(self._device)
        self._model.eval()

    def embed(self, audio: np.ndarray, sr: int) -> np.ndarray:
        if self._model is None or self._processor is None or self._torch is None:
            self.load()

        assert self._model is not None
        assert self._processor is not None
        assert self._torch is not None

        target_sr = int(getattr(self._processor, "sampling_rate", 24000))
        mono = resample_mono(audio, sr, target_sr, self.config.max_clip_seconds)
        inputs = self._processor(mono, sampling_rate=target_sr, return_tensors="pt")
        inputs = {key: value.to(self._device) for key, value in inputs.items()}
        with self._torch.no_grad():
            output = self._model(**inputs)
            hidden = getattr(output, "last_hidden_state", None)
            if hidden is None and getattr(output, "hidden_states", None):
                hidden = output.hidden_states[-1]
            if hidden is None:
                raise RuntimeError("MERT model did not return hidden states")
            embedding = hidden.mean(dim=1).squeeze(0)
            embedding = embedding / self._torch.clamp(embedding.norm(), min=1e-12)
        return embedding.detach().cpu().numpy().astype(np.float32)

    def reference_similarity(self, embedding: np.ndarray) -> float | None:
        references = self._load_reference_embeddings()
        if not references:
            return None
        return float(np.mean([cosine_similarity(embedding, reference) for reference in references]))

    def reference_count(self) -> int:
        return len(self._load_reference_embeddings())

    def _load_reference_embeddings(self) -> list[np.ndarray]:
        if self._reference_embeddings is not None:
            return self._reference_embeddings

        embeddings: list[np.ndarray] = []
        for path in iter_reference_audio(self.config.reference_dir):
            try:
                audio, sr = load_audio(path)
                embeddings.append(self.embed(audio, sr))
            except Exception as exc:
                print(f"[local-models] WARNING: skipping reference {Path(path).name}: {exc}")
        self._reference_embeddings = embeddings
        return embeddings


def cosine_similarity(left: np.ndarray, right: np.ndarray) -> float:
    denom = float(np.linalg.norm(left) * np.linalg.norm(right))
    if denom <= 1e-12:
        return 0.0
    return float(np.dot(left, right) / denom)


def _resolve_device(torch: Any, requested: str) -> str:
    if requested == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    if requested == "cuda" and not torch.cuda.is_available():
        return "cpu"
    return requested

