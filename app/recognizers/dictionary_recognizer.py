from __future__ import annotations

from app.config.models import DictionaryEntry
from app.core.entities import Entity


class DictionaryRecognizer:
    def __init__(self, entries: list[DictionaryEntry]) -> None:
        self.entries = tuple(entry for entry in entries if entry.enabled)

    def analyze(self, text: str) -> list[Entity]:
        entities: list[Entity] = []
        seen: set[tuple[int, int, object]] = set()
        for entry in self.entries:
            start = 0
            while True:
                start = text.find(entry.value, start)
                if start == -1:
                    break
                end = start + len(entry.value)
                key = (start, end, entry.entity_type)
                if key not in seen:
                    seen.add(key)
                    entities.append(
                        Entity(
                            text=entry.value,
                            entity_type=entry.entity_type,
                            start=start,
                            end=end,
                            confidence=1.0,
                            source="dictionary",
                            selected=entry.selected,
                        )
                    )
                start += max(1, len(entry.value))
        return sorted(entities, key=lambda item: (item.start, item.end))

