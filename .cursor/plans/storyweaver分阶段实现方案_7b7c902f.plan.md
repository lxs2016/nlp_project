---
name: StoryWeaver分阶段实现方案
overview: 严格按 COMP5423 项目文档的四个阶段（Data preparation、Algorithm design、System implementation、Performance evaluation）写出可执行方案，重点细化数据来源、获取方式、预处理与标注流程，以及各阶段产出与验收标准。
todos: []
isProject: false
---

# StoryWeaver 分阶段具体实现方案（按文档要求）

以下按项目文档中的四个关键步骤逐项展开：数据来源、具体操作、产出物及与后续阶段的衔接。

---

## 一、Data preparation（数据准备）

文档要求：收集并组织用于训练与测试的**文本冒险游戏脚本、分支叙事语料、对话数据集、剧情一致性标注样本**；通过**清洗文本噪声、划分剧情单元、标注叙事逻辑**保证一致性与质量。

### 1.1 数据来源（去哪里获取）

#### （1）文本冒险游戏脚本 / 分支叙事语料


| 来源                                                    | 说明与获取方式                                                                                                  | 用途                              |
| ----------------------------------------------------- | -------------------------------------------------------------------------------------------------------- | ------------------------------- |
| **Jericho / TextWorld**                               | Microsoft 的交互式小说环境；GitHub: `microsoft/jericho`、`microsoft/TextWorld`；游戏为 Z-Machine 格式，可解析「当前描述 + 可用动作」序列 | 抽取「状态—动作—下一状态」三元组，作为剧情单元与分支结构样本 |
| **TALES (Text Adventure Learning Environment Suite)** | 论文/资源：TALE-Suite (Microsoft)，集成 Jericho、TextWorld、ScienceWorld 等；PyPI/ GitHub 可获取                        | 标准化剧情轨迹与动作序列，用于评测与 few-shot 示例  |
| **StoryEngine Dataset**                               | Hugging Face: `SatorTenet/storyengine-dataset`；约 3140 条交互式叙事对话，含叙事状态、类型、基调等                              | 直接用作「上下文—玩家选择—叙述续写」的监督/提示示例     |
| **BAER (Actionable Entities Recognition)**            | GitHub: `altsoph/BAER`；互动小说中的可操作实体识别 benchmark                                                           | 辅助定义「动作/实体」词表与意图类别，用于意图标注规范     |
| **开源互动小说脚本**                                          | 如 Choice of Games 风格脚本、Twine 导出文本、IFDB 上的公开游戏 walkthrough                                                | 人工抽取「段落—选项—后果」结构，构建自有小规模分支叙事表   |


#### （2）对话数据集


| 来源                   | 说明与获取方式                                                                | 用途                                     |
| -------------------- | ---------------------------------------------------------------------- | -------------------------------------- |
| **NPC-Dialogue_v2**  | Hugging Face: `chimbiwide/NPC-Dialogue_v2`；约 1688 段游戏 NPC 对话（每段约 16 轮） | 角色语气、对话结构；可提炼「玩家意图—NPC 回应」模式           |
| **RolePlay-NPC**     | Hugging Face: `chimbiwide/RolePlay-NPC`；含 PIPPA 清洗数据与合成 NPC 对话         | 与 NPC-Dialogue 互补，用于对话管理与生成风格          |
| **MCPDial / KNUDGE** | Minecraft/《天外世界》相关对话树与约束                                               | 参考「任务/设定约束下的对话」结构，用于 WorldBible 下的对话逻辑 |
| **自建对话片段**           | 根据选定世界观（如村庄—洞穴—长老）手写 10–20 条/角色 的典型对话                                  | 与 WorldBible 一致，用于 few-shot 与评测        |


#### （3）剧情一致性标注样本


| 来源                                   | 说明与获取方式                                                                   | 用途                            |
| ------------------------------------ | ------------------------------------------------------------------------- | ----------------------------- |
| **ConStory-Bench**                   | Hugging Face: `jayden8888/ConStory-Bench`；长文故事一致性错误标注与分类（世界设定、时间线、事实、角色等） | 定义「一致性违规」类型与标注规范；可训练或提示一致性检查器 |
| **Plot-guided Coherence Evaluation** | GitHub: `PlusLabNLP/Plot-guided-Coherence-Evaluation`                     | 剧情引导的连贯性评估方法，可借鉴评测指标          |
| **自标注**                              | 从 StoryEngine / 自写剧情中抽样 50–100 段，标注「是否与上文/WorldBible 矛盾」及类型               | 小规模一致性分类数据或 LLM-as-judge 的验证集 |


