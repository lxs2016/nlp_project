---
name: performance_evaluation_性能评估实现方案
overview: 为 StoryWeaver 增加可重复的离线评测流水线：自动回放金标轨迹、采集延迟与一致性违规、计算选择匹配/相似度，并输出报告可直接引用的 CSV/JSON 与图表素材。
todos:
  - id: scan-current-engine-observability
    content: 梳理 `game/engine.py` 当前可返回的信息，设计最小侵入的 metrics 返回方式（不影响 Gradio UI）
    status: completed
  - id: implement-offline-eval-runner
    content: 新增 `scripts/eval/run_eval.py`：回放 gold trajectories、采集逐步记录（JSONL）与汇总（CSV）
    status: completed
  - id: choice-matching-metrics
    content: 实现 choice matching：严格匹配 + 语义相似度（优先 sentence-transformers，fallback fuzzy）并输出 hit@k
    status: completed
  - id: latency-breakdown
    content: 在评测 wrapper 或引擎中记录分段耗时，汇总 P50/P95 等统计
    status: completed
  - id: coherence-metrics
    content: 统计一致性违规率、原因分布、重试次数/降级次数；可选支持 LLM-as-judge 抽样评分
    status: completed
  - id: ablation-configs
    content: 实现 Full/NoRetrieve/NoConsistency/RuleOnlyChoices 的开关，并在评测脚本中跑全矩阵
    status: completed
  - id: artifacts-for-report
    content: 生成报告可引用的 summary 表、case study markdown，以及 user study 问卷模板与 CSV schema
    status: completed
isProject: false
---

## 目标与范围

- **目标**：按文档要求落地 4 类指标：剧情连贯性、生成响应时间、玩家选择匹配准确率、沉浸感/满意度，并支持**消融对比**（关闭检索/关闭一致性检查/规则分支）
- **范围**：提供可复现实验脚本（离线跑）、结果产物（CSV/JSON）、以及报告/展示用的最小素材（摘要表 + 失败案例片段）

## 现有实现可复用点（对齐代码结构）

- **单步推理入口**：`game/engine.py` 的 `step(session_id, user_input) -> (narration, choices, state_summary, error_message)`
- **一致性检查**：`models/consistency.py` 的 `check(state, narration, state_updates)` 返回 `(passed, reason)`，可用于统计“违规率/原因分布”
- **检索模块**：`models/retriever.py` 的 `retrieve(...)`；可通过开关实现“无检索”消融
- **规划/生成**：`models/planner.py` + `models/generator.py`；延迟主要集中在 `generator._call_llm()`
- **金标轨迹**：`data/gold_trajectories/gold_explore.json`、`data/gold_trajectories/gold_negotiate.json`
- **世界观**：`data/world_bible/world_main.yaml`（由 `game/config.py` 的 `load_world_bible()` 读取）

## 评测设计（实验矩阵）

- **系统配置（4 组）**：
  - **Full**：当前默认（检索 + 一致性检查）
  - **Ablation_NoRetrieve**：检索返回空（或 `k=0`）
  - **Ablation_NoConsistency**：跳过 `consistency_check`（永远通过/不重试）
  - **Ablation_RuleOnlyChoices**（可选）：不依赖生成器给 choices，固定使用 `planner.suggested_choices`（用于对比“生成分支质量”）

## 指标落地口径与实现方式

### 1) 生成响应时间（Latency）

- **采集点**：围绕 `game/engine.step()` 的端到端计时
- **输出**：每回合记录 `t_total_ms`，并细分（建议）
  - `t_intent_ms`、`t_retrieve_ms`、`t_plan_ms`、`t_generate_ms`、`t_consistency_ms`、`attempts`（重试次数）
- **统计**：按配置、按轨迹，计算 **P50/P95/Max**；区分“首回合（冷启动）vs 后续回合”

### 2) 剧情连贯性（Coherence / Consistency）

- **自动指标（必做）**：
  - **一致性违规率**：`passed=False` 的回合占比
  - **违规原因分布**：`reason` 计数（例如：禁忌规则、未知地点等）
  - **修复成本**：平均重试次数/因不一致导致的降级（例如 choices 截断）比例
