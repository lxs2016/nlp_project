"""StoryWeaver Gradio UI: single entry for System implementation.
Run from project root: python app_gradio.py
Optional: PORT=8080 python app_gradio.py
"""
from __future__ import annotations

import os
import uuid
from difflib import SequenceMatcher
from pathlib import Path

# Load .env from project root so OPENAI_API_KEY is available for the engine/generator
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except Exception:
    pass

import gradio as gr

from game.config import load_world_bible
from game.engine import reset_session, step_with_metrics

# Intro: 【背景】+ setting only (no "点击开始"); used after game has started
def _intro_body() -> str:
    try:
        world = load_world_bible()
        setting = (world.get("setting") or "").strip()
        if setting:
            return f"**【背景】**\n\n{setting}"
    except Exception:
        pass
    return ""


# Initial screen: intro + prompt to start
def _initial_narrative() -> str:
    body = _intro_body()
    if body:
        return f"{body}\n\n---\n\n点击「开始」开始游戏。"
    return "点击「开始」开始游戏。"


INITIAL_NARRATIVE = _initial_narrative()
INTRO_BODY = _intro_body() or "**【背景】**"
INITIAL_STATE = "—"
INITIAL_EVAL_DISPLAY = "**性能评估**：点击「结束游戏」后自动生成。"

# 通用 fallback 句，出现时只追加反馈、不再重复这句
FALLBACK_LINE = "你站在当前场景中，需要做出选择。"


def _ensure_session(session_id: str | None) -> str:
    if session_id is None or session_id == "":
        return str(uuid.uuid4())
    return session_id


def _normalize_text(text: str) -> str:
    s = (text or "").strip().lower()
    return " ".join(s.split())


def _choice_match_ratio(user_input: str, offered_choices: list[str]) -> float:
    if not offered_choices:
        return 0.0
    u = _normalize_text(user_input)
    if not u:
        return 0.0
    return max(
        (SequenceMatcher(None, u, _normalize_text(c)).ratio() for c in offered_choices),
        default=0.0,
    )


def _new_eval_state() -> dict:
    return {
        "turn_count": 0,
        "response_times_ms": [],
        "consistency_hits": 0,
        "consistency_total": 0,
        "choice_match_hits": 0,
        "choice_match_total": 0,
        "total_input_chars": 0,
        "choice_click_turns": 0,
        "free_input_turns": 0,
        "last_choices": [],
    }


def _safe_div(n: float, d: float) -> float:
    return (n / d) if d else 0.0


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    idx = int(0.95 * (len(s) - 1))
    return float(s[idx])


def _update_eval_state(
    eval_state: dict | None,
    *,
    user_input: str,
    offered_choices: list[str],
    generated_choices: list[str],
    metrics: dict,
    is_free_input: bool,
) -> dict:
    st = dict(eval_state or _new_eval_state())
    st.setdefault("response_times_ms", [])
    st.setdefault("last_choices", [])

    st["turn_count"] = int(st.get("turn_count", 0)) + 1
    st["total_input_chars"] = int(st.get("total_input_chars", 0)) + len((user_input or "").strip())
    if is_free_input:
        st["free_input_turns"] = int(st.get("free_input_turns", 0)) + 1
    else:
        st["choice_click_turns"] = int(st.get("choice_click_turns", 0)) + 1

    timing = (metrics.get("timing_ms") or {}) if isinstance(metrics, dict) else {}
    total_ms = float(timing.get("total") or 0.0)
    st["response_times_ms"].append(total_ms)

    st["consistency_total"] = int(st.get("consistency_total", 0)) + 1
    if bool(metrics.get("consistency_passed", True)):
        st["consistency_hits"] = int(st.get("consistency_hits", 0)) + 1

    if offered_choices:
        st["choice_match_total"] = int(st.get("choice_match_total", 0)) + 1
        if _choice_match_ratio(user_input, offered_choices) >= 0.65:
            st["choice_match_hits"] = int(st.get("choice_match_hits", 0)) + 1

    st["last_choices"] = list(generated_choices or [])
    return st


