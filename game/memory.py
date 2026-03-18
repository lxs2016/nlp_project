"""Memory: event summaries with optional location/character tags for retrieval."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MemoryEntry:
    """Single memory entry."""
    summary: str
    turn_id: int
    location: str = ""
    characters: list[str] = field(default_factory=list)


class Memory:
    """Runtime memory list: append summaries, get recent N or full list for retriever."""

    def __init__(self, max_entries: int = 100) -> None:
        self._entries: list[MemoryEntry] = []
        self._max_entries = max_entries

    def append(
        self,
        summary: str,
        turn_id: int,
        location: str = "",
        characters: list[str] | None = None,
    ) -> None:
        entry = MemoryEntry(
            summary=summary,
            turn_id=turn_id,
            location=location,
            characters=characters or [],
        )
        self._entries.append(entry)
        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries :]

    def recent_n(self, n: int) -> list[str]:
        """Last N summaries in order (oldest first in returned list)."""
        take = self._entries[-n:] if n > 0 else []
        return [e.summary for e in take]

    def recent_n_entries(self, n: int) -> list[MemoryEntry]:
        return self._entries[-n:] if n > 0 else []

    def all_summaries(self) -> list[str]:
        return [e.summary for e in self._entries]

    def entries_for_retrieval(self) -> list[tuple[str, str, list[str]]]:
        """(summary, location, characters) for retriever encoding."""
        return [(e.summary, e.location, e.characters) for e in self._entries]

    def clear(self) -> None:
        self._entries.clear()
