from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from uuid import uuid4


class EntityType(StrEnum):
    PERSON = "PERSON"
    ORGANIZATION = "ORGANIZATION"
    PROJECT = "PROJECT"
    DEPARTMENT = "DEPARTMENT"
    LOCATION = "LOCATION"
    PHONE = "PHONE"
    ID_CARD = "ID_CARD"
    BANK_CARD = "BANK_CARD"
    EMAIL = "EMAIL"
    CREDIT_CODE = "CREDIT_CODE"
    SECURITY_CODE = "SECURITY_CODE"
    AMOUNT = "AMOUNT"
    DATE = "DATE"
    IP_ADDRESS = "IP_ADDRESS"
    BUSINESS_SECRET = "BUSINESS_SECRET"
    CUSTOM = "CUSTOM"


@dataclass(frozen=True, slots=True)
class Entity:
    text: str
    entity_type: EntityType
    start: int
    end: int
    confidence: float
    source: str
    selected: bool = True
    replacement: str | None = None
    reason: str | None = None
    id: str = ""
    conflict: bool = False

    def __post_init__(self) -> None:
        if not self.id:
            object.__setattr__(self, "id", str(uuid4()))
        if self.start < 0 or self.end <= self.start:
            raise ValueError("Entity offsets must describe a non-empty range")
        if self.end - self.start != len(self.text):
            raise ValueError("Entity text length does not match its offsets")
        if not 0 <= self.confidence <= 1:
            raise ValueError("Entity confidence must be between 0 and 1")

    def with_updates(self, **changes: object) -> Entity:
        return replace(self, **changes)