def _format_eval_report(eval_state: dict | None) -> str:
    st = eval_state or {}
    turns = int(st.get("turn_count", 0))
    if turns <= 0:
        return "**性能评估**：暂无可评估的交互数据。"

    times = [float(x) for x in (st.get("response_times_ms") or [])]
    latency_mean = _safe_div(sum(times), len(times))
    latency_p95 = _p95(times)

    coherence = 100.0 * _safe_div(float(st.get("consistency_hits", 0)), float(st.get("consistency_total", 0)))
    choice_acc = 100.0 * _safe_div(float(st.get("choice_match_hits", 0)), float(st.get("choice_match_total", 0)))

    avg_input_len = _safe_div(float(st.get("total_input_chars", 0)), float(turns))
    engagement = min(100.0, turns * 12.0 + avg_input_len * 1.2)
    responsiveness = max(0.0, 100.0 - min(latency_mean / 40.0, 100.0))
    immersion = 0.35 * engagement + 0.25 * responsiveness + 0.20 * choice_acc + 0.20 * coherence

    if immersion >= 85:
        level = "非常满意"
    elif immersion >= 70:
        level = "满意"
    elif immersion >= 55:
        level = "一般"
    else:
        level = "待优化"

    return (
        "## 📊 本局性能评估\n\n"
        "| 指标 | 结果 | 说明 |\n"
        "|---|---:|---|\n"
        f"| 剧情连贯性评分 | **{coherence:.1f}/100** | 基于一致性检查通过率 |\n"
        f"| 生成响应时间（均值） | **{latency_mean:.1f} ms** | 单轮总耗时平均值 |\n"
        f"| 生成响应时间（P95） | **{latency_p95:.1f} ms** | 慢请求尾延迟 |\n"
        f"| 玩家选择匹配准确率 | **{choice_acc:.1f}%** | 玩家输入与系统候选动作的匹配率 |\n"
        f"| 沉浸式体验满意度 | **{immersion:.1f}/100（{level}）** | 结合参与度、响应速度、连贯性与匹配度估算 |\n\n"
        "### 交互统计\n"
        f"- 总交互轮次：**{turns}**\n"
        f"- 按钮选择轮次：**{int(st.get('choice_click_turns', 0))}**\n"
        f"- 自由输入轮次：**{int(st.get('free_input_turns', 0))}**\n"
    )


def _do_step(session_id: str, user_input: str) -> tuple[str, list[str], str, str, dict]:
    (narration, choices, state_summary, error_message), metrics = step_with_metrics(session_id, user_input or "开始")
    error_message = error_message or ""
    # 每次前端点击后打印后端返回
    print("\n" + "=" * 60)
    print("[后端返回] user_input:", repr(user_input or "开始"))
    print("[后端返回] narration:", repr(narration[:200] + ("..." if len(narration) > 200 else "")))
    print("[后端返回] choices:", choices)
    print("[后端返回] state_summary:", repr(state_summary))
    print("[后端返回] error_message:", repr(error_message))
    print("[后端返回] latency_ms:", round(float((metrics.get("timing_ms") or {}).get("total") or 0.0), 2))
    print("=" * 60 + "\n")
    return narration, choices, state_summary, error_message, metrics


def _choice_updates(choices: list[str], n_buttons: int = 4) -> list[dict]:
    """Return gr.update list for n_buttons: visible + value for first len(choices), visible=False for rest."""
    out = []
    for i in range(n_buttons):
        if i < len(choices):
            out.append(gr.update(visible=True, value=choices[i], interactive=True))
        else:
            out.append(gr.update(visible=False, value="", interactive=True))
    return out


def on_start_click(
    session_id: str | None,
    eval_state: dict | None,
) -> tuple:
    """Start game: create session, call step(session_id, '开始'), return UI updates. Keep intro and append first step."""
    sid = _ensure_session(session_id)
    narration, choices, state_summary, error_message, metrics = _do_step(sid, "开始")
    err_md = f"*{error_message}*" if error_message else ""
    choice_upds = _choice_updates(choices)
    eval_state = _new_eval_state()
    eval_state = _update_eval_state(
        eval_state,
        user_input="开始",
        offered_choices=[],
        generated_choices=choices,
        metrics=metrics,
        is_free_input=False,
    )

    first_page = f"{INTRO_BODY}\n\n---\n\n{narration or ''}"
    pages = [first_page]
    idx = 0
    nav, ind, p_btn, n_btn, goto_val = _update_pagination(pages, idx)

    return (
        sid,
        pages,
        idx,
        nav,
        ind,
        p_btn,
        n_btn,
        goto_val,
        state_summary or INITIAL_STATE,
        err_md,
        eval_state,
        INITIAL_EVAL_DISPLAY,
        "",  # clear free input
        *choice_upds,
        gr.update(visible=True),  # operations_group
        gr.update(visible=False), # start_btn_group
        gr.update(visible=False), # new_game_btn_group
        gr.update(visible=True),  # end_game_btn_group
    )
