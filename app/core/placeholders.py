from __future__ import annotations

from collections import defaultdict

from .entities import Entity, EntityType
from .mapping import MappingEntry


PREFIXES: dict[EntityType, str] = {
    EntityType.ORGANIZATION: "ORG",
    EntityType.ID_CARD: "ID",
    EntityType.BANK_CARD: "BANK",
    EntityType.CREDIT_CODE: "CREDIT",
    EntityType.SECURITY_CODE: "SECURITY",
    EntityType.IP_ADDRESS: "IP",
}


def assign_placeholders(
    text: str, entities: list[Entity]
) -> tuple[list[Entity], list[MappingEntry]]:
    counters: defaultdict[str, int] = defaultdict(int)
    by_value: dict[tuple[EntityType, str], str] = {}
    occupied = set(_placeholder_tokens(text))
    mappings: list[MappingEntry] = []
    assigned: list[Entity] = []

    for entity in sorted(entities, key=lambda item: (item.start, item.end)):
        key = (entity.entity_type, entity.text)
        placeholder = by_value.get(key)
        if placeholder is None:
            prefix = PREFIXES.get(entity.entity_type, entity.entity_type.value)
            while True:
                counters[prefix] += 1
                candidate = f"[{prefix}_{counters[prefix]:03d}]"
                if candidate not in occupied:
                    break
            placeholder = candidate
            occupied.add(placeholder)
            by_value[key] = placeholder
            mappings.append(
                MappingEntry(
                    placeholder=placeholder,
                    original=entity.text,
                    entity_type=entity.entity_type,
                )
            )
        assigned.append(entity.with_updates(replacement=placeholder))
    return assigned, mappings


def _placeholder_tokens(text: str) -> list[str]:
    import re

    return re.findall(r"\[[A-Z][A-Z_]*_\d{3,}\]", text)

