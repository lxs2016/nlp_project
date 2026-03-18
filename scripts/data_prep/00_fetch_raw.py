#!/usr/bin/env python3
"""
Step 2.2: Fetch StoryEngine dataset from Hugging Face and save as JSONL.
Downloads data/train.jsonl and writes data/raw/storyengine/storyengine_raw.jsonl, meta_stats.json, README.md
"""
from __future__ import annotations

import json
from pathlib import Path
from collections import Counter

from huggingface_hub import hf_hub_download


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def main() -> None:
    root = project_root()
    out_dir = root / "data" / "raw" / "storyengine"
    out_dir.mkdir(parents=True, exist_ok=True)

    raw_path = out_dir / "storyengine_raw.jsonl"
    print("Downloading SatorTenet/storyengine-dataset (data/train.jsonl) from Hugging Face...")
    local_path = hf_hub_download(
        repo_id="SatorTenet/storyengine-dataset",
        filename="data/train.jsonl",
        repo_type="dataset",
        local_dir=root / ".cache" / "storyengine_download",
        local_dir_use_symlinks=False,
    )

    type_counter: Counter[str] = Counter()
    n = 0
    with open(local_path, "r", encoding="utf-8") as fin, open(
        raw_path, "w", encoding="utf-8"
    ) as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            meta = rec.get("meta") or {}
            t = meta.get("type")
            if t is not None:
                type_counter[str(t)] += 1
            fout.write(line + "\n")
            n += 1

    meta_stats = {
        "source": "SatorTenet/storyengine-dataset",
        "huggingface_repo": "SatorTenet/storyengine-dataset",
        "filename": "data/train.jsonl",
        "total_examples": n,
        "meta_type_distribution": dict(type_counter),
    }
    with open(out_dir / "meta_stats.json", "w", encoding="utf-8") as f:
        json.dump(meta_stats, f, ensure_ascii=False, indent=2)

    readme = f"""# StoryEngine raw data

- **Source**: [SatorTenet/storyengine-dataset](https://huggingface.co/datasets/SatorTenet/storyengine-dataset) (Hugging Face)
- **Total rows**: {n}
- **Format**: One JSON object per line (JSONL). Each object has `messages` (list of {{role, content}}) and `meta` (type, genre, polti, etc.).
- **License**: Apache 2.0

## meta.type distribution

| type | count |
|------|-------|
"""
    for t, c in sorted(type_counter.items(), key=lambda x: -x[1]):
        readme += f"| {t} | {c} |\n"
    (out_dir / "README.md").write_text(readme, encoding="utf-8")

    print(f"Wrote {n} examples to {raw_path}")
    print("meta.type distribution:", dict(type_counter))


if __name__ == "__main__":
    main()