def _update_pagination(pages: list[str], idx: int) -> tuple:
    idx = max(0, min(idx, len(pages) - 1))
    nav = pages[idx]
    ind = f"{idx + 1} / {len(pages)}"
    return (
        nav,
        ind,
        gr.update(interactive=idx > 0),
        gr.update(interactive=idx < len(pages) - 1),
        gr.update(value=idx + 1, minimum=1, maximum=len(pages))  # 对应 goto_page，设置动态的翻页最大值
    )


def on_choice_click(
    session_id: str | None,
    choice_text: str,
    pages: list[str],
    eval_state: dict | None,
) -> tuple:
    """User clicked one of the choice buttons. choice_text is the button label."""
    sid = _ensure_session(session_id)
    offered_choices = list((eval_state or {}).get("last_choices") or [])
    narration, choices, state_summary, error_message, metrics = _do_step(sid, choice_text)
    err_md = f"*注意：{error_message}*" if error_message else ""
    feedback = f"> 你选择了「{choice_text}」。"
    eval_state = _update_eval_state(
        eval_state,
        user_input=choice_text,
        offered_choices=offered_choices,
        generated_choices=choices,
        metrics=metrics,
        is_free_input=False,
    )
    
    new_page = f"{feedback}\n\n{narration}"
    if pages is None:
        pages = []
    pages.append(new_page)
    idx = len(pages) - 1
    nav, ind, p_btn, n_btn, goto_val = _update_pagination(pages, idx)
    
    choice_upds = _choice_updates(choices)
    return (
        pages,
        idx,
        nav,
        ind,
        p_btn,
        n_btn,
        goto_val,
        state_summary or INITIAL_STATE,
        err_md,
        eval_state,
        gr.update(),
        "",  # clear free input
        *choice_upds,
    )


def on_free_input_submit(
    session_id: str | None,
    user_input: str,
    pages: list[str],
    eval_state: dict | None,
) -> tuple:
    """User submitted free text."""
    sid = _ensure_session(session_id)
    text = (user_input or "").strip() or "继续"
    offered_choices = list((eval_state or {}).get("last_choices") or [])
    narration, choices, state_summary, error_message, metrics = _do_step(sid, text)
    err_md = f"*注意：{error_message}*" if error_message else ""
    feedback = f"> 你输入了：{text}"
    eval_state = _update_eval_state(
        eval_state,
        user_input=text,
        offered_choices=offered_choices,
        generated_choices=choices,
        metrics=metrics,
        is_free_input=True,
    )
    
    new_page = f"{feedback}\n\n{narration}"
    if pages is None:
        pages = []
    pages.append(new_page)
    idx = len(pages) - 1
    nav, ind, p_btn, n_btn, goto_val = _update_pagination(pages, idx)
    
    choice_upds = _choice_updates(choices)
    return (
        pages,
        idx,
        nav,
        ind,
        p_btn,
        n_btn,
        goto_val,
        state_summary or INITIAL_STATE,
        err_md,
        eval_state,
        gr.update(),
        "",  # clear textbox
        *choice_upds,
    )


def on_new_game_click(session_id: str | None, eval_state: dict | None) -> tuple:
    """Reset session and show intro + first step again."""
    sid = _ensure_session(session_id)
    reset_session(sid)
    narration, choices, state_summary, error_message, metrics = _do_step(sid, "开始")
    err_md = f"*{error_message}*" if error_message else ""
    choice_upds = _choice_updates(choices)
    eval_state = _new_eval_state()
    eval_state = _update_eval_state(
        eval_state,
        user_input="开始",
        offered_choices=[],
        generated_choices=choices,
        metrics=metrics,
        is_free_input=False,
    )

    first_page = f"{INTRO_BODY}\n\n---\n\n{narration or ''}"
    pages = [first_page]
    idx = 0
    nav, ind, p_btn, n_btn, goto_val = _update_pagination(pages, idx)

    return (
        pages,
        idx,
        nav,
        ind,
        p_btn,
        n_btn,
        goto_val,
        state_summary or INITIAL_STATE,
        err_md,
    eval_state,
    INITIAL_EVAL_DISPLAY,
        gr.update(value="", visible=True),  # free_input
        *choice_upds,
        sid,
        gr.update(visible=True),  # operations_group
    gr.update(visible=False), # start_btn_group
    gr.update(visible=False), # new_game_btn_group
    gr.update(visible=True),  # end_game_btn_group
    )

