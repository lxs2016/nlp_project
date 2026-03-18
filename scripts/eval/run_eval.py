from __future__ import annotations

import argparse
import csv
import json
import os
import random
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any

from game.engine import StepOptions, reset_session, step_with_metrics


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GOLD_DIR = PROJECT_ROOT / "data" / "gold_trajectories"
DEFAULT_OUT_DIR = PROJECT_ROOT / "outputs" / "eval"


def _now_run_id() -> str:
    ts = time.strftime("%Y%m%d-%H%M%S")
    return f"{ts}_{uuid.uuid4().hex[:8]}"


def _read_json(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _iter_gold_files(gold_dir: Path) -> list[Path]:
    files = sorted(p for p in gold_dir.glob("*.json") if p.is_file())
    return files


def _parse_configs(configs_csv: str) -> list[str]:
    out = []
    for part in (configs_csv or "").split(","):
        name = part.strip()
        if name:
            out.append(name)
    return out or ["full"]


def _options_for_config(name: str) -> StepOptions:
    n = (name or "").strip().lower()
    if n in {"full", "default"}:
        return StepOptions()
    if n in {"no_retrieve", "noretrieve", "ablation_noretrieve"}:
        return StepOptions(disable_retrieve=True)
    if n in {"no_consistency", "noconsistency", "ablation_noconsistency"}:
        return StepOptions(disable_consistency=True)
    if n in {"rule_only_choices", "ruleonlychoices", "ablation_ruleonlychoices"}:
        return StepOptions(rule_only_choices=True)
    raise ValueError(f"Unknown config: {name}")


def _ensure_dirs(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _write_summary_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def run_once(
    *,
    gold_file: Path,
    config_name: str,
    options: StepOptions,
    seed: int,
    session_id: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    gold = _read_json(gold_file)
    steps = gold.get("steps") or []
    if not isinstance(steps, list):
        raise ValueError(f"Invalid gold file (steps not list): {gold_file}")

    reset_session(session_id)
    random.seed(seed)

    step_rows: list[dict[str, Any]] = []
    n_pass = 0
    n_steps = 0
    total_ms = 0.0
    p95_bucket: list[float] = []

    for i, s in enumerate(steps, start=1):
        user_input = str(s.get("player_choice_text") or "").strip() or "继续"
        expected = str(s.get("expected_narration_summary") or "").strip()

        (narration, choices, state_summary, error_message), metrics = step_with_metrics(
            session_id,
            user_input,
            options=options,
        )

        timing = (metrics.get("timing_ms") or {}) if isinstance(metrics, dict) else {}
        t_total = float(timing.get("total") or 0.0)

        passed = bool(metrics.get("consistency_passed"))
        reason = str(metrics.get("consistency_reason") or "")

        row = {
            "run_seed": seed,
            "config": config_name,
            "gold_file": gold_file.name,
            "trajectory_id": gold.get("trajectory_id") or gold_file.stem,
            "step_index": i,
            "player_choice_text": user_input,
            "expected_narration_summary": expected,
            "narration": narration,
            "choices": choices,
            "state_summary": state_summary,
            "error_message": error_message,
            "metrics": metrics,
        }
        step_rows.append(row)

        n_steps += 1
        total_ms += t_total
        p95_bucket.append(t_total)
        if passed:
            n_pass += 1

    p95_bucket_sorted = sorted(p95_bucket)
    p50 = p95_bucket_sorted[int(0.50 * (len(p95_bucket_sorted) - 1))] if p95_bucket_sorted else 0.0
    p95 = p95_bucket_sorted[int(0.95 * (len(p95_bucket_sorted) - 1))] if p95_bucket_sorted else 0.0
    max_ms = max(p95_bucket_sorted) if p95_bucket_sorted else 0.0

    summary = {
        "run_seed": seed,
        "config": config_name,
        "gold_file": gold_file.name,
        "trajectory_id": gold.get("trajectory_id") or gold_file.stem,
        "n_steps": n_steps,
        "consistency_pass_rate": (n_pass / n_steps) if n_steps else 0.0,
        "latency_mean_ms": (total_ms / n_steps) if n_steps else 0.0,
        "latency_p50_ms": p50,
        "latency_p95_ms": p95,
        "latency_max_ms": max_ms,
        "options": json.dumps(asdict(options), ensure_ascii=False),
    }
    return step_rows, summary


def main() -> None:
    ap = argparse.ArgumentParser(description="Offline evaluation runner for StoryWeaver.")
    ap.add_argument("--gold_dir", type=str, default=str(DEFAULT_GOLD_DIR))
    ap.add_argument("--configs", type=str, default="full,no_retrieve,no_consistency,rule_only_choices")
    ap.add_argument("--runs", type=int, default=1, help="Number of repeated runs per config per gold file.")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out_dir", type=str, default=str(DEFAULT_OUT_DIR))
    ap.add_argument("--run_id", type=str, default="", help="Optional run id; default auto-generated.")
    args = ap.parse_args()

    gold_dir = Path(args.gold_dir)
    out_root = Path(args.out_dir)
    run_id = (args.run_id or "").strip() or _now_run_id()

    configs = _parse_configs(args.configs)
    gold_files = _iter_gold_files(gold_dir)
    if not gold_files:
        raise SystemExit(f"No gold trajectories found in: {gold_dir}")

    run_dir = out_root / run_id
    _ensure_dirs(run_dir)

    # Make eval deterministic for non-LLM components
    os.environ.setdefault("PYTHONHASHSEED", str(args.seed))

    steps_all: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []

    for gold_file in gold_files:
        for cfg_name in configs:
            options = _options_for_config(cfg_name)
            for r in range(int(args.runs)):
                run_seed = int(args.seed) + r
                session_id = f"eval_{run_id}_{gold_file.stem}_{cfg_name}_{run_seed}"
                step_rows, summary = run_once(
                    gold_file=gold_file,
                    config_name=cfg_name,
                    options=options,
                    seed=run_seed,
                    session_id=session_id,
                )
                steps_all.extend(step_rows)
                summary_rows.append(summary)

    _write_jsonl(run_dir / "steps.jsonl", steps_all)
    _write_summary_csv(run_dir / "summary.csv", summary_rows)

    print(f"[eval] wrote: {run_dir / 'steps.jsonl'}")
    print(f"[eval] wrote: {run_dir / 'summary.csv'}")


if __name__ == "__main__":
    main()

