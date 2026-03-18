from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _norm(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    # remove common punctuation (keep CJK/letters/digits/spaces)
    s = re.sub(r"[^\w\u4e00-\u9fff ]+", "", s)
    return s.strip()


def _strict_hit(gold: str, choices: Iterable[str]) -> bool:
    g = _norm(gold)
    if not g:
        return False
    return any(_norm(c) == g for c in choices)


def _seq_ratio(a: str, b: str) -> float:
    # lightweight fallback; no extra deps
    from difflib import SequenceMatcher

    a2, b2 = _norm(a), _norm(b)
    if not a2 or not b2:
        return 0.0
    return float(SequenceMatcher(None, a2, b2).ratio())


@dataclass(frozen=True)
class ChoiceMatchResult:
    best_choice: str
    best_score: float
    hit_at_k: bool


class ChoiceMatcher:
    def __init__(self) -> None:
        self._encoder = None

    def _get_encoder(self):
        if self._encoder is not None:
            return self._encoder
        import os
        if os.environ.get("STORYWEAVER_DISABLE_SBERT", "").strip() in {"1", "true", "yes"}:
            self._encoder = False
            return self._encoder
        try:
            from sentence_transformers import SentenceTransformer

            self._encoder = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception:
            self._encoder = False
        return self._encoder

    def _embed_scores(self, gold: str, choices: list[str]) -> list[float]:
        enc = self._get_encoder()
        if enc is False:
            return []
        # cosine similarity
        from numpy import dot
        from numpy.linalg import norm

        texts = [gold] + choices
        vecs = enc.encode(texts, convert_to_numpy=True)
        g = vecs[0]
        out: list[float] = []
        for v in vecs[1:]:
            out.append(float(dot(g, v) / (norm(g) * norm(v) + 1e-9)))
        return out

    def match(self, gold: str, choices: list[str], *, k: int, threshold: float) -> ChoiceMatchResult:
        if not choices:
            return ChoiceMatchResult(best_choice="", best_score=0.0, hit_at_k=False)

        # Prefer embeddings if available; otherwise fallback to fuzzy ratio
        scores = self._embed_scores(gold, choices)
        if scores:
            best_i = max(range(len(scores)), key=lambda i: scores[i])
            ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
            hit = any(scores[i] >= threshold for i in ranked[: max(1, k)])
            return ChoiceMatchResult(best_choice=choices[best_i], best_score=float(scores[best_i]), hit_at_k=hit)

        fuzzy = [_seq_ratio(gold, c) for c in choices]
        best_i = max(range(len(fuzzy)), key=lambda i: fuzzy[i])
        ranked = sorted(range(len(fuzzy)), key=lambda i: fuzzy[i], reverse=True)
        hit = any(fuzzy[i] >= threshold for i in ranked[: max(1, k)])
        return ChoiceMatchResult(best_choice=choices[best_i], best_score=float(fuzzy[best_i]), hit_at_k=hit)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description="Score choice matching for eval steps.jsonl.")
    ap.add_argument("--input", type=str, required=True, help="Path to steps.jsonl")
    ap.add_argument("--output", type=str, default="", help="Output CSV; default next to input as choice_match.csv")
    ap.add_argument("--k", type=int, default=3, help="hit@k")
    ap.add_argument("--threshold", type=float, default=0.65, help="Embedding/fuzzy threshold for hit@k")
    args = ap.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output) if args.output else (in_path.parent / "choice_match.csv")

    rows = _read_jsonl(in_path)
    matcher = ChoiceMatcher()

    out_rows: list[dict[str, Any]] = []
    hit1 = 0
    hitk = 0
    n = 0

    for r in rows:
        gold = str(r.get("player_choice_text") or "")
        choices = r.get("choices") or []
        if not isinstance(choices, list):
            choices = []
        choices = [str(c) for c in choices]

        strict = _strict_hit(gold, choices)
        m = matcher.match(gold, choices, k=int(args.k), threshold=float(args.threshold))

        n += 1
        hit1 += 1 if strict else 0
        hitk += 1 if m.hit_at_k else 0

        out_rows.append(
            {
                "config": r.get("config", ""),
                "trajectory_id": r.get("trajectory_id", ""),
                "gold_file": r.get("gold_file", ""),
                "step_index": r.get("step_index", ""),
                "player_choice_text": gold,
                "strict_hit_at_1": int(strict),
                "best_choice": m.best_choice,
                "best_score": f"{m.best_score:.4f}",
                "hit_at_k": int(m.hit_at_k),
            }
        )

    _write_csv(out_path, out_rows)

    agg = {
        "n": n,
        "strict_hit_at_1_rate": (hit1 / n) if n else 0.0,
        "hit_at_k_rate": (hitk / n) if n else 0.0,
        "k": int(args.k),
        "threshold": float(args.threshold),
    }
    with open(out_path.with_suffix(".summary.json"), "w", encoding="utf-8") as f:
        json.dump(agg, f, ensure_ascii=False, indent=2)

    print(f"[choice-match] wrote: {out_path}")
    print(f"[choice-match] wrote: {out_path.with_suffix('.summary.json')}")


if __name__ == "__main__":
    main()

