"""CLAP audio-text style scoring."""
from __future__ import annotations

from typing import Any

import numpy as np

from .audio import resample_mono
from .config import LocalModelConfig


class ClapStyleScorer:
    def __init__(self, config: LocalModelConfig) -> None:
        self.config = config
        self._torch: Any | None = None
        self._model: Any | None = None
        self._processor: Any | None = None
        self._device = "cpu"

    def load(self) -> None:
        try:
            import torch
            from transformers import ClapModel, ClapProcessor
        except ImportError as exc:
            raise RuntimeError("install torch and transformers to enable CLAP scoring") from exc

        self._torch = torch
        self._device = _resolve_device(torch, self.config.device)
        self._processor = ClapProcessor.from_pretrained(
            self.config.clap_model,
            local_files_only=self.config.local_files_only,
        )
        self._model = ClapModel.from_pretrained(
            self.config.clap_model,
            local_files_only=self.config.local_files_only,
        ).to(self._device)
        self._model.eval()

    def style_similarity(self, audio: np.ndarray, sr: int, style: str) -> float:
        if self._model is None or self._processor is None or self._torch is None:
            self.load()

        assert self._model is not None
        assert self._processor is not None
        assert self._torch is not None

        target_sr = int(getattr(self._processor.feature_extractor, "sampling_rate", 48000))
        mono = resample_mono(audio, sr, target_sr, self.config.max_clip_seconds)
        inputs = self._processor(
            audios=mono,
            sampling_rate=target_sr,
            text=[style],
            return_tensors="pt",
            padding=True,
        )
        inputs = {key: value.to(self._device) for key, value in inputs.items()}
        with self._torch.no_grad():
            audio_features = self._model.get_audio_features(
                input_features=inputs["input_features"],
                is_longer=inputs.get("is_longer"),
            )
            text_features = self._model.get_text_features(
                input_ids=inputs["input_ids"],
                attention_mask=inputs["attention_mask"],
            )

        audio_features = _normalize(self._torch, audio_features)
        text_features = _normalize(self._torch, text_features)
        return float((audio_features @ text_features.T).squeeze().detach().cpu().item())


def _resolve_device(torch: Any, requested: str) -> str:
    if requested == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    if requested == "cuda" and not torch.cuda.is_available():
        return "cpu"
    return requested


def _normalize(torch: Any, tensor: Any) -> Any:
    return tensor / torch.clamp(tensor.norm(dim=-1, keepdim=True), min=1e-12)