def on_end_game_click(pages: list[str], current_idx: int, eval_state: dict | None) -> tuple:
    if not isinstance(pages, list) or not pages:
        pages = [INITIAL_NARRATIVE]

    try:
        idx = int(current_idx)
    except (TypeError, ValueError):
        idx = len(pages) - 1
    idx = max(0, min(idx, len(pages) - 1))

    # Keep the pages as they are, just update pagination based on current_idx
    nav, ind, p_btn, n_btn, goto_val = _update_pagination(pages, idx)
    eval_report = _format_eval_report(eval_state)

    choice_upds = [gr.update(visible=False, value="")] * 4

    return (
        pages,
        idx,
        nav,
        ind,
        p_btn,
        n_btn,
        goto_val,
        "**游戏已结束**。您可以通过分页继续查看历史剧情。",
        "",                                   # error_display
        eval_state or _new_eval_state(),
        eval_report,
        gr.update(value="", visible=False),   # free_input
        *choice_upds,
        None,                                   # session_id (doesn't matter)
        gr.update(visible=False),               # operations_group
        gr.update(visible=False),               # start_btn_group
        gr.update(visible=True),                # new_game_btn_group
        gr.update(visible=False),               # end_game_btn_group
    )
def on_prev_click(pages: list[str], idx: int) -> tuple:
    if pages is None: pages = [INITIAL_NARRATIVE]
    idx = max(0, idx - 1)
    nav, ind, p_btn, n_btn, goto_val = _update_pagination(pages, idx)
    return idx, nav, ind, p_btn, n_btn, goto_val


def on_next_click(pages: list[str], idx: int) -> tuple:
    if pages is None: pages = [INITIAL_NARRATIVE]
    idx = min(len(pages) - 1, idx + 1)
    nav, ind, p_btn, n_btn, goto_val = _update_pagination(pages, idx)
    return idx, nav, ind, p_btn, n_btn, goto_val


def on_goto_submit(pages: list[str], target_page: float) -> tuple:
    """Handle jumping to a specific page number."""
    if pages is None: pages = [INITIAL_NARRATIVE]
    try:
        # Convert target_page to int (Gradio Number sends float) and to 0-based index
        idx = int(target_page) - 1
    except (TypeError, ValueError):
        idx = 0
    idx = max(0, min(idx, len(pages) - 1))
    nav, ind, p_btn, n_btn, goto_val = _update_pagination(pages, idx)
    return idx, nav, ind, p_btn, n_btn, goto_val


GAME_INSTRUCTIONS = """
**游戏说明**
- **开始**：点击「开始」进入故事，系统会给出当前场景与选项。
- **推进剧情**：点击下方 2～4 个选项按钮之一，或在「自由输入」中输入行动后点击「提交」。
- **当前状态**：显示你所在地点与携带物品，随剧情更新。
- **新游戏**：点击「新游戏」重置进度，从世界观开头重新玩。
"""


