from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any
from uuid import uuid4

from .entities import EntityType


@dataclass(frozen=True, slots=True)
class MappingEntry:
    placeholder: str
    original: str
    entity_type: EntityType

    def to_dict(self) -> dict[str, str]:
        result = asdict(self)
        result["entity_type"] = self.entity_type.value
        return result


@dataclass(frozen=True, slots=True)
class MappingDocument:
    mappings: tuple[MappingEntry, ...]
    created_at: str
    document_id: str
    version: int = 1

    @classmethod
    def create(cls, mappings: list[MappingEntry]) -> MappingDocument:
        return cls(
            mappings=tuple(mappings),
            created_at=datetime.now().astimezone().isoformat(timespec="seconds"),
            document_id=str(uuid4()),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "created_at": self.created_at,
            "document_id": self.document_id,
            "mappings": [item.to_dict() for item in self.mappings],
        }

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_json(cls, raw: str) -> MappingDocument:
        data = json.loads(raw)
        if data.get("version") != 1:
            raise ValueError("Unsupported mapping version")
        required = {"created_at", "document_id", "mappings"}
        if not required.issubset(data):
            raise ValueError("Invalid mapping document")

        entries: list[MappingEntry] = []
        seen: set[str] = set()
        for item in data["mappings"]:
            placeholder = item["placeholder"]
            if placeholder in seen:
                raise ValueError("Duplicate placeholder in mapping")
            seen.add(placeholder)
            entries.append(
                MappingEntry(
                    placeholder=placeholder,
                    original=item["original"],
                    entity_type=EntityType(item["entity_type"]),
                )
            )
        return cls(
            version=1,
            created_at=data["created_at"],
            document_id=data["document_id"],
            mappings=tuple(entries),
        )

