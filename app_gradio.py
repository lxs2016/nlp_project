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
    with gr.Blocks(title="StoryWeaver", css=".err { color: #888; font-size: 0.9em; }") as app:
        session_id = gr.State(value=None)

        gr.Markdown("## StoryWeaver")
        with gr.Accordion("游戏说明", open=True):
            gr.Markdown(GAME_INSTRUCTIONS)
        narrative = gr.Markdown(value=INITIAL_NARRATIVE, label="叙述")
        with gr.Row():
            choice_1 = gr.Button(value="—", visible=False)
            choice_2 = gr.Button(value="—", visible=False)
            choice_3 = gr.Button(value="—", visible=False)
            choice_4 = gr.Button(value="—", visible=False)
        choice_buttons = [choice_1, choice_2, choice_3, choice_4]

        with gr.Row():
            free_input = gr.Textbox(
                placeholder="输入行动或选择上方按钮",
                label="自由输入",
                scale=4,
            )
            submit_btn = gr.Button("提交", scale=1)

        state_display = gr.Textbox(
            value=INITIAL_STATE,
            label="当前状态",
            interactive=False,
            lines=2,
        )
        error_display = gr.Markdown(value="", elem_classes=["err"])
        new_game_btn = gr.Button("新游戏")

        # Start: user clicks to get first narration (no session yet)
        start_btn = gr.Button("开始", variant="primary")
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
        ).then(
            fn=lambda: gr.update(visible=False),
            inputs=[],
            outputs=[start_btn],
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

    return app


def main() -> None:
    app = build_ui()
    port = int(os.environ.get("PORT", "7860"))
    app.launch(server_name="0.0.0.0", server_port=port)


if __name__ == "__main__":
    main()