def build_ui() -> gr.Blocks:
    css = r"""
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Noto+Serif+SC:wght@500;700&display=swap');

    :root {
      --sw-bg-global: #f8f5f0;
      --sw-bg-card: #ffffff;
      --sw-bg-module: #fdfcfb;
      --sw-text: #333333;
      --sw-text-muted: #666666;
      --sw-border: #e2ddd5;
      --sw-accent: #f27a38;
      --sw-accent-hover: #e06b2e;
      --sw-danger: #ff6b6b;
      --sw-radius: 8px;
      --sw-shadow: 0 4px 16px rgba(0, 0, 0, 0.04);
      --sw-shadow-hover: 0 6px 20px rgba(0, 0, 0, 0.08);
    }

    body, .gradio-container {
      background: var(--sw-bg-global) !important;
      color: var(--sw-text) !important;
      font-family: 'Inter', sans-serif !important;
      scroll-behavior: smooth;
    }

    .gradio-container { max-width: 1100px !important; }

    /* Animations */
    @keyframes fadeInUp {
      from { opacity: 0; transform: translateY(15px); }
      to { opacity: 1; transform: translateY(0); }
    }

    /* Top Nav */
    #swNav {
      background: var(--sw-bg-card) !important;
      padding: 16px 24px !important;
      border-radius: var(--sw-radius) !important;
      box-shadow: 0 2px 8px rgba(0,0,0,0.04) !important;
      margin-bottom: 20px !important;
      display: flex;
      align-items: center;
      gap: 16px;
      border: 1px solid var(--sw-border) !important;
    }
    #swNav h2 { 
      margin: 0; 
      font-family: 'Noto Serif SC', '思源宋体', serif; 
      color: var(--sw-accent); 
      font-size: 26px; 
      font-weight: 700; 
    }
    #swNav p { 
      color: var(--sw-text-muted); 
      font-size: 15px; 
      margin: 0; 
      margin-top: 6px;
    }

    /* Cards */
    .swCard {
      background: var(--sw-bg-card) !important;
      border: 1px solid var(--sw-border) !important;
      border-radius: var(--sw-radius) !important;
      box-shadow: var(--sw-shadow) !important;
      animation: fadeInUp 0.6s ease forwards;
    }

    /* Narrative */
    #swNarrative { padding: 40px 48px !important; box-sizing: border-box !important; }
    #swNarrative .prose { padding: 0 !important; margin: 0 auto !important; max-width: 100% !important; }
    #swNarrative p, #swNarrative li {
      font-family: 'Inter', sans-serif;
      font-size: 16px;
      line-height: 1.8;
      margin-bottom: 1.2em;
      color: var(--sw-text);
      text-align: justify;
    }
    #swNarrative strong {
      color: var(--sw-accent);
      font-weight: 600;
      font-size: 1.05em;
    }
    #swNarrative hr { border-color: var(--sw-border); margin: 24px 0; }

    /* Right panel */
    #swPanel { padding: 20px; }
    #swPanel label span { color: var(--sw-text-muted); font-size: 0.9rem; }
    
    /* Accordion headers */
    .gradio-accordion .label-wrap {
      font-family: 'Noto Serif SC', '思源宋体', serif !important;
      font-weight: 700 !important;
      font-size: 1.15em !important;
      color: var(--sw-accent) !important;
      transition: color 0.3s;
    }
    .gradio-accordion .icon { transition: transform 0.3s ease; }

    /* Input boxes */
    textarea, input[type="text"] {
      border-radius: var(--sw-radius) !important;
      border: 1px solid var(--sw-border) !important;
      background: #ffffff !important;
      transition: all 0.3s ease !important;
    }
    textarea:focus, input[type="text"]:focus {
      border-color: var(--sw-accent) !important;
      box-shadow: 0 0 0 2px rgba(242, 122, 56, 0.15) !important;
    }
    textarea::placeholder { animation: pulse 2s infinite; }
    @keyframes pulse {
      0% { opacity: 0.5; }
      50% { opacity: 0.9; }
      100% { opacity: 0.5; }
    }
    
    /* Custom Input Row (Submit inline) */
    #swInputRow {
      display: flex !important;
      align-items: stretch !important;
      gap: 12px !important;
      margin-top: 24px !important;
      margin-bottom: 0 !important;
    }
    #swInputRow > div:first-child { 
      flex-grow: 1 !important; 
      margin: 0 !important; 
    }
    #swInputRow > div:first-child textarea {
      height: 100px !important;
      min-height: 100px !important; 
      max-height: 100px !important; 
      font-size: 1.05em !important;
      overflow-y: auto !important; 
      resize: none !important;
    }
    #swSubmitBtn {
      border-radius: var(--sw-radius) !important;
      background: var(--sw-accent) !important;
      color: #fff !important;
      border: 0 !important;
      font-weight: 600 !important;
      padding: 0 16px !important;
      min-width: 80px !important;
      max-width: 80px !important;
      flex-shrink: 0 !important;
      /* 固定高度，并取消拉伸对齐，改为底部对齐 */
      height: 48px !important;
      align-self: flex-end !important;
      transition: background 0.2s !important;
    }
    #swSubmitBtn:hover { background: var(--sw-accent-hover) !important; }

    /* Buttons */
    .swChoice {
      width: 100% !important;
    }
    .swChoice button {
      border-radius: var(--sw-radius) !important;
      border: 1px solid var(--sw-border) !important;
      background: #ffffff !important;
      color: var(--sw-text) !important;
      padding: 16px !important;
      margin-bottom: 12px !important;
      transition: all 0.2s ease !important;
      box-shadow: 0 2px 4px rgba(0,0,0,0.02) !important;
      text-align: center !important;
      white-space: normal !important;
      line-height: 1.4 !important;
      width: 100% !important;
      font-weight: 500 !important;
    }
    .swChoice button:hover { 
      transform: translateY(-2px) !important; 
      box-shadow: var(--sw-shadow-hover) !important; 
      border-color: var(--sw-accent) !important; 
      color: var(--sw-accent) !important;
      background: #fffaf7 !important;
    }

    #swStart {
      background: var(--sw-accent) !important;
      color: #fff !important;
      border-radius: var(--sw-radius) !important;
      border: 0 !important;
      font-weight: 600 !important;
      font-size: 1.1em !important;
      padding: 14px !important;
      margin-bottom: 16px !important;
      transition: background 0.2s !important;
    }
    #swStart:hover { background: var(--sw-accent-hover) !important; }

    #swNewGame, #swEndGame {
      border-radius: var(--sw-radius) !important;
      border: none !important;
      background: var(--sw-accent) !important;
      color: #ffffff !important;
      font-weight: 600 !important;
      padding: 12px 0 !important;
      transition: all 0.3s;
      width: 100% !important;
    }
    #swNewGame {
      margin-bottom: 10px !important;
    }
    #swEndGame {
      margin-bottom: 20px !important;
    }
    #swNewGame:hover, #swEndGame:hover {
      background: var(--sw-accent-hover) !important;
      transform: translateY(-1px) !important;
      box-shadow: 0 4px 12px rgba(242, 122, 56, 0.25) !important;
    }
    #swNewGame:hover::before {
      content: "↺ ";
      display: inline-block;
      animation: spin 1s linear infinite;
    }
    #swEndGame:hover::before {
      content: "⏹ ";
      display: inline-block;
    }
    @keyframes spin { 100% { transform: rotate(360deg); } }

    /* Modules Separation */
    #swOperations {
      background: var(--sw-bg-module) !important;
      border-radius: var(--sw-radius) !important;
      padding: 20px !important;
      margin-bottom: 20px !important;
      border: 1px solid var(--sw-border) !important;
    }
    
    .swDivider {
      border: none !important;
      height: 1px !important;
      background: var(--sw-border) !important;
      margin: 24px 0 !important;
    }

    /* State Display */
    #swState textarea {
      background: rgba(0,0,0,0.02) !important;
      box-shadow: inset 0 2px 5px rgba(0,0,0,0.03) !important;
      border-radius: 8px !important;
      padding: 12px !important;
    }

    /* Footer */
    #swFooter {
      text-align: center;
      padding: 24px 0 12px 0;
      color: var(--sw-text-muted);
      font-size: 0.85em;
      margin-top: 40px;
    }

    /* Pagination */
    #swPagination {
      margin-top: 12px;
      align-items: center;
      justify-content: space-between;
      display: flex;
      gap: 8px;
    }
    #swPagination button {
      flex-grow: 0 !important;
      min-width: 80px !important;
      background: var(--sw-bg-card) !important;
      border: 1px solid var(--sw-border) !important;
      color: var(--sw-text) !important;
      border-radius: 8px !important;
      transition: all 0.2s ease !important;
    }
    #swPagination button:hover:not(:disabled) {
      border-color: var(--sw-accent) !important;
      color: var(--sw-accent) !important;
    }
    #swPageInd {
      text-align: center;
      color: var(--sw-text-muted);
      font-size: 14px;
      flex-grow: 1;
      margin: 0;
    }
    #swGoto {
      min-width: 60px !important;
      max-width: 80px !important;
    }
    #swGoto input {
      text-align: center !important;
    }

    .err { color: var(--sw-danger); font-size: 0.92em; }
    """

    # Gradio 6+ moved `css` from Blocks() to launch(); we attach it to the app
    # so both local `python app_gradio.py` and Spaces `app.py` can pass it at launch.
    with gr.Blocks(title="StoryWeaver") as app:
        session_id = gr.State(value=None)
        story_pages = gr.State(value=[INITIAL_NARRATIVE])
        current_page_idx = gr.State(value=0)
        eval_state = gr.State(value=_new_eval_state())

        with gr.Row(elem_id="swNav"):
            gr.Markdown("## StoryWeaver <br><p>一个轻量的互动叙事试玩</p>")

        with gr.Tabs():
            with gr.Tab("开始游戏", id="play"):
                with gr.Row(equal_height=True):
                    with gr.Column(scale=6):
                        narrative = gr.Markdown(
                            value=INITIAL_NARRATIVE,
                            elem_id="swNarrative",
                            elem_classes=["swCard"],
                        )
                        with gr.Row(elem_id="swPagination"):
                            prev_btn = gr.Button("上一页", interactive=False, size="sm")
                            page_indicator = gr.Markdown("**1 / 1**", elem_id="swPageInd")
                            jump_btn = gr.Button("跳转", elem_id="swJumpBtn", size="sm")
                            goto_page = gr.Number(
                                value=1,
                                minimum=1,
                                maximum=1,
                                label="", 
                                show_label=False, 
                                elem_id="swGoto", 
                                precision=0,
                                container=False
                            )
                            next_btn = gr.Button("下一页", interactive=False, size="sm")

                    with gr.Column(scale=4):
                        with gr.Group(elem_id="swPanel", elem_classes=["swCard"]):

                            with gr.Group(visible=False) as new_game_btn_group:
                                new_game_btn = gr.Button("新游戏", elem_id="swNewGame", visible=True)
                            with gr.Group(visible=False) as end_game_btn_group:
                                end_game_btn = gr.Button("结束游戏", elem_id="swEndGame", visible=True)

                            # Start: user clicks to get first narration (no session yet)
                            with gr.Group(visible=True) as start_btn_group:
                                start_btn = gr.Button("开始", variant="primary", elem_id="swStart", visible=True)

                            with gr.Group(elem_id="swOperations", visible=False) as operations_group:
                                # Choice buttons
                                choice_1 = gr.Button(value="—", visible=False, elem_classes=["swChoice"])
                                choice_2 = gr.Button(value="—", visible=False, elem_classes=["swChoice"])
                                choice_3 = gr.Button(value="—", visible=False, elem_classes=["swChoice"])
                                choice_4 = gr.Button(value="—", visible=False, elem_classes=["swChoice"])
                                choice_buttons = [choice_1, choice_2, choice_3, choice_4]

                                with gr.Row(elem_id="swInputRow"):
                                    free_input = gr.Textbox(
                                        placeholder="输入行动，例如：观察、交谈、调查、前往某地…",
                                        label="自定义行动",
                                        container=True,  # Set to True to show label, False to hide label entirely
                                    )
                                    submit_btn = gr.Button("提交", elem_id="swSubmitBtn")

                            gr.HTML("<hr class='swDivider'>")

                            with gr.Accordion("状态与提示", open=False):
                                state_display = gr.Textbox(
                                    value=INITIAL_STATE,
                                    label="🗺️ 地点 & 🎒 物品 (当前状态)",
                                    interactive=False,
                                    lines=3,
                                    elem_id="swState",
                                )
                                error_display = gr.Markdown(value="", elem_classes=["err"])
                                eval_display = gr.Markdown(value=INITIAL_EVAL_DISPLAY)

                with gr.Accordion("游戏说明（可折叠）", open=False):
                    gr.Markdown(GAME_INSTRUCTIONS)

            with gr.Tab("关于", id="about"):
                gr.Markdown(
                    "**StoryWeaver** 是一个基于世界观与当前状态动态生成叙述的互动小说试玩。"
                    "\n\n- 叙述来自 LLM（通过 `OPENAI_*` 环境变量配置）"
                    "\n- 意图识别/检索用于辅助规划与保持上下文一致性"
                )

        with gr.Row(elem_id="swFooter"):
            gr.Markdown("© 2026 StoryWeaver Team. Version 1.0.0 | [GitHub](#)")
        start_btn.click(
            fn=on_start_click,
            inputs=[session_id, eval_state],
            outputs=[
                session_id,
                story_pages,
                current_page_idx,
                narrative,
                page_indicator,
                prev_btn,
                next_btn,
                goto_page,
                state_display,
                error_display,
                eval_state,
                eval_display,
                free_input,
                choice_1,
                choice_2,
                choice_3,
                choice_4,
                operations_group,
                start_btn_group,
                new_game_btn_group,
                end_game_btn_group,
            ],
            api_name=False,
        )

        # Pagination clicks
        prev_btn.click(
            fn=on_prev_click,
            inputs=[story_pages, current_page_idx],
            outputs=[current_page_idx, narrative, page_indicator, prev_btn, next_btn, goto_page],
            api_name=False,
        )
        next_btn.click(
            fn=on_next_click,
            inputs=[story_pages, current_page_idx],
            outputs=[current_page_idx, narrative, page_indicator, prev_btn, next_btn, goto_page],
            api_name=False,
        )
        goto_page.submit(
            fn=on_goto_submit,
            inputs=[story_pages, goto_page],
            outputs=[current_page_idx, narrative, page_indicator, prev_btn, next_btn, goto_page],
            api_name=False,
        )
        jump_btn.click(
            fn=on_goto_submit,
            inputs=[story_pages, goto_page],
            outputs=[current_page_idx, narrative, page_indicator, prev_btn, next_btn, goto_page],
            api_name=False,
        )

        # Choice clicks: each button sends its label as user_input (btn value passed via inputs)
        for btn in choice_buttons:
            btn.click(
                fn=lambda sid, btn_val, pages, ev: on_choice_click(sid, btn_val, pages, ev),
                inputs=[session_id, btn, story_pages, eval_state],
                outputs=[
                    story_pages,
                    current_page_idx,
                    narrative,
                    page_indicator,
                    prev_btn,
                    next_btn,
                    goto_page,
                    state_display,
                    error_display,
                    eval_state,
                    eval_display,
                    free_input,
                    choice_1,
                    choice_2,
                    choice_3,
                    choice_4,
                ],
                api_name=False,
            )

        # Free input submit
        def on_submit(sid, inp, pages, ev):
            return on_free_input_submit(sid, inp, pages, ev)

        submit_btn.click(
            fn=on_submit,
            inputs=[session_id, free_input, story_pages, eval_state],
            outputs=[
                story_pages,
                current_page_idx,
                narrative,
                page_indicator,
                prev_btn,
                next_btn,
                goto_page,
                state_display,
                error_display,
                eval_state,
                eval_display,
                free_input,
                choice_1,
                choice_2,
                choice_3,
                choice_4,
            ],
            api_name=False,
        )
        free_input.submit(
            fn=on_submit,
            inputs=[session_id, free_input, story_pages, eval_state],
            outputs=[
                story_pages,
                current_page_idx,
                narrative,
                page_indicator,
                prev_btn,
                next_btn,
                goto_page,
                state_display,
                error_display,
                eval_state,
                eval_display,
                free_input,
                choice_1,
                choice_2,
                choice_3,
                choice_4,
            ],
            api_name=False,
        )

        # New game
        new_game_btn.click(
            fn=on_new_game_click,
            inputs=[session_id, eval_state],
            outputs=[
                story_pages,
                current_page_idx,
                narrative,
                page_indicator,
                prev_btn,
                next_btn,
                goto_page,
                state_display,
                error_display,
                eval_state,
                eval_display,
                free_input,
                choice_1,
                choice_2,
                choice_3,
                choice_4,
                session_id,
                operations_group,
                start_btn_group,
                new_game_btn_group,
                end_game_btn_group,
            ],
            api_name=False,
        )

        end_game_btn.click(
            fn=on_end_game_click,
            inputs=[story_pages, current_page_idx, eval_state],
            outputs=[
                story_pages,
                current_page_idx,
                narrative,
                page_indicator,
                prev_btn,
                next_btn,
                goto_page,
                state_display,
                error_display,
                eval_state,
                eval_display,
                free_input,
                choice_1,
                choice_2,
                choice_3,
                choice_4,
                session_id,
                operations_group,
                start_btn_group,
                new_game_btn_group,
                end_game_btn_group,
            ],
            api_name=False,
        )

    setattr(app, "_storyweaver_css", css)
    return app


def main() -> None:
    app = build_ui()
    port = int(os.environ.get("PORT", "7860"))
    app.launch(
        server_name="0.0.0.0",
        server_port=port,
        css=getattr(app, "_storyweaver_css", None),
    )


if __name__ == "__main__":
    main()
