# Data Preparation 报告用文档（COMP5423 Group Project）

以下内容可直接或略作改写后放入项目报告的 **Data preparation** 小节，包含数据来源、步骤、规模与字段说明。

---

## 1. 任务与目标

根据项目要求，数据准备阶段需：收集并组织用于训练与测试的**文本冒险游戏脚本、分支叙事语料、对话数据集、剧情一致性标注样本**；通过**清洗文本噪声、划分剧情单元、标注叙事逻辑**保证一致性与质量，以支撑用户意图识别、上下文感知生成与剧情一致性检测等后续模块。

---

## 2. 数据源选取

本组采用**单一主数据源**以降低实现复杂度并保证可复现性：

- **名称**：StoryEngine Interactive Fiction Dataset  
- **来源**：Hugging Face，`SatorTenet/storyengine-dataset`  
- **规模**：约 3,140 条交互式叙事对话轮次  
- **许可**：Apache 2.0  

**选取理由**：  
每条样本为「系统状态（system）→ 玩家选择（user）→ 叙述续写（assistant）」结构，与 StoryWeaver 的「GameState + 玩家输入 + 动态生成」流水线一致；且每条带有 `meta`（type, genre, polti），便于意图映射与世界观约束。数据为 JSONL 格式，便于批量清洗与剧情单元划分。

---

## 3. 数据准备步骤

### 3.1 获取与落盘

使用 Hugging Face `datasets` 库加载 `SatorTenet/storyengine-dataset`，将每条样本保存为一行 JSON，写入 `data/raw/storyengine/storyengine_raw.jsonl`，并统计 `meta.type` 分布，记录于 `meta_stats.json` 与 README。

### 3.2 清洗文本噪声

- **对象**：每条记录的 `messages[*].content` 及 `meta` 中的字符串。  
- **规则**：统一 UTF-8 编码、去除控制字符、将连续空白规范为单空格并保留段落换行；不修改 Markdown 与 A/B/C 选项结构。  
- **产出**：`data/cleaned/storyengine/storyengine_cleaned.jsonl` 及 `cleaning_rules.txt`（供附录引用）。

### 3.3 剧情单元划分（Segmenting plot units）

- **定义**：一条 StoryEngine 样本对应一个剧情单元。  
- **字段**：plot_unit_id, narrative_text（assistant 内容）, player_input（user 内容）, available_choices（从叙述中解析的 A/B/C 选项）, next_unit_id（置 null）, source（"storyengine"）, meta, world_context_summary（从 system 截取前 200 字）。  
- **选项解析**：通过正则匹配「**A.** … **B.** … **C.**」或「A) … B) … C)」等形式提取选项列表；解析失败则 available_choices 为空并标记 choices_parsed=false。  
- **产出**：`data/plot_units/storyengine_units.jsonl`，行数与清洗后数据一致。

### 3.4 意图标注（Labeling narrative logic — intent）

- **意图类别**：与 `meta.type` 一一映射——scene_continuation→continue, genre_opening→start, fail_forward→fail_forward, command_response→meta_help, session_end→end, init_sequence→init。  
- **格式**：每条含 input_text（player_input）, intent_label, plot_unit_id, source。  
- **划分**：按 80% / 10% / 10% 随机划分 train/val/test（固定随机种子 42），输出 `intent_train.jsonl`, `intent_val.jsonl`, `intent_test.jsonl`。

### 3.5 剧情一致性标注样本

- **目的**：为一致性检测模块提供正负样本。  
- **正样本**：取连续两条剧情单元的 narrative_text 作为 context 与 current_narrative，标签 consistent=1。  
- **负样本**：随机配对非连续单元，标签 consistent=0。  
- **产出**：`data/annotations/consistency_annotations.jsonl`，正负样本数量大致相当。

### 3.6 WorldBible 与金标轨迹

- **WorldBible**：手写单一世界观 YAML（`data/world_bible/world_main.yaml`），包含 setting, characters（3–5 人）, locations（5–8 处）, rules_forbidden（3–5 条）, main_conflict, key_items，与演示场景「村庄—洞穴—长老」一致。  
- **金标轨迹**：手写 2 条从开局到结局的玩家选择序列（`gold_negotiate.json`, `gold_explore.json`），每条 5 步，每步含 player_choice_text 与 expected_narration_summary，用于评测选择匹配与剧情走向。

---

## 4. 数据规模与划分（实际运行结果）

| 数据 | 规模 | 说明 |
|------|------|------|
| 原始/清洗/剧情单元 | 3,140 条 | 与 StoryEngine 一致 |
| 意图 train | 2,512 | 80% |
| 意图 val | 314 | 10% |
| 意图 test | 314 | 10% |
| 一致性标注 | 120 条 | 正负各 60 |
| 金标轨迹 | 2 条 | 各 5 步 |

---

## 5. 产出清单（验收用）

- `data/raw/storyengine/storyengine_raw.jsonl` — 原始 JSONL  
- `data/raw/storyengine/meta_stats.json`, README.md — 来源与 type 分布  
- `data/cleaned/storyengine/storyengine_cleaned.jsonl`, cleaning_rules.txt — 清洗后数据与规则  
- `data/plot_units/storyengine_units.jsonl` — 剧情单元表  
- `data/annotations/intent_train.jsonl`, intent_val.jsonl, intent_test.jsonl — 意图标注及划分  
- `data/annotations/consistency_annotations.jsonl` — 一致性标注  
- `data/world_bible/world_main.yaml`, schema 说明 — 世界观设定  
- `data/gold_trajectories/gold_*.json` — 金标轨迹  
- `data/README.md` — 数据说明与复现步骤  

脚本位于 `scripts/data_prep/`：`00_fetch_raw.py`, `01_clean.py`, `02_segment_plot_units.py`, `03_build_intent_annotations.py`, `04_build_consistency_annotations.py`。

---

*以上内容对应 COMP5423 项目文档中的 Data preparation 阶段，便于直接引用到项目报告中。*
