#!/usr/bin/env python3
"""
Step 2.3: Clean text noise in StoryEngine raw JSONL.
Outputs: data/cleaned/storyengine/storyengine_cleaned.jsonl, cleaning_rules.txt
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def normalize_whitespace(text: str) -> str:
    """Collapse runs of whitespace to single space; keep one newline between paragraphs."""
    if not text:
        return text
    # Remove control characters
    text = "".join(c for c in text if unicodedata.category(c) != "Cc" or c in "\n\t")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Paragraphs: split by double newline or more, then rejoin with single \n
    paragraphs = re.split(r"\n\s*\n", text)
    cleaned = []
    for p in paragraphs:
        p = " ".join(p.split())
        if p:
            cleaned.append(p)
    return "\n".join(cleaned)


def clean_string(s: str) -> str:
    if not isinstance(s, str):
        return str(s)
    s = s.encode("utf-8", errors="replace").decode("utf-8")
    return normalize_whitespace(s)


def clean_record(rec: dict) -> dict:
    out: dict = {}
    if "messages" in rec:
        out["messages"] = []
        for m in rec["messages"]:
            msg = dict(m)
            if "content" in msg and isinstance(msg["content"], str):
                msg["content"] = clean_string(msg["content"])
            out["messages"].append(msg)
    if "meta" in rec:
        meta = rec["meta"]
        out["meta"] = {}
        for k, v in meta.items():
            if isinstance(v, str):
                out["meta"][k] = clean_string(v)
            else:
                out["meta"][k] = v
    return out


def main() -> None:
    root = project_root()
    raw_path = root / "data" / "raw" / "storyengine" / "storyengine_raw.jsonl"
    out_dir = root / "data" / "cleaned" / "storyengine"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "storyengine_cleaned.jsonl"

    rules = """# Cleaning rules (for report)

1. Encoding: UTF-8; invalid bytes replaced.
2. Control characters: removed (except \\n, \\t kept before collapse).
3. Whitespace: consecutive spaces/tabs/newlines collapsed to single space; paragraph breaks preserved as single newline.
4. No change: Markdown, A/B/C option structure, or meta keys.
"""

    (out_dir / "cleaning_rules.txt").write_text(rules, encoding="utf-8")

    count = 0
    with open(raw_path, "r", encoding="utf-8") as fin, open(
        out_path, "w", encoding="utf-8"
    ) as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            cleaned = clean_record(rec)
            fout.write(json.dumps(cleaned, ensure_ascii=False) + "\n")
            count += 1

    print(f"Cleaned {count} records -> {out_path}")


if __name__ == "__main__":
    main()