#### （4）故事生成预训练/微调（可选）


| 来源                              | 说明与获取方式                                                               | 用途                                      |
| ------------------------------- | --------------------------------------------------------------------- | --------------------------------------- |
| **TinyStories / SimpleStories** | Hugging Face: `roneneldan/TinyStories`, `SimpleStories/SimpleStories` | 若用本地 Transformers 小模型做叙述生成，可作为风格数据或微调数据 |
| **story-generation-dataset**    | Hugging Face: `krisha05/story-generation-dataset` 等                   | 指令—叙述对，用于 SFT 或 prompt 设计参考             |


### 1.2 数据准备具体步骤（怎么做）

#### 步骤 1：清洗文本噪声

- **内容**：统一编码（UTF-8）、去除不可见字符、规范化空白与断行；去除游戏引擎/调试标记（如 `[DEBUG]`、行号）；统一标点（中英文标点按需统一）。
- **工具**：脚本（Python）正则 + `unicodedata`；可配合 `ftfy` 修复乱码。
- **产出**：`data/raw/` 下按来源分目录存放清洗后原文；记录清洗规则文档（用于报告）。

#### 步骤 2：剧情单元划分（segmenting plot units）

- **定义剧情单元**：最小单位 = 「一个完整叙述片段 + 对应可选动作集合 + 执行某动作后的下一片段」。
- **操作**：
  - 对 Jericho/TextWorld 轨迹：解析日志得到 `(observation, valid_actions, chosen_action, next_observation)`，每一条作为一单元。
  - 对 StoryEngine：按 turn 切分，每 turn 含「叙事状态 + 玩家输入 + 系统叙述」。
  - 对自采 IF 脚本：按「段落—选项块—下一段落」切分，缺失处标为「待补全」。
- **产出**：结构化表（如 CSV/JSON），字段至少包含：`plot_unit_id`, `narrative_text`, `available_choices[]`, `next_unit_id_or_null`, `source`, `world_context_summary`（可选）。

#### 步骤 3：叙事逻辑与意图标注（labeling narrative logic）

- **意图标签**：定义 6–8 类（如 `explore`, `talk`, `negotiate`, `fight`, `use_item`, `inspect`, `meta_help`），对「玩家输入/选项」做标注。
  - 数据来源：从 StoryEngine、NPC 对话、自写选项中抽样；每人标注 50+ 条，交叉校验后合并。
  - 格式：`(input_text, intent_label, optional: entity_list)`，存为 `data/annotations/intent_*.json` 或 CSV。
- **叙事逻辑**：对「前一单元 → 选择 → 当前单元」标注是否**因果合理**、是否**符合世界观**（二分类或 1–3 分）；可从 ConStory 错误类型中选 3–5 类做简化标注。
- **产出**：意图数据集（train/val/test 划分）；一致性标注子集（用于规则设计或小模型训练）。

#### 步骤 4：WorldBible 与评测用金标

- **WorldBible**：手写 YAML/JSON，包含单一世界观下的：背景、3–5 个核心人物、5–8 个地点、规则/禁忌、主线冲突、关键物品。存于 `data/world_bible/`。
- **金标轨迹**：在固定 WorldBible 下，手写 2–3 条「从开局到结局」的完整选择序列 + 每步期望叙述摘要（用于评测「选择匹配」与「剧情走向」）。

### 1.3 数据准备阶段产出清单

- `data/raw/`：清洗后原文（按来源分子目录）。
- `data/plot_units/`：剧情单元表（CSV/JSON）。
- `data/annotations/intent_*.json`：意图标注（含 train/val/test 划分）。
- `data/annotations/consistency_*.json`：一致性标注样本（可选）。
- `data/world_bible/world_*.yaml`：世界观设定。
- `data/gold_trajectories/`：金标轨迹与期望叙述摘要。
- 简短 **数据说明文档**（来源、字段、规模、划分比例），便于报告中的「Data preparation」小节引用。

