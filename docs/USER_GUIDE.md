# StoryWeaver 用户说明（System implementation）

## 安装与启动

### 环境

- Python 3.10+
- 安装依赖（在项目根目录执行）：
  ```bash
  pip install -r requirements.txt
  ```
- 需已具备数据与模型产出：`data/world_bible/world_main.yaml`、`data/annotations/intent_*.jsonl`、意图模型权重（如 `models/intent/`），参见 [data/README.md](../data/README.md)。

### 工作目录

**必须在项目根目录**（即包含 `app_gradio.py`、`game/`、`data/` 的目录）下启动，否则无法加载 WorldBible 与模型。

### 一键启动

- 方式一（推荐）：
  ```bash
  python app_gradio.py
  ```
- 方式二：
  ```bash
  ./scripts/run_app.sh
  ```
  或 `bash scripts/run_app.sh`（会先切换到项目根再启动）。

启动后在浏览器打开终端提示的地址（默认 `http://0.0.0.0:7860` 或 `http://127.0.0.1:7860`）。

### 可选配置

- **端口**：默认 7860。指定端口示例：
  ```bash
  PORT=8080 python app_gradio.py
  ```
  或 `PORT=8080 ./scripts/run_app.sh`。
- **演示种子**：若后续在 Generator 或配置中支持 `DEMO_SEED` 环境变量，可设置以保证演示可复现。

### API 配置（OpenRouter / OpenAI）

剧情生成使用 OpenAI 兼容的 Chat API。若使用 **OpenRouter**，在项目根目录的 `.env` 中配置：

```bash
# OpenRouter：密钥 + 统一入口
OPENAI_API_KEY=sk-or-v1-你的OpenRouter密钥
OPENAI_API_BASE=https://openrouter.ai/api/v1
# 模型 ID：须与你在 OpenRouter 中启用的提供商一致
# 若仅启用 Google：用 google/gemini-2.5-pro 或 google/gemini-flash-1.5
# 若启用 OpenAI：用 openai/gpt-3.5-turbo 或 openai/gpt-4
OPENAI_MODEL=openai/gpt-3.5-turbo
```

若报错 `No allowed providers are available for the selected model`，说明当前 key 只能使用部分提供商（错误信息里会列出 `available_providers`）。请把 `OPENAI_MODEL` 改成**这些提供商之一**能提供的模型，例如：

- 若可用 **Google**：`OPENAI_MODEL=google/gemini-2.5-pro` 或 `google/gemini-flash-1.5`
- 若可用 **Together / DeepInfra** 等（无 Google）：可改为 `meta-llama/llama-3.1-8b-instruct`、`qwen/qwen-2.5-7b-instruct`、`deepseek/deepseek-chat-v3-0324` 等（在 [OpenRouter 模型页](https://openrouter.ai/models) 中查看对应 provider 再选）

若使用 **OpenAI 官方**，只需设置 `OPENAI_API_KEY=sk-...`，无需 `OPENAI_API_BASE`。

验证是否连通：`python scripts/check_openai.py`。

**若每次点击都返回同一句「你站在当前场景中，需要做出选择。」**：说明 Generator 未接通 LLM，在用内置 fallback。请查看运行 `python app_gradio.py` 的终端是否出现 `[Generator] 未配置 API key` 或 `[Generator] LLM 调用异常`，并按上文配置 `.env` 与 `python scripts/check_openai.py` 通过后再试。**训练数据**（`data/annotations/intent_*.jsonl`、`data/plot_units/`）用于意图识别和记忆检索，**叙述正文由 LLM 根据世界观与当前状态实时生成**，不是从数据里直接查的；只有 LLM 接通后剧情才会随选择变化。

**若感觉响应慢**：每步都会请求一次远程 LLM，通常需数秒。可改用更快的模型（如在 OpenRouter 使用 `google/gemini-flash-1.5` 而非 `gemini-2.5-pro`），或减少生成长度（生成器已限制约 500 tokens）。

---

## 如何使用

1. **开始游戏**  
   打开页面后点击 **「开始」**，系统会生成会话并显示第一段叙述与 2–4 个选项。

2. **选择与输入**  
   - **选项**：点击任一选项按钮，即以其文本作为本步输入，并得到新的叙述与下一组选项。  
   - **自由输入**：在「自由输入」框输入行动描述（如「前往洞穴」），点击 **「提交」** 或按回车，系统会据此推进剧情。

3. **当前状态**  
   「当前状态」区域显示地点、携带物品等，随剧情更新。

4. **新游戏**  
   点击 **「新游戏」** 会重置当前会话状态并重新从开场开始，适合演示或重新游玩。

5. **错误提示**  
   若出现一致性检查等提示，会显示在叙述区下方，不影响继续操作。

---

## 报告与演示

- **技术栈**：Hugging Face Transformers、PyTorch、Gradio；后端单步接口见 `game.engine.step` / `reset_session`。
- **运行方式**：在项目根执行 `python app_gradio.py` 或 `./scripts/run_app.sh`，浏览器打开指定 URL。
- **演示可复现**：使用「新游戏」回到固定起始状态；若已配置 `DEMO_SEED`，演示前设置该环境变量即可。
