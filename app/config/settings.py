from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

from app.core.entities import EntityType


DEFAULT_SELECTIONS: dict[EntityType, bool] = {
    EntityType.PHONE: True,
    EntityType.ID_CARD: True,
    EntityType.BANK_CARD: True,
    EntityType.EMAIL: True,
    EntityType.CREDIT_CODE: True,
    EntityType.IP_ADDRESS: True,
    EntityType.SECURITY_CODE: False,
    EntityType.AMOUNT: False,
    EntityType.DATE: False,
    EntityType.LOCATION: True,
    EntityType.PERSON: True,
    EntityType.ORGANIZATION: True,
    EntityType.PROJECT: True,
    EntityType.DEPARTMENT: True,
    EntityType.BUSINESS_SECRET: True,
    EntityType.CUSTOM: True,
}


class SettingsStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> dict[EntityType, bool]:
        result = dict(DEFAULT_SELECTIONS)
        if not self.path.exists():
            return result
        with self.path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        if not isinstance(raw, dict) or not isinstance(
            raw.get("entity_defaults"), dict
        ):
            raise ValueError("settings.json has an invalid structure")
        for key, value in raw["entity_defaults"].items():
            result[EntityType(key)] = bool(value)
        return result

    def save(self, values: dict[EntityType, bool]) -> None:
        merged = dict(DEFAULT_SELECTIONS)
        merged.update(values)
        payload = {
            "entity_defaults": {
                key.value: value for key, value in merged.items()
            }
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            dir=self.path.parent,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)