---

## 二、Algorithm design（算法设计）

文档要求：探索**上下文感知文本生成、用户意图识别、剧情一致性检测、对话管理**等先进 NLP 方法；实现**实时生成流水线**与**有效分支策略**；**整合多个 NLP 模型**以提供连贯、个性化的叙事输出。

### 2.1 用户意图识别（User intent recognition）

- **方法**：基于 Hugging Face Transformers 的序列分类（如 BERT/ALBERT `ForSequenceClassification`），PyTorch 训练与推理。
- **数据**：使用 1.3 中的意图标注数据；划分 80/10/10 或 70/15/15。
- **实现要点**：`transformers.AutoModelForSequenceClassification` + `Trainer`；输入为玩家原始输入或选项文本；输出意图 ID + 置信度；不确定时可用阈值触发「多意图」或默认 `explore`。
- **与下游衔接**：意图作为「规划器」与「生成器」的 conditioning 信号。

### 2.2 上下文感知文本生成（Context-aware text generation）

- **上下文构成**：当前 GameState（地点、人物、物品、目标） + 检索到的记忆（最近 K 条 + 与当前状态相关的历史事件） + 当前意图 + 规划器给出的本步「剧情目标/冲突推进」。
- **方法**：以 LLM API 或本地 Transformers 生成模型（如 TinyLlama/Phi）为 backbone；严格 prompt 模板（system + user），输出格式限定为 JSON（`narration`, `choices[]`, `state_updates`）。
- **分支策略**：规划器每次产出 2–4 个**语义不重叠**的选项（通过 prompt 约束或后处理去重）；选项与意图映射表可选，用于「选择匹配准确率」计算。

### 2.3 剧情一致性检测（Plot consistency detection）

- **规则层**：实体一致性（人物/地点/物品不凭空出现）、状态转移合法（如物品数量、角色存活）、禁忌条款（来自 WorldBible）检查。
- **模型层（可选）**：用 ConStory 类型标注做二分类（一致/不一致），Transformers 分类器在 PyTorch 下推理；或采用「LLM 评审」：固定 prompt 让模型对「前文 + 本段」打分并给出理由。
- **回退**：不一致时带理由重生成（最多 2 次），仍失败则输出简化叙述 + 减少选项数以降低风险。

### 2.4 对话管理（Dialogue management）

- **状态管理**：维护 GameState（地点、人物状态、物品、已完成事件列表）；每步根据生成器的 `state_updates` 更新。
- **记忆与检索**：用 sentence-transformers（Transformers + PyTorch）对「事件摘要」编码；存储为向量 + 时间戳；每步检索「与当前地点/人物/冲突相关」的 Top-K，并与最近 N 条按时间拼接，注入生成上下文。
- **对话轮次**：同一场景内多轮对话可建模为「多轮上下文 + 当前玩家输入」一次性送入生成器，由生成器决定是否推进场景。

### 2.5 实时生成流水线与多模型整合

- **流水线顺序**：输入 → 意图识别 → 规划器（基于状态+意图生成本步计划）→ 记忆检索 → 上下文组装 → 生成 → 一致性检查 → 状态更新 → 输出。
- **多模型角色**：意图模型（Transformers 分类）、检索编码器（sentence-transformers）、生成模型（API 或 Transformers）、一致性模型（规则 + 可选分类/LLM）。
- **性能**：意图与检索在 CPU/单 GPU 上可做到 <100ms；生成延迟主要来自 API 或本地大模型，通过「流式输出 + 提前展示」改善体验。

### 2.6 算法设计阶段产出

- 意图模型权重与推理脚本；检索索引构建脚本；生成与一致性检查的接口与默认 prompt。
- 设计文档：各模块输入输出、依赖关系、超参与阈值（便于报告中的「Algorithm design」小节）。

---

## 三、System implementation（系统实现）

文档要求：使用 **Hugging Face Transformers、PyTorch、Gradio** 开发交互式文本冒险系统；**用户友好界面**，处理玩家选择并输出**动态生成、逻辑衔接顺畅**的剧情。

### 3.1 技术栈与目录

