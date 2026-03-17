---
name: Data Preparation 数据准备实现方案
overview: 以 Hugging Face 上的 StoryEngine Dataset（SatorTenet/storyengine-dataset）为唯一主数据源，完成数据获取、清洗、剧情单元划分、意图与一致性标注、以及 WorldBible/金标轨迹的构建，产出可直接供后续 Transformers + PyTorch + Gradio 架构使用的结构化数据。
todos: []
isProject: false
---

# Data Preparation（数据准备）实现方案

本方案仅覆盖**数据准备阶段**。选定**单一主数据源**，并给出针对该来源的完整准备流程与产出规范，便于你审核后按此实现。

---

## 一、数据源选取：StoryEngine Dataset

### 1.1 为何选 StoryEngine

- **与架构一致**：每条样本即「系统状态（system）→ 玩家选择（user）→ 叙述续写（assistant）」，天然对应我们的「GameState + 玩家输入 + 动态生成」流水线；可直接支撑意图识别、上下文生成与分支选项设计。
- **结构清晰**：JSONL 格式，字段固定（`messages` + `meta`），便于用 Python 批量清洗与划分剧情单元，无需解析游戏引擎或非结构化脚本。
- **含叙事状态与类型**：`meta` 含 `type`（scene_continuation / genre_opening / fail_forward 等）、`genre`、`polti`（戏剧情境），可直接用于「世界观/类型」约束和意图映射。
- **规模适中**：约 3140 条对话轮次，足够做剧情单元表、意图标注抽样与一致性抽样，无需再接入多数据源增加实现复杂度。
- **获取简单**：Hugging Face `datasets` 一行加载，支持离线缓存；Apache 2.0 许可，可写进报告。

### 1.2 数据源唯一标识与获取方式

- **名称**：StoryEngine Interactive Fiction Dataset  
- **Hugging Face**：`SatorTenet/storyengine-dataset`  
- **获取方式**：`datasets.load_dataset("SatorTenet/storyengine-dataset")`（或指定 `split="train"` 若仅需训练集）；首次运行自动下载至本地缓存。  
- **原始格式**：每条约为：
  - `messages`: 列表，依次为 `system`（叙事状态提示）、`user`（如 "Player chose: B. Continue the story."）、`assistant`（叙述续写 + 选项 A/B/C）。
  - `meta`: 字典，至少含 `type`, `genre`, `polti`。

本阶段**不再引入其他数据集**；意图与一致性若需更多样本，通过对 StoryEngine 抽样后自标注完成。

---

## 二、数据准备流程（针对 StoryEngine 的实操步骤）

### 2.1 环境与目录约定

- **环境**：Python 3.11+；依赖 `datasets`, `pandas`（或仅标准库 JSON），可选 `pyyaml`（WorldBible）。
- **目录结构**（在项目根下）：
  - `data/raw/storyengine/`：从 Hugging Face 拉取后的原始 JSONL 或按条保存的 JSON（若需逐条留存）。
  - `data/cleaned/storyengine/`：清洗后的 JSONL。
  - `data/plot_units/`：剧情单元表（CSV 或 JSONL）。
  - `data/annotations/`：意图标注、一致性标注（JSON/JSONL），含 `train/val/test` 划分文件列表或单文件内带 `split` 字段。
  - `data/world_bible/`：世界观 YAML/JSON。
  - `data/gold_trajectories/`：金标轨迹 JSON。
  - `scripts/data_prep/`：本阶段所有脚本（见下）。

### 2.2 步骤 1：获取与落盘原始数据

- **操作**：
  1. 使用 `datasets.load_dataset("SatorTenet/storyengine-dataset")` 加载；
  2. 将每条样本写为一行 JSON，保存到 `data/raw/storyengine/storyengine_raw.jsonl`（若 dataset 为分块或 list，则逐条 `json.dumps` 写入）；
  3. 记录条数、以及 `meta.type` 的分布（各 type 数量），写入 `data/raw/storyengine/README.md` 或同目录下 `meta_stats.json`。
- **验收**：存在 `data/raw/storyengine/storyengine_raw.jsonl`，行数约 3140；README 或 meta_stats 中记录来源与 type 分布。

### 2.3 步骤 2：清洗文本噪声

- **清洗对象**：每条中的 `messages[*].content` 及 `meta` 中的字符串（若有）。
- **规则**：
  - 编码：统一为 UTF-8；对异常字节用 `errors="replace"` 或丢弃。
  - 空白：将连续空白（含 `\t`、`\n` 多行）规范为单空格；段落间保留一个换行即可。
  - 不可见字符：去除 `\r`、`\x00` 等控制字符（可用 `unicodedata` 或简单正则）。
  - 不去除内容中的 Markdown 或 A/B/C 选项结构；不修改 `meta` 键名与结构。
- **实现**：脚本 `scripts/data_prep/01_clean.py`：读 `data/raw/storyengine/storyengine_raw.jsonl`，逐条清洗后写 `data/cleaned/storyengine/storyengine_cleaned.jsonl`；同一目录下可输出 `cleaning_rules.txt` 记录上述规则（供报告引用）。
- **验收**：`storyengine_cleaned.jsonl` 行数与 raw 一致；抽检若干条无乱码与异常空白。

