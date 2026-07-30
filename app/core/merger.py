from __future__ import annotations

from collections import defaultdict

from .entities import Entity


SOURCE_PRIORITY = {
    "manual": 400,
    "dictionary": 300,
    "custom_regex": 250,
    "regex": 200,
    "qwen": 100,
}


def merge_entities(groups: list[list[Entity]]) -> list[Entity]:
    exact: dict[tuple[int, int, object], list[Entity]] = defaultdict(list)
    for group in groups:
        for entity in group:
            exact[(entity.start, entity.end, entity.entity_type)].append(entity)

    merged = [_merge_exact(items) for items in exact.values()]
    merged.sort(key=lambda item: (item.start, item.end))
    return _resolve_partial_overlaps(merged)


def _merge_exact(items: list[Entity]) -> Entity:
    preferred = max(items, key=_priority)
    sources = sorted({item.source for item in items})
    return preferred.with_updates(
        confidence=max(item.confidence for item in items),
        source="+".join(sources),
        selected=any(item.selected for item in items),
    )


def _resolve_partial_overlaps(entities: list[Entity]) -> list[Entity]:
    result = list(entities)
    for left_index, left in enumerate(result):
        for right_index in range(left_index + 1, len(result)):
            right = result[right_index]
            if right.start >= left.end:
                break
            if left.start >= right.end:
                continue

            if left.entity_type != right.entity_type:
                result[left_index] = result[left_index].with_updates(
                    conflict=True, selected=False
                )
                result[right_index] = result[right_index].with_updates(
                    conflict=True, selected=False
                )
                left = result[left_index]
                continue

            winner, loser = _choose_same_type(left, right)
            loser_index = left_index if loser.id == left.id else right_index
            result[loser_index] = result[loser_index].with_updates(selected=False)
            if winner.id == right.id:
                left = result[left_index]
    return result


def _choose_same_type(left: Entity, right: Entity) -> tuple[Entity, Entity]:
    left_key = (_priority(left), left.end - left.start)
    right_key = (_priority(right), right.end - right.start)
    return (left, right) if left_key >= right_key else (right, left)


def _priority(entity: Entity) -> int:
    root_source = entity.source.split(":", 1)[0]
    return SOURCE_PRIORITY.get(root_source, 0)

