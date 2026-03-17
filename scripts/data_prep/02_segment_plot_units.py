#!/usr/bin/env python3
"""
Step 2.4: Segment cleaned StoryEngine into plot units (one unit per record).
Outputs: data/plot_units/storyengine_units.jsonl
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


# Match "**A.** text" or "A) text" or "A. text" (optionally bold)
CHOICE_PATTERNS = [
    re.compile(r"\*\*([A-C])[\.\)]\*\*\s*([^*\n]+?)(?=\*\*[A-C]|\Z)", re.DOTALL),
    re.compile(r"([A-C])[\.\)]\s*([^\n]+?)(?=[A-C][\.\)]|\n\n|\Z)", re.DOTALL),
    re.compile(r"([A-C])\.\s+([^\n]+?)(?=\n\s*[A-C]\.|\Z)", re.DOTALL),
]


def parse_choices(narrative_text: str) -> tuple[list[str], bool]:
    """Extract choice labels (e.g. A/B/C text). Returns (list of choice texts, parsed_ok)."""
    if not narrative_text or not isinstance(narrative_text, str):
        return [], False
    for pat in CHOICE_PATTERNS:
        matches = pat.findall(narrative_text)
        if matches:
            if isinstance(matches[0], tuple):
                choices = [m[1].strip() for m in matches]
            else:
                choices = [m.strip() for m in matches]
            if choices:
                return choices[:6], True
    return [], False


def extract_system_summary(system_content: str, max_chars: int = 200) -> str:
    """First N chars of system prompt as world_context_summary."""
    if not system_content:
        return ""
    s = " ".join(system_content.split())
    return s[:max_chars] + ("..." if len(s) > max_chars else "")


def main() -> None:
    root = project_root()
    cleaned_path = root / "data" / "cleaned" / "storyengine" / "storyengine_cleaned.jsonl"
    out_dir = root / "data" / "plot_units"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "storyengine_units.jsonl"

    count = 0
    with open(cleaned_path, "r", encoding="utf-8") as fin, open(
        out_path, "w", encoding="utf-8"
    ) as fout:
        for i, line in enumerate(fin):
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            messages = rec.get("messages") or []
            meta = rec.get("meta") or {}

            narrative_text = ""
            player_input = ""
            system_content = ""

            for m in messages:
                role = (m.get("role") or "").strip().lower()
                content = m.get("content") or ""
                if role == "assistant":
                    narrative_text = content
                elif role == "user":
                    player_input = content
                elif role == "system":
                    system_content = content

            available_choices, choices_parsed = parse_choices(narrative_text)

            unit: dict[str, Any] = {
                "plot_unit_id": f"se_{i:04d}",
                "narrative_text": narrative_text,
                "player_input": player_input,
                "available_choices": available_choices,
                "choices_parsed": choices_parsed,
                "next_unit_id": None,
                "source": "storyengine",
                "meta": meta,
                "world_context_summary": extract_system_summary(system_content),
            }
            fout.write(json.dumps(unit, ensure_ascii=False) + "\n")
            count += 1

    print(f"Wrote {count} plot units -> {out_path}")


if __name__ == "__main__":
    main()
