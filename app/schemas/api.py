from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.entities import EntityType


class EntityPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    text: str
    entity_type: EntityType
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    confidence: float = Field(ge=0, le=1)
    source: str
    selected: bool = True
    replacement: str | None = None
    reason: str | None = None
    conflict: bool = False

    @model_validator(mode="after")
    def validate_range(self) -> EntityPayload:
        if self.end <= self.start:
            raise ValueError("end must be greater than start")
        if self.end - self.start != len(self.text):
            raise ValueError("text length does not match offsets")
        return self


class AnalyzeTextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(max_length=50_000)
    use_llm: bool = False


class AnalyzeTextResponse(BaseModel):
    text: str
    entities: list[EntityPayload]
    semantic_available: bool = False


class AnonymizeTextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(max_length=50_000)
    entities: list[EntityPayload]


class AnonymizeTextResponse(BaseModel):
    text: str
    entities: list[EntityPayload]
    mapping: dict[str, Any]


class RestoreTextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(max_length=100_000)
    mapping: dict[str, Any]


class RestoreTextResponse(BaseModel):
    text: str
    replaced: list[str]
    unused_mappings: list[str]
    unknown_placeholders: list[str]


class DictionaryEntryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str = Field(min_length=1, max_length=500)
    entity_type: EntityType
    enabled: bool = True
    selected: bool = True


class SettingsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_defaults: dict[EntityType, bool]

