from app.config.models import DictionaryEntry
from app.core.entities import Entity, EntityType
from app.core.merger import merge_entities
from app.core.pipeline import DetectionPipeline
from app.recognizers import DictionaryRecognizer, RegexRecognizer


def test_pipeline_combines_dictionary_and_regex() -> None:
    pipeline = DetectionPipeline(
        [
            RegexRecognizer(),
            DictionaryRecognizer(
                [DictionaryEntry("渝西专项", EntityType.PROJECT)]
            ),
        ]
    )
    entities = pipeline.analyze("渝西专项联系人13812345678")
    assert [(item.text, item.source) for item in entities] == [
        ("渝西专项", "dictionary"),
        ("13812345678", "regex"),
    ]


def make_entity(
    text: str, entity_type: EntityType, start: int, source: str
) -> Entity:
    return Entity(
        text=text,
        entity_type=entity_type,
        start=start,
        end=start + len(text),
        confidence=1,
        source=source,
    )


def test_different_type_overlap_requires_review() -> None:
    entities = merge_entities(
        [
            [make_entity("渝西专项", EntityType.PROJECT, 0, "dictionary")],
            [make_entity("专项", EntityType.CUSTOM, 2, "custom_regex:test")],
        ]
    )
    assert len(entities) == 2
    assert all(item.conflict and not item.selected for item in entities)


def test_same_type_prefers_dictionary_over_shorter_rule_match() -> None:
    entities = merge_entities(
        [
            [
                make_entity(
                    "重庆某城投集团",
                    EntityType.ORGANIZATION,
                    0,
                    "dictionary",
                )
            ],
            [
                make_entity(
                    "城投集团",
                    EntityType.ORGANIZATION,
                    3,
                    "regex",
                )
            ],
        ]
    )
    assert entities[0].selected is True
    assert entities[1].selected is False

