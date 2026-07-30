from app.config.models import DictionaryEntry
from app.core.entities import EntityType
from app.recognizers.dictionary_recognizer import DictionaryRecognizer


def test_finds_every_occurrence_with_stable_offsets() -> None:
    text = "渝西专项由重庆某城投集团负责，渝西专项已启动。"
    recognizer = DictionaryRecognizer(
        [
            DictionaryEntry("渝西专项", EntityType.PROJECT),
            DictionaryEntry("重庆某城投集团", EntityType.ORGANIZATION),
        ]
    )
    entities = recognizer.analyze(text)
    assert [item.text for item in entities] == [
        "渝西专项",
        "重庆某城投集团",
        "渝西专项",
    ]
    assert all(text[item.start : item.end] == item.text for item in entities)


def test_ignores_disabled_and_deduplicates_entries() -> None:
    recognizer = DictionaryRecognizer(
        [
            DictionaryEntry("渝西专项", EntityType.PROJECT),
            DictionaryEntry("渝西专项", EntityType.PROJECT),
            DictionaryEntry("不应命中", EntityType.PROJECT, enabled=False),
        ]
    )
    entities = recognizer.analyze("渝西专项，不应命中")
    assert len(entities) == 1
    assert entities[0].text == "渝西专项"

