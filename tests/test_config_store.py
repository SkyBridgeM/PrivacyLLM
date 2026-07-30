import json
from pathlib import Path

import pytest

from app.config.models import DictionaryEntry
from app.config.store import JsonConfigStore
from app.core.entities import EntityType


def store(path: Path) -> JsonConfigStore[DictionaryEntry]:
    return JsonConfigStore(
        path,
        DictionaryEntry.from_dict,
        DictionaryEntry.to_dict,
    )


def test_atomic_save_load_and_backup(tmp_path: Path) -> None:
    path = tmp_path / "dictionary.json"
    config = store(path)
    first = [DictionaryEntry("渝西专项", EntityType.PROJECT)]
    second = [DictionaryEntry("重庆某城投集团", EntityType.ORGANIZATION)]

    config.save(first)
    assert config.load() == first
    config.save(second)

    assert config.load() == second
    backup = json.loads(config.backup_path.read_text(encoding="utf-8"))
    assert backup[0]["value"] == "渝西专项"


def test_invalid_config_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "dictionary.json"
    path.write_text('{"value": "not-a-list"}', encoding="utf-8")
    with pytest.raises(ValueError, match="JSON list"):
        store(path).load()

