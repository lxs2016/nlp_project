from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _read_csv(path: Path) -> list[dict[str, str]]:
    with open(path, "r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        return [dict(row) for row in r]


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def _percentile(xs: list[float], p: float) -> float:
    if not xs:
        return 0.0
    xs2 = sorted(xs)
    idx = int(p * (len(xs2) - 1))
    return float(xs2[idx])


def _mean(xs: list[float]) -> float:
    return float(sum(xs) / len(xs)) if xs else 0.0


def _safe_float(x: Any) -> float:
    try:
        return float(x)
    except Exception:
        return 0.0


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description="Build report-ready tables from eval outputs.")
    ap.add_argument("--run_dir", type=str, required=True, help="outputs/eval/<run_id>")
    ap.add_argument("--choice_match_csv", type=str, default="", help="Optional: choice_match.csv")
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    steps_path = run_dir / "steps.jsonl"
    summary_path = run_dir / "summary.csv"
    if not steps_path.exists() or not summary_path.exists():
        raise SystemExit(f"Missing steps.jsonl or summary.csv in {run_dir}")

    steps = _read_jsonl(steps_path)
    summary_rows = _read_csv(summary_path)

    # Latency breakdown and coherence aggregates from steps
    by_cfg_lat: dict[str, list[float]] = defaultdict(list)
    by_cfg_generate: dict[str, list[float]] = defaultdict(list)
    by_cfg_consistency: dict[str, list[float]] = defaultdict(list)
    by_cfg_pass: dict[str, list[int]] = defaultdict(list)
    by_cfg_attempts: dict[str, list[int]] = defaultdict(list)
    reason_counter: dict[str, Counter[str]] = defaultdict(Counter)

    for r in steps:
        cfg = str(r.get("config") or "full")
        m = r.get("metrics") or {}
        timing = (m.get("timing_ms") or {}) if isinstance(m, dict) else {}
        by_cfg_lat[cfg].append(_safe_float(timing.get("total")))
        by_cfg_generate[cfg].append(_safe_float(timing.get("generate_total")))
        by_cfg_consistency[cfg].append(_safe_float(timing.get("consistency_total")))
        by_cfg_pass[cfg].append(1 if bool(m.get("consistency_passed")) else 0)
        by_cfg_attempts[cfg].append(int(m.get("attempts") or 0))
        reason = str(m.get("consistency_reason") or "").strip()
        if reason:
            reason_counter[cfg][reason] += 1

    latency_table: list[dict[str, Any]] = []
    for cfg, xs in sorted(by_cfg_lat.items()):
        latency_table.append(
            {
                "config": cfg,
                "n_steps": len(xs),
                "lat_mean_ms": f"{_mean(xs):.2f}",
                "lat_p50_ms": f"{_percentile(xs, 0.50):.2f}",
                "lat_p95_ms": f"{_percentile(xs, 0.95):.2f}",
                "gen_mean_ms": f"{_mean(by_cfg_generate.get(cfg, [])):.2f}",
                "consistency_mean_ms": f"{_mean(by_cfg_consistency.get(cfg, [])):.2f}",
                "attempts_mean": f"{_mean([float(a) for a in by_cfg_attempts.get(cfg, [])]):.2f}",
                "consistency_pass_rate": f"{(_mean([float(x) for x in by_cfg_pass.get(cfg, [])]) if by_cfg_pass.get(cfg) else 0.0):.3f}",
            }
        )

    _write_csv(run_dir / "table_latency_and_consistency.csv", latency_table)

    # Reasons
    reasons_out = {
        cfg: dict(cnt.most_common())
        for cfg, cnt in sorted(reason_counter.items(), key=lambda kv: kv[0])
    }
    with open(run_dir / "consistency_reasons.json", "w", encoding="utf-8") as f:
        json.dump(reasons_out, f, ensure_ascii=False, indent=2)

    # Optionally merge choice matching aggregates
    if args.choice_match_csv:
        cm_path = Path(args.choice_match_csv)
        cm = _read_csv(cm_path)
        by_cfg = defaultdict(lambda: {"n": 0, "hit1": 0, "hitk": 0, "best_score_sum": 0.0})
        for r in cm:
            cfg = r.get("config", "full")
            by_cfg[cfg]["n"] += 1
            by_cfg[cfg]["hit1"] += int(r.get("strict_hit_at_1") or 0)
            by_cfg[cfg]["hitk"] += int(r.get("hit_at_k") or 0)
            by_cfg[cfg]["best_score_sum"] += _safe_float(r.get("best_score"))
        out = []
        for cfg, agg in sorted(by_cfg.items()):
            n = agg["n"] or 1
            out.append(
                {
                    "config": cfg,
                    "n_steps": agg["n"],
                    "strict_hit_at_1_rate": f"{agg['hit1'] / n:.3f}",
                    "hit_at_k_rate": f"{agg['hitk'] / n:.3f}",
                    "best_score_mean": f"{agg['best_score_sum'] / n:.3f}",
                }
            )
        _write_csv(run_dir / "table_choice_matching.csv", out)

    # Also write a compact markdown snippet for report copy/paste
    md_lines = []
    md_lines.append("## Performance evaluation summary (auto-generated)\n")
    md_lines.append("### Latency & consistency\n")
    md_lines.append("See `table_latency_and_consistency.csv`.\n")
    if args.choice_match_csv:
        md_lines.append("### Choice matching\n")
        md_lines.append("See `table_choice_matching.csv`.\n")
    md_lines.append("### Consistency failure reasons\n")
    md_lines.append("See `consistency_reasons.json`.\n")
    (run_dir / "REPORT_SNIPPET.md").write_text("\n".join(md_lines), encoding="utf-8")

    print(f"[report] wrote: {run_dir / 'table_latency_and_consistency.csv'}")
    print(f"[report] wrote: {run_dir / 'consistency_reasons.json'}")
    if args.choice_match_csv:
        print(f"[report] wrote: {run_dir / 'table_choice_matching.csv'}")
    print(f"[report] wrote: {run_dir / 'REPORT_SNIPPET.md'}")


if __name__ == "__main__":
    main()

