import json

import pytest

from app.core.entities import EntityType
from app.core.mapping import MappingDocument, MappingEntry
from app.core.restorer import restore


def sample_mapping() -> MappingDocument:
    return MappingDocument.create(
        [
            MappingEntry("[PERSON_001]", "张伟", EntityType.PERSON),
            MappingEntry("[ORG_001]", "重庆城投集团", EntityType.ORGANIZATION),
        ]
    )


def test_mapping_json_round_trip() -> None:
    mapping = sample_mapping()
    restored = MappingDocument.from_json(mapping.to_json())
    assert restored == mapping
    assert "张伟" in mapping.to_json()


def test_rejects_unknown_mapping_version() -> None:
    raw = sample_mapping().to_dict()
    raw["version"] = 2
    with pytest.raises(ValueError, match="Unsupported"):
        MappingDocument.from_json(json.dumps(raw, ensure_ascii=False))


def test_restores_ai_rewritten_text_and_reports_status() -> None:
    result = restore(
        "[PERSON_001]任职于[ORG_001]。[UNKNOWN_999]保持不变。",
        sample_mapping(),
    )
    assert result.text == "张伟任职于重庆城投集团。[UNKNOWN_999]保持不变。"
    assert result.replaced == ("[ORG_001]", "[PERSON_001]")
    assert result.unused_mappings == ()
    assert result.unknown_placeholders == ("[UNKNOWN_999]",)


def test_modified_placeholder_is_not_guessed() -> None:
    result = restore("PERSON_001提出了建议。", sample_mapping())
    assert result.text == "PERSON_001提出了建议。"
    assert result.replaced == ()
    assert set(result.unused_mappings) == {"[PERSON_001]", "[ORG_001]"}

