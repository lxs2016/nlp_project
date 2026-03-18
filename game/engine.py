"""GameEngine: single entry point step(session_id, user_input) -> narration, choices, state_summary, error_message."""
from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
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


@dataclass(frozen=True)
class StepOptions:
    """Optional switches for evaluation/ablation without changing UI behavior."""

    disable_retrieve: bool = False
    disable_consistency: bool = False
    rule_only_choices: bool = False
    retrieve_k: int = 5
    retrieve_recent_n: int = 3
    max_consistency_attempts: int = 3


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


def _step_impl(
    session_id: str,
    user_input: str,
    *,
    options: StepOptions,
    return_metrics: bool,
) -> tuple[str, list[str], str, str, dict[str, Any] | None]:
    """
    Single step: process user_input.
    Returns (narration, choices, state_summary, error_message, metrics_or_none).
    error_message is non-empty only on failure or fallback.
    """
    t0_total = perf_counter()
    state, memory = _get_or_create_session(session_id)
    t_after_session = perf_counter()
    world = _get_world()
    t_after_world = perf_counter()
    intent_model = _get_intent_model()
    t_after_intent_model = perf_counter()

    user_input = (user_input or "").strip() or "继续"
    t0_intent = perf_counter()
    intent, _ = intent_model.predict(user_input)
    t_after_intent = perf_counter()

    t0_state_summary = perf_counter()
    state_summary = state.to_prompt_summary()
    t_after_state_summary = perf_counter()

    t0_retrieve = perf_counter()
    if options.disable_retrieve:
        retrieved = ""
    else:
        retrieved = retrieve_memory(
            memory,
            state_summary,
            intent,
            k=max(0, int(options.retrieve_k)),
            recent_n=max(0, int(options.retrieve_recent_n)),
        )
    t_after_retrieve = perf_counter()

    main_conflict = (world.get("main_conflict") or "").strip()[:200]
    t0_plan = perf_counter()
    plan_text, suggested_choices = plan_step(
        state_summary, intent, retrieved, main_conflict
    )
    t_after_plan = perf_counter()

    narration = ""
    choices = []
    state_updates = {}
    error_message = ""
    passed = True
    reason = ""
    attempt = 0
    downgraded_choices = False

    max_attempts = max(1, int(options.max_consistency_attempts))
    t_generate_total = 0.0
    t_consistency_total = 0.0
    for attempt in range(max_attempts):
        t0_generate = perf_counter()
        narration, choices, state_updates = generate_narration(
            world=world,
            state_summary=state_summary,
            retrieved_context=retrieved,
            plan_text=plan_text,
            suggested_choices=suggested_choices,
            user_input=user_input,
            max_retries=1,
        )
        t_after_generate = perf_counter()
        t_generate_total += t_after_generate - t0_generate

        if options.rule_only_choices:
            # Keep generator narration/state_updates, but force choices to planner suggestions for ablation.
            choices = list(suggested_choices[:4])

        if options.disable_consistency:
            passed, reason = True, ""
            break

        t0_consistency = perf_counter()
        passed, reason = consistency_check(state, narration, state_updates)
        t_after_consistency = perf_counter()
        t_consistency_total += t_after_consistency - t0_consistency

        if passed:
            break
        if attempt >= max_attempts - 1:
            error_message = reason or "一致性检查未通过，已使用当前输出。"
            if len(choices) > 2:
                choices = choices[:2]
                downgraded_choices = True
            break

    t0_state_apply = perf_counter()
    state.apply_state_updates(state_updates)
    t_after_state_apply = perf_counter()

    t0_memory = perf_counter()
    events = state_updates.get("recent_events") or []
    if isinstance(events, list) and events:
        for ev in events[:2]:
            memory.append(str(ev), state.turn_id, state.current_location, state.characters_met)
    elif narration:
        memory.append(narration[:150], state.turn_id, state.current_location, state.characters_met)
    t_after_memory = perf_counter()

    state_summary_out = state.state_summary()
    t1_total = perf_counter()

    metrics: dict[str, Any] | None = None
    if return_metrics:
        metrics = {
            "intent": intent,
            "attempts": int(attempt) + 1,
            "consistency_passed": bool(passed),
            "consistency_reason": (reason or "") if not passed else "",
            "choices_downgraded": bool(downgraded_choices),
            "timing_ms": {
                "total": (t1_total - t0_total) * 1000.0,
                "session_get_or_create": (t_after_session - t0_total) * 1000.0,
                "world_get": (t_after_world - t_after_session) * 1000.0,
                "intent_model_get": (t_after_intent_model - t_after_world) * 1000.0,
                "intent_predict": (t_after_intent - t0_intent) * 1000.0,
                "state_summary": (t_after_state_summary - t0_state_summary) * 1000.0,
                "retrieve": (t_after_retrieve - t0_retrieve) * 1000.0,
                "plan": (t_after_plan - t0_plan) * 1000.0,
                "generate_total": t_generate_total * 1000.0,
                "consistency_total": t_consistency_total * 1000.0,
                "state_apply": (t_after_state_apply - t0_state_apply) * 1000.0,
                "memory_append": (t_after_memory - t0_memory) * 1000.0,
            },
            "options": {
                "disable_retrieve": bool(options.disable_retrieve),
                "disable_consistency": bool(options.disable_consistency),
                "rule_only_choices": bool(options.rule_only_choices),
                "retrieve_k": int(options.retrieve_k),
                "retrieve_recent_n": int(options.retrieve_recent_n),
                "max_consistency_attempts": int(options.max_consistency_attempts),
            },
        }
    return narration, choices, state_summary_out, error_message, metrics


def step(
    session_id: str,
    user_input: str,
) -> tuple[str, list[str], str, str]:
    """
    UI-friendly step: returns (narration, choices, state_summary, error_message).
    """
    narration, choices, state_summary_out, error_message, _ = _step_impl(
        session_id,
        user_input,
        options=StepOptions(),
        return_metrics=False,
    )
    return narration, choices, state_summary_out, error_message


def step_with_metrics(
    session_id: str,
    user_input: str,
    *,
    options: StepOptions | None = None,
) -> tuple[tuple[str, list[str], str, str], dict[str, Any]]:
    """
    Evaluation-only step that returns both the UI result and a metrics dict.
    Does not change default UI behavior.
    """
    narration, choices, state_summary_out, error_message, metrics = _step_impl(
        session_id,
        user_input,
        options=options or StepOptions(),
        return_metrics=True,
    )
    assert metrics is not None
    return (narration, choices, state_summary_out, error_message), metrics
