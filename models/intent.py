"""IntentRecognizer: Transformers sequence classification, predict(text) -> (label, confidence)."""
from __future__ import annotations

from pathlib import Path
from typing import Tuple

# Lazy imports so inference works without torch/transformers when using fallback
_DEFAULT_LABEL = "continue"
_LABELS = ["continue", "start", "fail_forward", "meta_help", "end", "init"]


class IntentRecognizer:
    """Predict intent from player input text. Uses Transformers or fallback to default."""

    def __init__(self, model_path: Path | None = None) -> None:
        self._model_path = Path(model_path) if model_path else None
        self._pipe = None
        self._label2id: dict[str, int] = {}
        self._id2label: dict[int, str] = {}
        if model_path and Path(model_path).exists():
            self._load_model()

    def _load_model(self) -> None:
        try:
            from transformers import pipeline
            self._pipe = pipeline(
                "text-classification",
                model=str(self._model_path),
                top_k=1,
            )
            # Recover id2label from config if available
            from transformers import AutoConfig
            cfg = AutoConfig.from_pretrained(str(self._model_path))
            if getattr(cfg, "id2label", None):
                self._id2label = {int(k): v for k, v in cfg.id2label.items()}
            else:
                self._id2label = {i: _LABELS[i] for i in range(len(_LABELS))}
        except Exception:
            self._pipe = None

    def predict(self, text: str) -> Tuple[str, float]:
        """Return (intent_label, confidence). Falls back to ('continue', 0.0) if no model."""
        if not text or not text.strip():
            return _DEFAULT_LABEL, 0.0
        if self._pipe is None:
            return _DEFAULT_LABEL, 0.0
        try:
            out = self._pipe(text.strip()[:512], top_k=1)
            if out and len(out) > 0:
                label = out[0].get("label", _DEFAULT_LABEL)
                score = float(out[0].get("score", 0.0))
                return label, score
        except Exception:
            pass
        return _DEFAULT_LABEL, 0.0
