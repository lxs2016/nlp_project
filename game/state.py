"""GameState: structure, init from WorldBible, apply state_updates."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from game.config import load_world_bible


@dataclass
class GameState:
    """Current game state aligned with WorldBible entities."""

    current_location: str = ""
    characters_met: list[str] = field(default_factory=list)
    inventory: list[str] = field(default_factory=list)
    flags: dict[str, bool | str] = field(default_factory=dict)
    recent_events: list[str] = field(default_factory=list)
    turn_id: int = 0
    # Snapshot of world bible for rules/entities (no mutation)
    _world: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_world_bible(cls, world: dict[str, Any] | None = None) -> "GameState":
        """Initialize from WorldBible. If world is None, load from config path."""
        if world is None:
            world = load_world_bible()
        locations = world.get("locations") or []
        first_loc = locations[0].get("name", "石溪镇广场") if locations else "石溪镇广场"
        if isinstance(first_loc, dict):
            first_loc = first_loc.get("name", "石溪镇广场")
        return cls(
            current_location=first_loc,
            characters_met=[],
            inventory=[],
            flags={},
            recent_events=[],
            turn_id=0,
            _world=world,
        )

    def rules_forbidden(self) -> list[str]:
        return self._world.get("rules_forbidden") or []

    def character_names(self) -> list[str]:
        chars = self._world.get("characters") or []
        return [c.get("name", "") for c in chars if isinstance(c, dict)]

    def location_names(self) -> list[str]:
        locs = self._world.get("locations") or []
        return [l.get("name", "") for l in locs if isinstance(l, dict)]

    def key_items(self) -> list[str]:
        return list(self._world.get("key_items") or [])

    def apply_state_updates(self, updates: dict[str, Any] | None) -> None:
        """Apply generator output state_updates. Only known fields are updated."""
        if not updates:
            return
        if "location" in updates:
            self.current_location = str(updates["location"])
        if "current_location" in updates:
            self.current_location = str(updates["current_location"])
        if "inventory" in updates:
            inv = updates["inventory"]
            self.inventory = list(inv) if isinstance(inv, (list, tuple)) else [str(inv)]
        if "characters_met" in updates:
            cm = updates["characters_met"]
            self.characters_met = list(cm) if isinstance(cm, (list, tuple)) else [str(cm)]
        if "flags" in updates and isinstance(updates["flags"], dict):
            self.flags.update(updates["flags"])
        if "recent_events" in updates:
            ev = updates["recent_events"]
            if isinstance(ev, (list, tuple)):
                self.recent_events.extend(str(x) for x in ev)
            else:
                self.recent_events.append(str(ev))
        self.turn_id += 1

    def to_prompt_summary(self) -> str:
        """Short summary for planner/generator prompt."""
        parts = [
            f"当前地点: {self.current_location}",
            f"已遇见: {', '.join(self.characters_met) or '无'}",
            f"携带: {', '.join(self.inventory) or '无'}",
        ]
        if self.recent_events:
            parts.append(f"最近: {'; '.join(self.recent_events[-3:])}")
        return "\n".join(parts)

    def state_summary(self) -> str:
        """One-line summary for System API (Gradio state display)."""
        return f"地点: {self.current_location} | 携带: {', '.join(self.inventory) or '无'}"
