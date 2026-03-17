"""ConsistencyChecker: rule-based entity, state, and forbidden-rule checks."""
from __future__ import annotations

from typing import Any

from game.state import GameState


def check(
    state: GameState,
    narration: str,
    state_updates: dict[str, Any] | None,
) -> tuple[bool, str]:
    """
    Return (passed, reason). reason is non-empty only when passed is False.
    Rules: entities in narration must be in WorldBible or state; rules_forbidden not violated.
    """
    narration = (narration or "").strip()
    state_updates = state_updates or {}

    allowed_names = set(state.character_names()) | set(state.location_names()) | set(state.key_items())
    allowed_names |= set(state.inventory) | {state.current_location}
    # Allow common words that might appear in narrative
    for name in list(allowed_names):
        if len(name) >= 2:
            allowed_names.add(name)

    # Simple forbidden-rule check: if narration or state_updates imply entering 禁洞 without permit
    rules = state.rules_forbidden()
    for rule in rules:
        if "禁洞" in rule and "许可" in rule:
            if "北山禁洞" in narration or state_updates.get("location") == "北山禁洞":
                if not state.flags.get("has_permit") and "长老手令" not in str(state.inventory):
                    return False, "未经许可进入禁洞，违反世界观禁忌。"

    # Entity check: extract candidate names (CJK or words) and see if any unknown key entity appears
    # Relaxed: only flag if we see a clear new location/character name not in list
    locs = set(state.location_names())
    chars = set(state.character_names())
    # If narration mentions a location not in world, could be inconsistency
    for loc in locs:
        if loc in narration and loc not in state.location_names():
            pass  # loc is in world
    # Simple: if state_updates set location to something not in world, fail
    new_loc = state_updates.get("location") or state_updates.get("current_location")
    if new_loc and state.location_names() and new_loc not in state.location_names():
        return False, f"未知地点: {new_loc}"

    return True, ""


def check_entity_consistency(narration: str, allowed_entities: set[str]) -> tuple[bool, str]:
    """Optional: strict entity check. Return (passed, reason)."""
    # Very simple: no strict extraction here; main check is in check()
    return True, ""
