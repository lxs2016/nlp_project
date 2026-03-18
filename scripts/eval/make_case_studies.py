from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def _read_choice_match(path: Path) -> dict[tuple[str, str, str, str], dict[str, Any]]:
    # key: (config, trajectory_id, gold_file, step_index)
    import csv

    m: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    with open(path, "r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            key = (
                row.get("config", ""),
                row.get("trajectory_id", ""),
                row.get("gold_file", ""),
                str(row.get("step_index", "")),
            )
            m[key] = row
    return m


def _short(s: str, n: int = 420) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else (s[:n] + "…")


def main() -> None:
    ap = argparse.ArgumentParser(description="Build case studies markdown from eval outputs.")
    ap.add_argument("--run_dir", type=str, required=True, help="outputs/eval/<run_id>")
    ap.add_argument("--choice_match_csv", type=str, default="", help="Optional: choice_match.csv for low-score cases")
    ap.add_argument("--max_cases", type=int, default=12)
    ap.add_argument("--min_best_score", type=float, default=0.55, help="If provided with choice_match_csv, select low-score cases")
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    steps_path = run_dir / "steps.jsonl"
    if not steps_path.exists():
        raise SystemExit(f"Missing: {steps_path}")
    steps = _read_jsonl(steps_path)

    cm_map = _read_choice_match(Path(args.choice_match_csv)) if args.choice_match_csv else {}

    # Prioritize: (1) consistency failed, (2) low choice-match score (if available)
    failed = []
    low_score = []
    for r in steps:
        cfg = str(r.get("config", ""))
        traj = str(r.get("trajectory_id", ""))
        gf = str(r.get("gold_file", ""))
        si = str(r.get("step_index", ""))
        m = r.get("metrics") or {}
        if isinstance(m, dict) and not bool(m.get("consistency_passed", True)):
            failed.append(r)
            continue
        if cm_map:
            key = (cfg, traj, gf, si)
            cm = cm_map.get(key)
            if cm:
                try:
                    score = float(cm.get("best_score") or 0.0)
                except Exception:
                    score = 0.0
                if score < float(args.min_best_score):
                    low_score.append(r)

    picked = failed + low_score
    picked = picked[: int(args.max_cases)]

    lines = []
    lines.append("# StoryWeaver case studies (auto-generated)\n")
    lines.append(f"- Total picked: {len(picked)}\n")
    lines.append("- Priority: consistency failures first, then low choice-matching score (if provided).\n")
    lines.append("\n---\n")

    for idx, r in enumerate(picked, start=1):
        cfg = str(r.get("config", ""))
        traj = str(r.get("trajectory_id", ""))
        si = str(r.get("step_index", ""))
        gold = str(r.get("player_choice_text", ""))
        expected = str(r.get("expected_narration_summary", ""))
        narration = str(r.get("narration", ""))
        choices = r.get("choices") or []
        if not isinstance(choices, list):
            choices = []
        m = r.get("metrics") or {}
        passed = bool(m.get("consistency_passed")) if isinstance(m, dict) else True
        reason = str(m.get("consistency_reason") or "") if isinstance(m, dict) else ""

        cm_score = ""
        cm_best = ""
        if cm_map:
            key = (cfg, traj, str(r.get("gold_file", "")), si)
            cm = cm_map.get(key)
            if cm:
                cm_score = str(cm.get("best_score") or "")
                cm_best = str(cm.get("best_choice") or "")

        lines.append(f"## Case {idx}: {traj} step {si} ({cfg})\n")
        lines.append(f"- **Gold choice**: {gold}\n")
        lines.append(f"- **Expected summary**: {_short(expected)}\n")
        lines.append(f"- **Consistency**: {'PASS' if passed else 'FAIL'}\n")
        if not passed:
            lines.append(f"- **Fail reason**: {reason}\n")
        if cm_score:
            lines.append(f"- **Choice-match best_score**: {cm_score}\n")
            lines.append(f"- **Choice-match best_choice**: {cm_best}\n")
        lines.append("\n### System choices\n")
        for c in choices[:8]:
            lines.append(f"- {c}\n")
        lines.append("\n### System narration (truncated)\n")
        lines.append("```\n")
        lines.append(_short(narration, n=900) + "\n")
        lines.append("```\n")
        lines.append("\n---\n")

    out_path = run_dir / "case_studies.md"
    out_path.write_text("".join(lines), encoding="utf-8")
    print(f"[case-studies] wrote: {out_path}")


if __name__ == "__main__":
    main()

