from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from app.core.entities import EntityType


_SAFE_NAME = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


@dataclass(frozen=True, slots=True)
class DictionaryEntry:
    value: str
    entity_type: EntityType
    enabled: bool = True
    selected: bool = True

    def __post_init__(self) -> None:
        if not self.value or not self.value.strip():
            raise ValueError("Dictionary value must not be empty")
        if len(self.value) > 500:
            raise ValueError("Dictionary value is too long")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DictionaryEntry:
        return cls(
            value=str(data["value"]),
            entity_type=EntityType(data["entity_type"]),
            enabled=bool(data.get("enabled", True)),
            selected=bool(data.get("selected", True)),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "value": self.value,
            "entity_type": self.entity_type.value,
            "enabled": self.enabled,
            "selected": self.selected,
        }


@dataclass(frozen=True, slots=True)
class CustomRegexRule:
    name: str
    pattern: str
    entity_type: EntityType = EntityType.CUSTOM
    enabled: bool = True
    selected: bool = True
    test_samples: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not _SAFE_NAME.fullmatch(self.name):
            raise ValueError(
                "Rule name must contain only letters, numbers, underscores, or hyphens"
            )
        if not self.pattern or len(self.pattern) > 1000:
            raise ValueError("Rule pattern must contain 1 to 1000 characters")
        if len(self.test_samples) > 20:
            raise ValueError("A rule may contain at most 20 test samples")
        if any(len(sample) > 2000 for sample in self.test_samples):
            raise ValueError("A regex test sample is too long")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CustomRegexRule:
        samples = data.get("test_samples", [])
        if not isinstance(samples, list):
            raise ValueError("test_samples must be a list")
        return cls(
            name=str(data["name"]),
            pattern=str(data["pattern"]),
            entity_type=EntityType(data.get("entity_type", "CUSTOM")),
            enabled=bool(data.get("enabled", True)),
            selected=bool(data.get("selected", True)),
            test_samples=tuple(str(item) for item in samples),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "pattern": self.pattern,
            "entity_type": self.entity_type.value,
            "enabled": self.enabled,
            "selected": self.selected,
            "test_samples": list(self.test_samples),
        }

