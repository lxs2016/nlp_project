#!/usr/bin/env python3
"""
Step 2.5: Build intent annotations from plot units (meta.type -> intent_label), split train/val/test.
Outputs: data/annotations/intent_train.jsonl, intent_val.jsonl, intent_test.jsonl
"""
from __future__ import annotations

import json
import random
from pathlib import Path

# meta.type -> intent_label (plan 2.5)
TYPE_TO_INTENT = {
    "scene_continuation": "continue",
    "genre_opening": "start",
    "fail_forward": "fail_forward",
    "command_response": "meta_help",
    "session_end": "end",
    "init_sequence": "init",
}
DEFAULT_INTENT = "continue"


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def main() -> None:
    root = project_root()
    units_path = root / "data" / "plot_units" / "storyengine_units.jsonl"
    out_dir = root / "data" / "annotations"
    out_dir.mkdir(parents=True, exist_ok=True)

    seed = 42
    train_ratio, val_ratio = 0.8, 0.1  # test = 0.1

    units: list[dict] = []
    with open(units_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                units.append(json.loads(line))

    rows: list[dict] = []
    for u in units:
        meta = u.get("meta") or {}
        raw_type = meta.get("type")
        intent = TYPE_TO_INTENT.get(str(raw_type), DEFAULT_INTENT) if raw_type else DEFAULT_INTENT
        rows.append({
            "plot_unit_id": u.get("plot_unit_id"),
            "input_text": u.get("player_input") or "",
            "intent_label": intent,
            "source": "storyengine",
        })

    random.seed(seed)
    indices = list(range(len(rows)))
    random.shuffle(indices)
    n = len(indices)
    n_train = int(n * train_ratio)
    n_val = int(n * val_ratio)
    train_idx = set(indices[:n_train])
    val_idx = set(indices[n_train : n_train + n_val])
    test_idx = set(indices[n_train + n_val :])

    def write_split(name: str, idx_set: set[int]) -> None:
        path = out_dir / f"intent_{name}.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            for i in idx_set:
                f.write(json.dumps(rows[i], ensure_ascii=False) + "\n")
        print(f"  {name}: {len(idx_set)} -> {path}")

    write_split("train", train_idx)
    write_split("val", val_idx)
    write_split("test", test_idx)
    print(f"Intent annotations: {len(rows)} total (train/val/test 80/10/10)")


if __name__ == "__main__":
    main()
