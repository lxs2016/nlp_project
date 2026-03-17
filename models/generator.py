"""Generator: build prompt from WorldBible + state + memory + plan + user_input, call LLM, parse JSON."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
# Load .env from project root so OPENAI_API_KEY etc. are available
_env_path = _PROJECT_ROOT / ".env"
if _env_path.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_path)
    except Exception:
        pass
_SYSTEM_PROMPT_PATH = _PROJECT_ROOT / "prompts" / "generator_system.txt"
_USER_PROMPT_PATH = _PROJECT_ROOT / "prompts" / "generator_user.txt"


def _load_template(path: Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def _format_world(world: dict[str, Any]) -> dict[str, str]:
    setting = (world.get("setting") or "").strip()
    main_conflict = (world.get("main_conflict") or "").strip()
    chars = world.get("characters") or []
    char_str = "\n".join(
        f"- {c.get('name', '')}: {c.get('role', '')} {c.get('traits', '')}"
        for c in chars if isinstance(c, dict)
    )
    locs = world.get("locations") or []
    loc_str = "\n".join(
        f"- {l.get('name', '')}: {l.get('desc', '')}"
        for l in locs if isinstance(l, dict)
    )
    rules = world.get("rules_forbidden") or []
    rules_str = "\n".join(f"- {r}" for r in rules)
    return {
        "setting": setting,
        "main_conflict": main_conflict,
        "characters": char_str,
        "locations": loc_str,
        "rules_forbidden": rules_str,
    }


# OpenRouter endpoint (OpenAI-compatible)
OPENROUTER_BASE = "https://openrouter.ai/api/v1"


def _call_llm(system: str, user: str) -> str:
    """Call LLM API if available (OpenAI or OpenRouter); otherwise return fallback JSON."""
    api_key = (
        os.environ.get("OPENROUTER_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("API_KEY")
    )
    if not api_key:
        print("[Generator] 未配置 API key (OPENAI_API_KEY / OPENROUTER_API_KEY)，使用 fallback。")
    elif api_key:
        try:
            from openai import OpenAI
            base_url = os.environ.get("OPENROUTER_API_BASE") or os.environ.get("OPENAI_API_BASE")
            if not base_url and os.environ.get("OPENROUTER_API_KEY"):
                base_url = OPENROUTER_BASE
            client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
            model = os.environ.get("OPENROUTER_MODEL") or os.environ.get("OPENAI_MODEL", "gpt-3.5-turbo")
            r = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=500,
            )
            if r.choices:
                return (r.choices[0].message.content or "").strip()
            print("[Generator] API 返回无 choices，使用 fallback。")
        except Exception as e:
            print("[Generator] LLM 调用异常，使用 fallback:", e)
    # Fallback: deterministic placeholder so pipeline runs
    return json.dumps({
        "narration": "你站在当前场景中，需要做出选择。",
        "choices": ["继续探索", "与角色交谈", "前往他处"],
        "state_updates": {"recent_events": ["玩家正在考虑下一步。"]},
    }, ensure_ascii=False)


def _extract_json(text: str) -> dict | None:
    """Try to parse JSON from model output (strip markdown code block if present)."""
    text = text.strip()
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def generate(
    world: dict[str, Any],
    state_summary: str,
    retrieved_context: str,
    plan_text: str,
    suggested_choices: list[str],
    user_input: str,
    max_retries: int = 2,
) -> tuple[str, list[str], dict[str, Any]]:
    """
    Return (narration, choices, state_updates). Retries on parse failure up to max_retries.
    """
    fmt = _format_world(world)
    system_tpl = _load_template(_SYSTEM_PROMPT_PATH)
    user_tpl = _load_template(_USER_PROMPT_PATH)
    system = system_tpl.format(**fmt)
    user = user_tpl.format(
        state_summary=state_summary or "无",
        retrieved_context=retrieved_context or "无",
        plan_text=plan_text or "无",
        suggested_choices="\n".join(suggested_choices) if suggested_choices else "无",
        user_input=user_input or "继续",
    )
    last_raw = ""
    for _ in range(max_retries + 1):
        raw = _call_llm(system, user)
        last_raw = raw
        parsed = _extract_json(raw)
        if parsed:
            narration = parsed.get("narration") or ""
            choices = parsed.get("choices")
            if isinstance(choices, list):
                choices = [str(c) for c in choices][:6]
            else:
                choices = ["继续", "离开"]
            state_updates = parsed.get("state_updates")
            if not isinstance(state_updates, dict):
                state_updates = {}
            return narration, choices, state_updates
    # Final fallback
    return (
        "故事继续。请从下方选项中选择。",
        ["继续探索", "与角色交谈"],
        {"recent_events": ["生成超时或解析失败，使用默认叙述。"]},
    )
