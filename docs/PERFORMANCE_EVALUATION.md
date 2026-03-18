## Performance evaluation: how to run

This doc describes the **end-to-end commands** to run StoryWeaver performance evaluation and generate report-ready artifacts.

### Inputs / outputs

- **Gold trajectories (inputs)**: `data/gold_trajectories/*.json`
- **Evaluation outputs**: `outputs/eval/<run_id>/`
  - `steps.jsonl`: per-step records (gold choice, system narration/choices, metrics)
  - `summary.csv`: per-trajectory run summaries
  - `choice_match.csv` + `choice_match.summary.json`: choice matching results
  - `table_latency_and_consistency.csv`: report-ready latency/coherence table
  - `table_choice_matching.csv`: report-ready choice matching table
  - `consistency_reasons.json`: consistency failure reasons distribution
  - `case_studies.md`: picked failures / low-score examples

### Common environment switches

- **Disable sentence-transformers download** (use retriever fallback; choice-matching uses fuzzy):
  - `STORYWEAVER_DISABLE_SBERT=1`
- **Force generator fallback** (no network calls; used for pipeline smoke test):
  - `STORYWEAVER_FORCE_FALLBACK=1`

### 1) Offline reproducible run (no LLM calls)

Use this when you want to validate the **evaluation pipeline** (I/O, metrics, tables) without depending on network.

```bash
RUN_ID=offline_eval_$(date +%Y%m%d-%H%M%S)

STORYWEAVER_DISABLE_SBERT=1 STORYWEAVER_FORCE_FALLBACK=1 \
python -m scripts.eval.run_eval --runs 1 --seed 42 --run_id "$RUN_ID"

STORYWEAVER_DISABLE_SBERT=1 \
python -m scripts.eval.score_choice_match --input "outputs/eval/$RUN_ID/steps.jsonl"

python -m scripts.eval.report_tables \
  --run_dir "outputs/eval/$RUN_ID" \
  --choice_match_csv "outputs/eval/$RUN_ID/choice_match.csv"

python -m scripts.eval.make_case_studies \
  --run_dir "outputs/eval/$RUN_ID" \
  --choice_match_csv "outputs/eval/$RUN_ID/choice_match.csv"
```

### 2) Real LLM run (uses `.env` / environment keys)

Prerequisites:
- `.env` contains either `OPENAI_API_KEY` or `OPENROUTER_API_KEY` (and optional `*_API_BASE`, `*_MODEL`)
- Network can reach the configured endpoint

```bash
RUN_ID=real_eval_$(date +%Y%m%d-%H%M%S)

# Keep SBERT disabled unless you have the model cached locally.
STORYWEAVER_DISABLE_SBERT=1 \
python -m scripts.eval.run_eval --runs 1 --seed 42 --run_id "$RUN_ID"

STORYWEAVER_DISABLE_SBERT=1 \
python -m scripts.eval.score_choice_match --input "outputs/eval/$RUN_ID/steps.jsonl"

python -m scripts.eval.report_tables \
  --run_dir "outputs/eval/$RUN_ID" \
  --choice_match_csv "outputs/eval/$RUN_ID/choice_match.csv"

python -m scripts.eval.make_case_studies \
  --run_dir "outputs/eval/$RUN_ID" \
  --choice_match_csv "outputs/eval/$RUN_ID/choice_match.csv"
```

### 3) Configuration matrix / ablations

`run_eval` supports multiple configs (comma-separated):
- `full`: default pipeline (retrieve + consistency)
- `no_retrieve`: disable retriever
- `no_consistency`: skip consistency check (no retry)
- `rule_only_choices`: force choices from planner suggestions

Example:

```bash
RUN_ID=ablation_eval_$(date +%Y%m%d-%H%M%S)

STORYWEAVER_DISABLE_SBERT=1 \
python -m scripts.eval.run_eval \
  --runs 1 \
  --seed 42 \
  --run_id "$RUN_ID" \
  --configs "full,no_retrieve,no_consistency,rule_only_choices"
```

### Troubleshooting

- **It hangs on first run**:
  - Likely `sentence-transformers` model download. Use `STORYWEAVER_DISABLE_SBERT=1`.
- **You see `Connection error` and it falls back**:
  - The environment cannot reach your LLM endpoint. Verify `*_API_BASE` and network availability.
- **Choice matching is always 0 in offline mode**:
  - Expected: fallback generator outputs generic choices that do not align with gold steps.

