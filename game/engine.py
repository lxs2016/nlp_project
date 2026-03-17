"""GameEngine: single entry point step(session_id, user_input) -> narration, choices, state_summary, error_message."""
from __future__ import annotations

from typing import Any

from game.config import DIR_INTENT_MODEL, load_world_bible
from game.memory import Memory
from game.state import GameState
from models.consistency import check as consistency_check
from models.generator import generate as generate_narration
from models.intent import IntentRecognizer
from models.planner import plan as plan_step
from models.retriever import retrieve as retrieve_memory


# Session store: session_id -> (GameState, Memory)
_sessions: dict[str, tuple[GameState, Memory]] = {}
_world: dict[str, Any] | None = None
_intent_model: IntentRecognizer | None = None


def _get_world() -> dict[str, Any]:
    global _world
    if _world is None:
        _world = load_world_bible()
    return _world


def _get_intent_model() -> IntentRecognizer:
    global _intent_model
    if _intent_model is None:
        _intent_model = IntentRecognizer(DIR_INTENT_MODEL)
    return _intent_model


def _get_or_create_session(session_id: str) -> tuple[GameState, Memory]:
    if session_id in _sessions:
        return _sessions[session_id]
    world = _get_world()
    state = GameState.from_world_bible(world)
    memory = Memory()
    _sessions[session_id] = (state, memory)
    return state, memory


def reset_session(session_id: str) -> None:
    """Reset game for this session (new game)."""
    world = _get_world()
    state = GameState.from_world_bible(world)
    memory = Memory()
    _sessions[session_id] = (state, memory)


def step(
    session_id: str,
    user_input: str,
) -> tuple[str, list[str], str, str]:
    """
    Single step: process user_input, return (narration, choices, state_summary, error_message).
    error_message is non-empty only on failure or fallback.
    """
    state, memory = _get_or_create_session(session_id)
    world = _get_world()
    intent_model = _get_intent_model()

    user_input = (user_input or "").strip() or "继续"
    intent, _ = intent_model.predict(user_input)

    state_summary = state.to_prompt_summary()
    retrieved = retrieve_memory(memory, state_summary, intent, k=5, recent_n=3)
    main_conflict = (world.get("main_conflict") or "").strip()[:200]
    plan_text, suggested_choices = plan_step(
        state_summary, intent, retrieved, main_conflict
    )

    narration = ""
    choices = []
    state_updates = {}
    error_message = ""
    passed = True
    attempt = 0

    for attempt in range(3):
        narration, choices, state_updates = generate_narration(
            world=world,
            state_summary=state_summary,
            retrieved_context=retrieved,
            plan_text=plan_text,
            suggested_choices=suggested_choices,
            user_input=user_input,
            max_retries=1,
        )
        passed, reason = consistency_check(state, narration, state_updates)
        if passed:
            break
        if attempt >= 2:
            error_message = reason or "一致性检查未通过，已使用当前输出。"
            choices = choices[:2] if len(choices) > 2 else choices
            break

    state.apply_state_updates(state_updates)
    events = state_updates.get("recent_events") or []
    if isinstance(events, list) and events:
        for ev in events[:2]:
            memory.append(str(ev), state.turn_id, state.current_location, state.characters_met)
    elif narration:
        memory.append(narration[:150], state.turn_id, state.current_location, state.characters_met)

    state_summary_out = state.state_summary()
    return narration, choices, state_summary_out, error_message