### 2.4 步骤 3：剧情单元划分（segmenting plot units）

- **定义**：一条 StoryEngine 样本 = 一个**剧情单元**。单元字段与含义：
  - `plot_unit_id`：唯一 ID（如 `se_0001` 或基于行号）。
  - `narrative_text`：本步「叙述内容」——取 `messages` 中 `role=="assistant"` 的 `content`（即模型续写的那段，含选项 A/B/C 文本）。
  - `player_input`：玩家在本步的输入——取 `role=="user"` 的 `content`。
  - `available_choices`：从 `narrative_text` 中解析出的选项列表（如通过正则提取 "**A.** ... **B.** ... **C.** ..." 或 "A) ... B) ... C) ..."）；若解析失败可置空列表并标 `choices_parsed: false`。
  - `next_unit_id`：StoryEngine 为独立轮次，无显式「下一单元」指针，可置 `null`；若后续做会话链还原（同一 genre/session），可在此阶段或后续脚本中按顺序或 session 推断。
  - `source`：固定为 `"storyengine"`。
  - `meta`：整块保留（`type`, `genre`, `polti`），便于后续意图映射与过滤。
  - `world_context_summary`（可选）：从 `system` 的 content 中截取前 200 字或提取「Genre / Scene / Dramatic thread」等关键行，作为摘要。
- **实现**：脚本 `scripts/data_prep/02_segment_plot_units.py`：读 `storyengine_cleaned.jsonl`，逐条生成上述结构，输出 `data/plot_units/storyengine_units.jsonl`（或 CSV，若更便于后续标注工具）。
- **验收**：`storyengine_units.jsonl` 行数与原数据一致；每条含 `narrative_text`, `player_input`, `available_choices`, `meta`；`available_choices` 在可解析样本中非空。

### 2.5 步骤 4：意图标注（labeling narrative logic — intent）

- **意图类别**（与 `meta.type` 对齐，便于半自动标注）：
  - `scene_continuation` → 映射为 `continue`（或保留原名）；
  - `genre_opening` → `start`；
  - `fail_forward` → `fail_forward`；
  - `command_response` → `meta_help`（对应 /status、/time 等）；
  - `session_end` → `end`；
  - `init_sequence` → `init`。
- **若需更细粒度**：可增加 `explore` / `talk` / `negotiate` 等，则从 `player_input` 与 `narrative_text` 中抽样 200–500 条，人工标注后与上述 6 类合并（标注格式见下）。
- **标注格式**：每条约为 `{"id": "se_0001", "input_text": "Player chose: B. ...", "intent_label": "continue", "source": "storyengine"}`；若为人工标注子集，可增加 `annotator`、`notes`。
- **数据划分**：从 `data/plot_units/storyengine_units.jsonl` 中按 80/10/10 或 70/15/15 划分 train/val/test（按 `plot_unit_id` 或随机 seed 划分，保证同一 session 不跨 split 若后续有 session 信息）；输出：
  - `data/annotations/intent_train.jsonl`
  - `data/annotations/intent_val.jsonl`
  - `data/annotations/intent_test.jsonl`
  每条带 `input_text`, `intent_label`，以及可选的 `plot_unit_id` 以便回溯。
- **实现**：脚本 `scripts/data_prep/03_build_intent_annotations.py`：读 `storyengine_units.jsonl`，用 `meta.type` 映射得到默认 `intent_label`，再做 train/val/test 划分并写入上述三个文件；若有人工标注文件，脚本支持合并（相同 id 以人工为准）。
- **验收**：三个 intent 文件存在；`intent_label` 取值在预定集合内；train 规模约 2500+，val/test 各约 300+。

### 2.6 步骤 5：剧情一致性标注样本（可选但建议做）

- **目的**：为后续「一致性检测」模块提供正负样本或评测集。
- **做法**：从 `storyengine_units.jsonl` 中随机抽样 80–150 条；对每条构造「上下文 = 该条之前的同 session 的 narrative_text 拼接（若无 session 则取前一条）」+「当前 narrative_text」。
  - **正样本**：上下文与当前叙述来自同一 StoryEngine 样本链（或同 genre 的连续两条），标签 `consistent=1`。
  - **负样本**：随机配对不同 genre 或打乱顺序的「上下文—当前」，或人工改写当前叙述引入 1–2 处事实/时间/角色矛盾，标签 `consistent=0`。
- **格式**：`{"id": "...", "context": "...", "current_narrative": "...", "consistent": 1|0, "notes": "optional"}`。
- **实现**：脚本 `scripts/data_prep/04_build_consistency_annotations.py`：读 `storyengine_units.jsonl`，抽样并生成 context/current 对，自动标正样本；负样本可随机配对生成一部分，另一部分留作人工填写；输出 `data/annotations/consistency_annotations.jsonl`，并可选 train/val 划分。
- **验收**：文件存在；`consistent` 0/1 比例大致平衡或略偏正样本；至少 50 条可用于验证一致性模块。

