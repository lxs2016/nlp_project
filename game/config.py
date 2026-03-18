"""Data path constants and WorldBible loading. All paths relative to project root."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Data preparation outputs
DIR_DATA = _PROJECT_ROOT / "data"
DIR_ANNOTATIONS = DIR_DATA / "annotations"
DIR_PLOT_UNITS = DIR_DATA / "plot_units"
DIR_WORLD_BIBLE = DIR_DATA / "world_bible"
DIR_GOLD_TRAJECTORIES = DIR_DATA / "gold_trajectories"

PATH_WORLD_BIBLE = DIR_WORLD_BIBLE / "world_main.yaml"
PATH_INTENT_TRAIN = DIR_ANNOTATIONS / "intent_train.jsonl"
PATH_INTENT_VAL = DIR_ANNOTATIONS / "intent_val.jsonl"
PATH_INTENT_TEST = DIR_ANNOTATIONS / "intent_test.jsonl"
PATH_PLOT_UNITS = DIR_PLOT_UNITS / "storyengine_units.jsonl"
PATH_CONSISTENCY_ANNOTATIONS = DIR_ANNOTATIONS / "consistency_annotations.jsonl"

# Model outputs
DIR_MODELS = _PROJECT_ROOT / "models"
DIR_INTENT_MODEL = DIR_MODELS / "intent"


def load_world_bible(path: Path | None = None) -> dict[str, Any]:
    """Load WorldBible YAML. Returns dict with setting, characters, locations, rules_forbidden, main_conflict, key_items."""
    p = path or PATH_WORLD_BIBLE
    if not p.exists():
        raise FileNotFoundError(f"WorldBible not found: {p}")
    with open(p, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


def get_project_root() -> Path:
    return _PROJECT_ROOT
