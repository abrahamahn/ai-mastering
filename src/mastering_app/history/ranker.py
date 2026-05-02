"""Lightweight preference ranker trained on pairwise labels from the history DB."""
from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

import numpy as np

# Feature keys extracted from each candidate row.
# Deltas (candidate - source) are computed during training.
_CANDIDATE_KEYS = [
    "metric_score",
    "final_score",
    "mert_preservation",
    "clap_delta",
    "presence_db",
    "air_db",
    "sub_db",
    "side_to_mid_db",
    "crest_factor_db",
    "lufs",
]

_RANKER_PATH = Path(__file__).resolve().parents[4] / "taste_ranker.pkl"


def _feature_vector(candidate: dict[str, Any]) -> np.ndarray:
    return np.array([float(candidate.get(k) or 0.0) for k in _CANDIDATE_KEYS], dtype=np.float64)


def _pairwise_features(winner: dict[str, Any], loser: dict[str, Any]) -> np.ndarray:
    """Pairwise diff: winner - loser. Label = 1 (winner preferred)."""
    return _feature_vector(winner) - _feature_vector(loser)


def train(db_path: Path | None = None, output_path: Path | None = None) -> dict[str, Any]:
    """Train a logistic regression ranker from pairwise preference labels.

    Returns a report dict with feature importances and accuracy.
    """
    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import cross_val_score
        from sklearn.preprocessing import StandardScaler
        from sklearn.pipeline import Pipeline
    except ImportError:
        return {"ok": False, "error": "scikit-learn not installed — run: pip install scikit-learn"}

    from .db import HistoryDB

    db = HistoryDB(db_path)
    pairs = db.pairwise_training_data()
    db.close()

    if len(pairs) < 4:
        return {"ok": False, "error": f"need at least 4 pairwise labels, have {len(pairs)}"}

    X_rows: list[np.ndarray] = []
    y: list[int] = []
    for pair in pairs:
        diff = _pairwise_features(pair["winner"], pair["loser"])
        X_rows.append(diff)
        y.append(1)
        X_rows.append(-diff)
        y.append(0)

    X = np.stack(X_rows)
    y_arr = np.array(y)

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(max_iter=1000, C=1.0)),
    ])
    pipeline.fit(X, y_arr)

    cv_scores = cross_val_score(pipeline, X, y_arr, cv=min(5, len(pairs)), scoring="accuracy")
    coef = pipeline.named_steps["clf"].coef_[0]
    importances = {k: float(c) for k, c in zip(_CANDIDATE_KEYS, coef)}

    save_path = output_path or _RANKER_PATH
    with open(save_path, "wb") as f:
        pickle.dump(pipeline, f)

    return {
        "ok": True,
        "n_pairs": len(pairs),
        "n_training_rows": len(X_rows),
        "cv_accuracy_mean": float(cv_scores.mean()),
        "cv_accuracy_std": float(cv_scores.std()),
        "feature_importances": importances,
        "saved_to": str(save_path),
    }


class TasteRanker:
    """Load a trained ranker and score a candidate dict.

    Returns a float taste score. Positive = preferred, negative = disfavored.
    Returns 0.0 if no ranker is trained yet (graceful degradation).
    """

    def __init__(self, path: Path | None = None) -> None:
        ranker_path = path or _RANKER_PATH
        self._pipeline = None
        if ranker_path.exists():
            with open(ranker_path, "rb") as f:
                self._pipeline = pickle.load(f)

    @property
    def available(self) -> bool:
        return self._pipeline is not None

    def score(self, candidate: dict[str, Any]) -> float:
        if not self._pipeline:
            return 0.0
        vec = _feature_vector(candidate).reshape(1, -1)
        # Use decision_function (log-odds) for a continuous score, not hard class
        try:
            return float(self._pipeline.decision_function(vec)[0])
        except Exception:
            return 0.0
