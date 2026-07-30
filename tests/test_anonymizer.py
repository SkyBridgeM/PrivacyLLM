import pytest

from app.core.anonymizer import anonymize
from app.core.entities import Entity, EntityType


def entity(text: str, value: str, start: int, kind: EntityType) -> Entity:
    return Entity(
        text=value,
        entity_type=kind,
        start=start,
        end=start + len(value),
        confidence=1,
        source="test",
    )


def test_repeated_value_uses_same_placeholder() -> None:
    text = "张伟联系张伟"
    entities = [
        entity(text, "张伟", 0, EntityType.PERSON),
        entity(text, "张伟", 4, EntityType.PERSON),
    ]
    result = anonymize(text, entities)
    assert result.text == "[PERSON_001]联系[PERSON_001]"
    assert len(result.mapping.mappings) == 1


def test_existing_placeholder_is_not_reused() -> None:
    text = "保留[PHONE_001]，电话13812345678"
    start = text.index("13812345678")
    result = anonymize(
        text, [entity(text, "13812345678", start, EntityType.PHONE)]
    )
    assert result.text.endswith("[PHONE_002]")


def test_unselected_entity_is_ignored() -> None:
    original = entity("日期2026年7月30日", "2026年7月30日", 2, EntityType.DATE)
    result = anonymize(
        "日期2026年7月30日", [original.with_updates(selected=False)]
    )
    assert result.text == "日期2026年7月30日"
    assert result.mapping.mappings == ()


def test_rejects_overlapping_entities() -> None:
    text = "重庆城投集团"
    entities = [
        entity(text, text, 0, EntityType.ORGANIZATION),
        entity(text, "城投集团", 2, EntityType.ORGANIZATION),
    ]
    with pytest.raises(ValueError, match="overlap"):
        anonymize(text, entities)


def test_rejects_stale_offsets() -> None:
    with pytest.raises(ValueError, match="does not match"):
        anonymize(
            "张伟",
            [entity("李伟", "李伟", 0, EntityType.PERSON)],
        )