- **半自动指标（可选，给报告加分）**：LLM-as-judge 评分 1–5
  - 输入：`WorldBible摘要 + 最近N回合叙述 + 本回合叙述 + 期望摘要`（来自 gold）
  - 输出：`score(1-5) + violated_rule_type + rationale`
  - 产物：抽样 20 回合即可（成本可控）

### 3) 玩家选择匹配准确率（Choice matching）

- **问题**：金标是“玩家想做什么”（`player_choice_text`），系统是“给出 choices 并接收 user_input”
- **实现口径（推荐两档）**：
  - **Top-1 命中率（严格）**：金标 choice 文本在系统 `choices[]` 中出现（字符串归一化后精确匹配）
  - **Top-k 语义命中率（实用）**：金标与系统 `choices[]` 做相似度（embedding 或 fuzzy），若最高分 ≥ 阈值则命中
    - embedding：优先复用 `sentence-transformers`（项目已用在检索）
    - fuzzy：作为无依赖 fallback（如 token Jaccard/Levenshtein）
- **输出**：每步记录 `best_choice`, `best_score`, `hit@1`, `hit@k`

### 4) 沉浸感/满意度（User study）

- **最小用户测试**：5–10 人，15–20 分钟试玩
- **问卷**：Likert 1–5（沉浸感、连贯性、可控感、响应速度、总体满意）+ 2 个开放问题（最喜欢/最困惑）
- **产物**：`data/eval/user_study_responses.csv` + 报告中的均值/方差 + 3 条典型评论（匿名）

## 需要新增/调整的代码与文件（指向明确路径）

### A) 评测脚本（离线可重复跑）

- 新增：`scripts/eval/run_eval.py`
  - 读取 `data/gold_trajectories/*.json`
  - 按配置矩阵回放：每个 step 将 `player_choice_text` 作为 `user_input` 喂给 `game.engine.step()`
  - 采集：延迟、choices、error_message、一致性结果（需要 engine 额外返回/或在脚本侧做 wrapper）
  - 写出：`outputs/eval/<run_id>/*.jsonl`（逐步记录）与 `summary.csv`
- 新增：`scripts/eval/score_choice_match.py`
  - 对 `run_eval` 输出的逐步记录计算 hit@1/hit@k 与平均相似度
- 新增：`scripts/eval/report_tables.py`
  - 汇总出报告可直接引用的表：指标均值、P50/P95、违规率、命中率

### B) 引擎侧最小化“可观测性”改造（用于分解延迟/记录重试）

- 调整：`game/engine.py`
  - 为评测暴露一个 **可选** 的结构化返回（不破坏 UI）：例如新增 `step_with_metrics(...) -> (result, metrics)` 或让 `step()` 支持 `return_metrics: bool=False`
  - metrics 字段：`attempts`, `passed`, `reason`, `t_*_ms`
- 调整：`models/generator.py`
  - 记录 `model_name`, `base_url`（来自环境变量），以及 `_call_llm` 的耗时，写入 metrics

### C) 配置与产物目录

- 新增：`outputs/eval/README.md`（说明每个文件含义、如何复现实验）
- 新增：`data/eval/`（用户问卷结果、LLM judge 抽样结果）

## 运行方式（计划写到 README/报告里）

- 离线评测（示例）：
  - `python -m scripts.eval.run_eval --gold_dir data/gold_trajectories --configs full,no_retrieve,no_consistency --runs 3 --seed 42`
  - `python -m scripts.eval.score_choice_match --input outputs/eval/<run_id>/steps.jsonl`
  - `python -m scripts.eval.report_tables --input outputs/eval/<run_id>/summary.csv`

## 验收标准（你交报告时可直接写）

- **可复现**：同一 seed + 同一配置重复运行，输出文件结构一致；主要汇总指标波动在可解释范围
- **覆盖指标**：4 类指标都有定义、脚本与结果文件；报告里至少 1 张汇总表 + 1 个失败案例分析
- **消融有效**：至少 2 个消融配置能体现指标差异（例如 NoConsistency 违规率上升、NoRetrieve 命中率或连贯性下降）

## 失败案例与可视化（建议最低限度实现）

- 从 `steps.jsonl` 自动挑选：
  - `passed=False` 的回合
  - 或 choice matching 低分回合
- 输出到 `outputs/eval/<run_id>/case_studies.md`：包含输入、系统 choices、选择、叙述片段、违规原因/评分

