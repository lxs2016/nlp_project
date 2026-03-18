# StoryWeaver 数据说明（Data Preparation 产出）

本目录为 COMP5423 项目 **Data preparation** 阶段的产出，供后续算法、系统实现与报告引用。

---

## 1. 主数据源

| 项目 | 说明 |
|------|------|
| **名称** | StoryEngine Interactive Fiction Dataset |
| **Hugging Face** | `SatorTenet/storyengine-dataset` |
| **规模** | 约 3140 条交互式叙事对话轮次 |
| **许可** | Apache 2.0 |
| **格式** | 每条为「system + user + assistant」消息列表 + meta（type, genre, polti） |

选用理由：与 StoryWeaver 的「GameState + 玩家输入 + 动态叙述」流水线一致，含叙事状态与类型标签，便于意图映射与剧情单元划分。

---

## 2. 目录与文件用途

| 路径 | 用途 |
|------|------|
| `data/raw/storyengine/` | 从 Hugging Face 拉取的原始 JSONL、条数及 meta.type 分布 |
| `data/cleaned/storyengine/` | 清洗后 JSONL、清洗规则说明 |
| `data/plot_units/` | 剧情单元表（narrative_text, player_input, available_choices, meta 等） |
| `data/annotations/` | 意图 train/val/test 与一致性标注 |
| `data/world_bible/` | 单一世界观设定（YAML）及字段说明 |
| `data/gold_trajectories/` | 金标轨迹（用于评测选择匹配与剧情走向） |

---

## 3. 剧情单元字段说明（storyengine_units.jsonl）

| 字段 | 类型 | 说明 |
|------|------|------|
| plot_unit_id | str | 唯一 ID，如 se_0001 |
| narrative_text | str | 本步叙述（assistant 内容，含选项 A/B/C） |
| player_input | str | 玩家输入（user 内容） |
| available_choices | list[str] | 解析出的选项文本列表 |
| choices_parsed | bool | 是否成功解析出选项 |
| next_unit_id | null | StoryEngine 无显式下一单元，固定 null |
| source | str | 固定 "storyengine" |
| meta | object | type, genre, polti 等 |
| world_context_summary | str | 从 system 截取的前 200 字摘要 |

---

## 4. 意图类别与标注格式

**意图标签**（与 meta.type 映射）：

- `scene_continuation` → **continue**
- `genre_opening` → **start**
- `fail_forward` → **fail_forward**
- `command_response` → **meta_help**
- `session_end` → **end**
- `init_sequence` → **init**

**意图文件**：`intent_train.jsonl` / `intent_val.jsonl` / `intent_test.jsonl`  
每条含：`plot_unit_id`, `input_text`, `intent_label`, `source`。  
划分比例：80% train，10% val，10% test（随机种子 42）。

---

## 5. 一致性标注格式

**文件**：`consistency_annotations.jsonl`  
每条含：`id`, `context`, `current_narrative`, `consistent`（1=一致，0=不一致）, `notes`。  
正样本：连续两条叙述对；负样本：随机配对叙述对。用于一致性检测模块训练或评测。

---

## 6. 复现数据准备流程

依赖：`huggingface_hub`, `pyyaml`（见项目根目录 `requirements.txt`）。

**一键运行**（项目根目录）：

```bash
python scripts/data_prep/run_all.py
```

**分步运行**：

```bash
# 1) 拉取原始数据（需网络）
python scripts/data_prep/00_fetch_raw.py

# 2) 清洗
python scripts/data_prep/01_clean.py

# 3) 剧情单元划分
python scripts/data_prep/02_segment_plot_units.py

# 4) 意图标注与划分
python scripts/data_prep/03_build_intent_annotations.py

# 5) 一致性标注
python scripts/data_prep/04_build_consistency_annotations.py
```

WorldBible 与金标轨迹为手写文件，无需脚本生成。

---

## 7. 报告引用要点

- **数据来源**：仅使用 StoryEngine（Hugging Face），无其他外部叙事数据集。
- **预处理**：编码统一 UTF-8、去除控制字符、规范化空白；保留选项与 meta 结构。
- **剧情单元**：一条样本 = 一单元；选项通过正则从 assistant 文本解析。
- **意图**：由 meta.type 映射得到 6 类，按 80/10/10 划分。
- **一致性**：连续对为正、随机对为负，用于一致性评测或训练。
- **WorldBible 与金标**：手写单一世界观与 2 条金标轨迹，用于演示与选择匹配/剧情走向评测。