- **Gradio**：唯一前端；`gr.Blocks()` 布局（叙述区、选项区、自由输入、状态摘要）；回调函数调用后端「单步推理」接口。
- **PyTorch**：所有模型推理后端；自定义模块与数据加载基于 PyTorch。
- **Transformers**：意图分类、sentence-transformers 检索、可选本地生成模型。
- **推荐目录**：`app_gradio.py` 或 `gradio_app/`（界面）、`game/`（状态与回合逻辑）、`models/`（意图/检索/生成封装）、`prompts/`、`data/`、`scripts/`、`tests/`。

### 3.2 后端单步接口

- **入参**：`session_id`, `user_input`（文本或选项 ID）, `history`（可选，由服务端从 session 恢复）。
- **内部**：加载 GameState 与 Memory → 意图识别 → 规划 → 检索 → 生成 → 一致性检查 → 更新状态与记忆。
- **出参**：`narration`, `choices[]`, `state_summary`, `error_message`（若发生回退或异常）。

### 3.3 Gradio 界面要点

- 展示最新叙述（Markdown 或 Chatbot）；下方固定 2–4 个按钮（对应当前 `choices`）+ 可选自由输入框；侧边或折叠区展示「当前地点/关键物品/目标」。
- 每次提交后禁用输入直至返回结果，避免重复提交；支持「新游戏」重置 session 与状态。
- 演示时使用固定种子与固定起始状态，保证 4 月 8 日现场可复现。

### 3.4 系统实现阶段产出

- 可运行的 Gradio 应用；一键启动脚本（含环境与模型路径说明）；简短用户说明（如何开始、选择、重置）。

---

## 四、Performance evaluation（性能评估）

文档要求：评估系统的**叙事质量、交互响应性、用户体验**；测量**剧情连贯性得分、生成响应时间、玩家选择匹配准确率、沉浸感满意度**等。

### 4.1 指标与测量方式


| 指标                         | 含义             | 测量方法                                                   |
| -------------------------- | -------------- | ------------------------------------------------------ |
| **剧情连贯性 (Plot coherence)** | 叙述与世界观/前文是否一致  | 规则检查违规率（每回合）；抽样用 ConStory 类型标注或 LLM 评审打 1–5 分，报告均值与分布  |
| **生成响应时间**                 | 从用户提交到返回叙述的延迟  | 端到端计时（P50/P95），区分首次加载与后续步；报告含重试次数分布                    |
| **玩家选择匹配准确率**              | 系统是否正确理解玩家所选选项 | 在金标轨迹上，对比「金标选项」与「系统识别的意图/执行的分支」；若为按钮选项则可为精确匹配率         |
| **沉浸感/满意度**                | 主观体验           | 小规模用户测试（5–10 人），Likert 1–5 问卷（沉浸感、逻辑顺畅度、可控感）；报告均值与简要评论 |


### 4.2 评测数据与实验设计

- **数据**：1.3 中的金标轨迹 + 自建 WorldBible；可额外构造 10–20 条「含已知一致性错误」的叙述用于一致性检测器的召回/精确率。
- **实验**：完整系统 vs 消融（无检索、无一致性检查、仅规则分支）对比；报告各指标与 1–2 个失败案例分析。
- **工具**：`scripts/eval.py` 可重复跑响应时间与选择匹配；连贯性与满意度依赖人工/LLM 评审脚本半自动化。

### 4.3 评估阶段产出

- 评测脚本与结果数据（JSON/CSV）；报告用表格与短段分析；可选 1–2 个展示「逻辑衔接顺畅」与「不一致案例」的截图或片段。

---

## 五、与报告、演示的对应关系

- **Data preparation**：报告中出现数据来源表、预处理与标注步骤、规模与划分、WorldBible 与金标简介。
- **Algorithm design**：各 NLP 任务的方法简述、流水线图、多模型整合说明。
- **System implementation**：技术栈说明、Gradio 界面截图、目录与运行方式。
- **Performance evaluation**：指标定义、实验设置、结果表与简短讨论。
- **演示**：4 月 8 日现场用 Gradio 展示 2–3 条可控路径，强调「玩家选择 → 动态剧情 → 逻辑衔接」；PPT 提前交 Blackboard。

以上方案可直接作为开发与报告撰写的执行清单；数据来源均采用公开或常用资源，便于复现与引用。