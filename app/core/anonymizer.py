from __future__ import annotations

from dataclasses import dataclass

from .entities import Entity
from .mapping import MappingDocument
from .placeholders import assign_placeholders


@dataclass(frozen=True, slots=True)
class AnonymizationResult:
    text: str
    entities: tuple[Entity, ...]
    mapping: MappingDocument


def anonymize(text: str, entities: list[Entity]) -> AnonymizationResult:
    selected = [item for item in entities if item.selected]
    _validate_entities(text, selected)
    assigned, mappings = assign_placeholders(text, selected)

    result = text
    for entity in sorted(assigned, key=lambda item: item.start, reverse=True):
        assert entity.replacement is not None
        result = result[: entity.start] + entity.replacement + result[entity.end :]

    return AnonymizationResult(
        text=result,
        entities=tuple(assigned),
        mapping=MappingDocument.create(mappings),
    )


def _validate_entities(text: str, entities: list[Entity]) -> None:
    ordered = sorted(entities, key=lambda item: (item.start, item.end))
    previous: Entity | None = None
    for entity in ordered:
        if text[entity.start : entity.end] != entity.text:
            raise ValueError(f"Entity {entity.id} does not match source text")
        if previous is not None and entity.start < previous.end:
            raise ValueError("Selected entities must not overlap")
        previous = entity