### 2.7 步骤 6：WorldBible 与金标轨迹（与 StoryEngine 风格对齐）

- **WorldBible**：不直接从 StoryEngine 解析，而是**手写**一份与 StoryWeaver 演示场景一致的单一世界观（例如村庄—洞穴—长老—禁忌），便于 Gradio 演示与评测可控。建议字段：
  - `setting`：背景简述；
  - `characters`：3–5 人（姓名、身份、性格要点）；
  - `locations`：5–8 个地点及简短描述；
  - `rules_forbidden`：3–5 条禁忌或规则（如「长老未同意不得进入禁地」）；
  - `main_conflict`：主线冲突一句话；
  - `key_items`：可选，若干关键物品。
- **存放**：`data/world_bible/world_main.yaml`（或 JSON）。
- **金标轨迹**：在 `world_main` 设定下，手写 2–3 条「从开局到结局」的玩家选择序列，每条 5–10 步即可；每步包含：`step_id`, `player_choice_text`, `expected_narration_summary`（期望叙述的 1–2 句摘要，用于评测「剧情走向」与选择匹配）。存放 `data/gold_trajectories/gold_*.json`。
- **实现**：WorldBible 与金标为手写 YAML/JSON，无需自动脚本；可提供 `data/world_bible/schema.yaml` 或示例文件说明字段含义。
- **验收**：`world_main.yaml` 符合上述结构；至少 2 个金标轨迹文件，每条约 5–10 步且含 `player_choice_text` 与 `expected_narration_summary`。

### 2.8 步骤 7：数据说明文档（供报告引用）

- **内容**：一页内说明（可放在 `data/README.md`）：
  - 主数据源：StoryEngine，Hugging Face 名、条数、许可；
  - 各目录与文件用途（raw / cleaned / plot_units / annotations / world_bible / gold_trajectories）；
  - 剧情单元字段说明；
  - 意图类别与一致性标注格式；
  - train/val/test 划分比例与大致规模。
- **验收**：存在 `data/README.md`，他人可据此复现数据准备流程。

---

## 三、产出清单与验收总表


| 产出路径                                                    | 说明                      | 验收                                                      |
| ------------------------------------------------------- | ----------------------- | ------------------------------------------------------- |
| `data/raw/storyengine/storyengine_raw.jsonl`            | 原始 StoryEngine 条数约 3140 | 行数正确、JSON 可解析                                           |
| `data/raw/storyengine/README.md` 或 `meta_stats.json`    | 来源与 type 分布             | 有记录                                                     |
| `data/cleaned/storyengine/storyengine_cleaned.jsonl`    | 清洗后 JSONL               | 行数一致、无乱码                                                |
| `data/plot_units/storyengine_units.jsonl`               | 剧情单元表                   | 含 narrative_text, player_input, available_choices, meta |
| `data/annotations/intent_train.jsonl`                   | 意图训练集                   | 含 input_text, intent_label                              |
| `data/annotations/intent_val.jsonl`                     | 意图验证集                   | 同上                                                      |
| `data/annotations/intent_test.jsonl`                    | 意图测试集                   | 同上                                                      |
| `data/annotations/consistency_annotations.jsonl`        | 一致性标注（可选）               | 含 context, current_narrative, consistent                |
| `data/world_bible/world_main.yaml`                      | 世界观设定                   | 含 setting, characters, locations, rules, conflict       |
| `data/gold_trajectories/gold_*.json`                    | 金标轨迹 ≥2 条               | 每条约 5–10 步，含 choice 与 expected_summary                  |
| `data/README.md`                                        | 数据说明                    | 含来源、字段、划分说明                                             |
| `scripts/data_prep/01_clean.py`                         | 清洗脚本                    | 可复现清洗                                                   |
| `scripts/data_prep/02_segment_plot_units.py`            | 剧情单元脚本                  | 可复现单元表                                                  |
| `scripts/data_prep/03_build_intent_annotations.py`      | 意图标注与划分                 | 可复现 intent 三份文件                                         |
| `scripts/data_prep/04_build_consistency_annotations.py` | 一致性标注脚本（可选）             | 可复现 consistency 文件                                      |


---

## 四、实现顺序建议

1. 步骤 2.2（获取与落盘）→ 2.3（清洗）→ 2.4（剧情单元）可顺序执行，前一步产出为后一步输入。
2. 步骤 2.5（意图）依赖 2.4 的 `storyengine_units.jsonl`。
3. 步骤 2.6（一致性）同样依赖 2.4，可与 2.5 并行开发。
4. 步骤 2.7（WorldBible + 金标）与 2.8（README）可随时补充，建议在 2.4 完成后即可开始手写 WorldBible，以便后续算法与评测设计对齐。

审核通过后，按上述步骤与脚本命名实现即可；若你希望某一步再细化（例如选项解析的正则规范、意图与 meta.type 的精确映射表），可在实现前补充进本 plan 的对应小节。