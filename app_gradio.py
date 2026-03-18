"""StoryWeaver Gradio UI: single entry for System implementation.
Run from project root: python app_gradio.py
Optional: PORT=8080 python app_gradio.py
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path

# Load .env from project root so OPENAI_API_KEY is available for the engine/generator
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except Exception:
    pass

import gradio as gr

from game.config import load_world_bible
from game.engine import reset_session, step

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

# 通用 fallback 句，出现时只追加反馈、不再重复这句
FALLBACK_LINE = "你站在当前场景中，需要做出选择。"


def _ensure_session(session_id: str | None) -> str:
    if session_id is None or session_id == "":
        return str(uuid.uuid4())
    return session_id


def _do_step(session_id: str, user_input: str) -> tuple[str, list[str], str, str]:
    narration, choices, state_summary, error_message = step(session_id, user_input or "开始")
    error_message = error_message or ""
    # 每次前端点击后打印后端返回
    print("\n" + "=" * 60)
    print("[后端返回] user_input:", repr(user_input or "开始"))
    print("[后端返回] narration:", repr(narration[:200] + ("..." if len(narration) > 200 else "")))
    print("[后端返回] choices:", choices)
    print("[后端返回] state_summary:", repr(state_summary))
    print("[后端返回] error_message:", repr(error_message))
    print("=" * 60 + "\n")
    return narration, choices, state_summary, error_message


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
) -> tuple:
    """Start game: create session, call step(session_id, '开始'), return UI updates. Keep intro and append first step."""
    sid = _ensure_session(session_id)
    narration, choices, state_summary, error_message = _do_step(sid, "开始")
    err_md = f"*{error_message}*" if error_message else ""
    choice_upds = _choice_updates(choices)
    # After start: show 【背景】+ first step only (no "点击开始" to avoid mess)
    full_narrative = _append_narrative(INTRO_BODY, narration or "")
    return (
        sid,
        full_narrative,
        state_summary or INITIAL_STATE,
        err_md,
        "",  # clear free input
        *choice_upds,
    )


def _append_narrative(current_narrative: str, narration: str) -> str:
    """Append narration; skip if identical to last segment to avoid duplicate display."""
    if not narration or not narration.strip():
        return current_narrative or narration
    if not current_narrative or not current_narrative.strip():
        return narration
    parts = current_narrative.split("\n\n---\n\n")
    last_segment = (parts[-1] or "").strip() if parts else ""
    if narration.strip() == last_segment:
        return current_narrative
    return f"{current_narrative}\n\n---\n\n{narration}"


def _append_narrative_with_feedback(
    current_narrative: str, narration: str, choice_feedback: str
) -> str:
    """Append narration; when duplicate or generic fallback, only append choice_feedback to avoid messy repeat."""
    if not choice_feedback:
        return _append_narrative(current_narrative, narration)
    # 若是通用 fallback 句，不再重复显示，只追加反馈
    if narration and narration.strip() == FALLBACK_LINE:
        return f"{current_narrative}\n\n---\n\n{choice_feedback}"
    appended = _append_narrative(current_narrative, narration)
    if appended == current_narrative:
        return f"{current_narrative}\n\n---\n\n{choice_feedback}"
    return appended


def on_choice_click(
    session_id: str | None,
    choice_text: str,
    current_narrative: str,
) -> tuple:
    """User clicked one of the choice buttons. choice_text is the button label."""
    sid = _ensure_session(session_id)
    narration, choices, state_summary, error_message = _do_step(sid, choice_text)
    err_md = f"*注意：{error_message}*" if error_message else ""
    feedback = f"你选择了「{choice_text}」。"
    new_narrative = _append_narrative_with_feedback(
        current_narrative, narration, feedback
    )
    choice_upds = _choice_updates(choices)
    return (
        new_narrative,
        state_summary or INITIAL_STATE,
        err_md,
        "",  # clear free input
        *choice_upds,
    )


def on_free_input_submit(
    session_id: str | None,
    user_input: str,
    current_narrative: str,
) -> tuple:
    """User submitted free text."""
    sid = _ensure_session(session_id)
    text = (user_input or "").strip() or "继续"
    narration, choices, state_summary, error_message = _do_step(sid, text)
    err_md = f"*注意：{error_message}*" if error_message else ""
    feedback = f"你输入了：{text}"
    new_narrative = _append_narrative_with_feedback(
        current_narrative, narration, feedback
    )
    choice_upds = _choice_updates(choices)
    return (
        new_narrative,
        state_summary or INITIAL_STATE,
        err_md,
        "",  # clear textbox
        *choice_upds,
    )


def on_new_game_click(session_id: str | None) -> tuple:
    """Reset session and show intro + first step again."""
    sid = _ensure_session(session_id)
    reset_session(sid)
    narration, choices, state_summary, error_message = _do_step(sid, "开始")
    err_md = f"*{error_message}*" if error_message else ""
    choice_upds = _choice_updates(choices)
    full_narrative = _append_narrative(INTRO_BODY, narration or "")
    return (
        full_narrative,
        state_summary or INITIAL_STATE,
        err_md,
        "",
        *choice_upds,
        sid,
    )


GAME_INSTRUCTIONS = """
**游戏说明**
- **开始**：点击「开始」进入故事，系统会给出当前场景与选项。
- **推进剧情**：点击下方 2～4 个选项按钮之一，或在「自由输入」中输入行动后点击「提交」。
- **当前状态**：显示你所在地点与携带物品，随剧情更新。
- **新游戏**：点击「新游戏」重置进度，从世界观开头重新玩。
"""


def build_ui() -> gr.Blocks:
    css = r"""
    @import url('https://fonts.googleapis.com/css2?family=Literata:opsz,wght@7..72,400;7..72,600&family=IBM+Plex+Mono:wght@400;500&display=swap');

    :root {
      --sw-bg0: #0b0f17;
      --sw-bg1: rgba(255, 255, 255, 0.05);
      --sw-bg2: rgba(255, 255, 255, 0.08);
      --sw-border: rgba(255, 255, 255, 0.10);
      --sw-text: rgba(255, 255, 255, 0.88);
      --sw-muted: rgba(255, 255, 255, 0.62);
      --sw-faint: rgba(255, 255, 255, 0.45);
      --sw-accent: #ffb86b;
      --sw-accent2: #6ee7ff;
      --sw-danger: #ff6b6b;
      --sw-radius: 16px;
      --sw-shadow: 0 18px 60px rgba(0,0,0,0.45);
    }

    body {
      background: radial-gradient(1200px 800px at 20% 10%, rgba(110,231,255,0.12), transparent 55%),
                  radial-gradient(900px 700px at 80% 40%, rgba(255,184,107,0.10), transparent 60%),
                  linear-gradient(180deg, var(--sw-bg0), #070a10);
      color: var(--sw-text);
    }

    /* Keep it centered & calm */
    .gradio-container { max-width: 1100px !important; }

    /* Title */
    #swTitle h2 { margin: 0.2rem 0 0.2rem 0; font-family: "Literata", ui-serif, Georgia, serif; letter-spacing: 0.2px; }
    #swSub { color: var(--sw-muted); font-size: 0.95rem; margin-top: 0.2rem; }

    /* Cards */
    .swCard {
      border: 1px solid var(--sw-border);
      background: linear-gradient(180deg, var(--sw-bg1), rgba(255,255,255,0.03));
      border-radius: var(--sw-radius);
      box-shadow: var(--sw-shadow);
    }

    /* Narrative */
    #swNarrative { padding: 14px 16px; }
    #swNarrative p, #swNarrative li { font-family: "Literata", ui-serif, Georgia, serif; font-size: 1.02rem; line-height: 1.65; }
    #swNarrative hr { border-color: rgba(255,255,255,0.10); }

    /* Right panel */
    #swPanel { padding: 14px 16px; }
    #swPanel label { color: var(--sw-faint); font-size: 0.85rem; }
    #swPanel textarea, #swPanel input { font-family: "IBM Plex Mono", ui-monospace, Menlo, monospace; }

    /* Buttons */
    .swChoice button {
      border-radius: 14px !important;
      border: 1px solid rgba(255,255,255,0.12) !important;
      background: rgba(255,255,255,0.06) !important;
      transition: transform 120ms ease, background 120ms ease, border-color 120ms ease;
      text-align: left !important;
      padding: 12px 12px !important;
      white-space: normal !important;
      line-height: 1.25 !important;
    }
    .swChoice button:hover { transform: translateY(-1px); background: rgba(255,255,255,0.09) !important; border-color: rgba(255,255,255,0.18) !important; }

    #swStart button {
      background: linear-gradient(90deg, rgba(255,184,107,0.95), rgba(110,231,255,0.85)) !important;
      color: #111 !important;
      border-radius: 999px !important;
      border: 0 !important;
      font-weight: 650 !important;
      padding: 10px 14px !important;
    }
    #swNewGame button {
      border-radius: 999px !important;
      border: 1px solid rgba(255,255,255,0.14) !important;
      background: rgba(255,255,255,0.06) !important;
    }

    .err { color: var(--sw-danger); font-size: 0.92em; }
    """

    # Gradio 6+ moved `css` from Blocks() to launch(); we attach it to the app
    # so both local `python app_gradio.py` and Spaces `app.py` can pass it at launch.
    with gr.Blocks(title="StoryWeaver") as app:
        session_id = gr.State(value=None)

        with gr.Row():
            gr.Markdown("## StoryWeaver", elem_id="swTitle")
            gr.Markdown("一个轻量的互动叙事试玩", elem_id="swSub")

        with gr.Tabs():
            with gr.Tab("开始游戏", id="play"):
                with gr.Row(equal_height=True):
                    with gr.Column(scale=7):
                        narrative = gr.Markdown(
                            value=INITIAL_NARRATIVE,
                            elem_id="swNarrative",
                            elem_classes=["swCard"],
                        )

                    with gr.Column(scale=5):
                        with gr.Group(elem_id="swPanel", elem_classes=["swCard"]):
                            # Start: user clicks to get first narration (no session yet)
                            start_btn = gr.Button("开始", variant="primary", elem_id="swStart")

                            with gr.Accordion("操作", open=True):
                                with gr.Row():
                                    free_input = gr.Textbox(
                                        placeholder="输入行动，例如：观察、交谈、调查、前往某地…",
                                        label="自由输入",
                                        scale=4,
                                    )
                                    submit_btn = gr.Button("提交", scale=1)

                                # Choice buttons
                                choice_1 = gr.Button(value="—", visible=False, elem_classes=["swChoice"])
                                choice_2 = gr.Button(value="—", visible=False, elem_classes=["swChoice"])
                                choice_3 = gr.Button(value="—", visible=False, elem_classes=["swChoice"])
                                choice_4 = gr.Button(value="—", visible=False, elem_classes=["swChoice"])
                                choice_buttons = [choice_1, choice_2, choice_3, choice_4]

                            with gr.Accordion("状态与提示", open=False):
                                state_display = gr.Textbox(
                                    value=INITIAL_STATE,
                                    label="当前状态",
                                    interactive=False,
                                    lines=3,
                                )
                                error_display = gr.Markdown(value="", elem_classes=["err"])

                            new_game_btn = gr.Button("新游戏", elem_id="swNewGame")

                with gr.Accordion("游戏说明（可折叠）", open=False):
                    gr.Markdown(GAME_INSTRUCTIONS)

            with gr.Tab("关于", id="about"):
                gr.Markdown(
                    "**StoryWeaver** 是一个基于世界观与当前状态动态生成叙述的互动小说试玩。"
                    "\n\n- 叙述来自 LLM（通过 `OPENAI_*` 环境变量配置）"
                    "\n- 意图识别/检索用于辅助规划与保持上下文一致性"
                )
        start_btn.click(
            fn=on_start_click,
            inputs=[session_id],
            outputs=[
                session_id,
                narrative,
                state_display,
                error_display,
                free_input,
                choice_1,
                choice_2,
                choice_3,
                choice_4,
            ],
            api_name=False,
        ).then(
            fn=lambda: gr.update(visible=False),
            inputs=[],
            outputs=[start_btn],
            api_name=False,
        )

        # Choice clicks: each button sends its label as user_input (btn value passed via inputs)
        for btn in choice_buttons:
            btn.click(
                fn=lambda sid, cur, btn_val: on_choice_click(sid, btn_val, cur),
                inputs=[session_id, narrative, btn],
                outputs=[
                    narrative,
                    state_display,
                    error_display,
                    free_input,
                    choice_1,
                    choice_2,
                    choice_3,
                    choice_4,
                ],
                api_name=False,
            )

        # Free input submit
        def on_submit(sid, inp, cur):
            return on_free_input_submit(sid, inp, cur)

        submit_btn.click(
            fn=on_submit,
            inputs=[session_id, free_input, narrative],
            outputs=[
                narrative,
                state_display,
                error_display,
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
            inputs=[session_id, free_input, narrative],
            outputs=[
                narrative,
                state_display,
                error_display,
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
            inputs=[session_id],
            outputs=[
                narrative,
                state_display,
                error_display,
                free_input,
                choice_1,
                choice_2,
                choice_3,
                choice_4,
                session_id,
            ],
        )
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
