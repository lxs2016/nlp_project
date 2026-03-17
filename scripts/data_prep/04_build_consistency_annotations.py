#!/usr/bin/env python3
"""
Step 2.6: Build consistency annotations (positive: consecutive pairs; negative: random pairs).
Outputs: data/annotations/consistency_annotations.jsonl
"""
from __future__ import annotations

import json
import random
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def main() -> None:
    root = project_root()
    units_path = root / "data" / "plot_units" / "storyengine_units.jsonl"
    out_dir = root / "data" / "annotations"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "consistency_annotations.jsonl"

    seed = 42
    n_positive = 60
    n_negative = 60

    units: list[dict] = []
    with open(units_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                units.append(json.loads(line))

    random.seed(seed)
    out: list[dict] = []

    # Positive: consecutive pairs (context = prev narrative, current = this narrative)
    for i in range(1, min(n_positive + 1, len(units))):
        prev = units[i - 1]
        curr = units[i]
        out.append({
            "id": f"cons_pos_{i}",
            "context": prev.get("narrative_text") or "",
            "current_narrative": curr.get("narrative_text") or "",
            "consistent": 1,
            "notes": "consecutive pair",
        })

    # Negative: random pairs from different indices (different genre when possible)
    used = set()
    n = len(units)
    neg_count = 0
    while neg_count < n_negative:
        i, j = random.randint(0, n - 1), random.randint(0, n - 1)
        if i == j or abs(i - j) <= 1:
            continue
        key = (min(i, j), max(i, j))
        if key in used:
            continue
        used.add(key)
        ctx_meta = (units[i].get("meta") or {}).get("genre", "")
        cur_meta = (units[j].get("meta") or {}).get("genre", "")
        out.append({
            "id": f"cons_neg_{neg_count}",
            "context": (units[i].get("narrative_text") or ""),
            "current_narrative": (units[j].get("narrative_text") or ""),
            "consistent": 0,
            "notes": "random pair" if ctx_meta != cur_meta else "random pair (same genre)",
        })
        neg_count += 1

    with open(out_path, "w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    n_pos = sum(1 for r in out if r["consistent"] == 1)
    n_neg = len(out) - n_pos
    print(f"Wrote {len(out)} consistency annotations ({n_pos} pos, {n_neg} neg) -> {out_path}")


if __name__ == "__main__":
    main()
