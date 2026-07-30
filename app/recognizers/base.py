from __future__ import annotations

from typing import Protocol

from app.core.entities import Entity


class Recognizer(Protocol):
    def analyze(self, text: str) -> list[Entity]:
        """Return candidate entities with offsets relative to text."""

