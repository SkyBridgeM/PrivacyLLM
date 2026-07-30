from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import ipaddress
import re
from typing import Callable

from app.core.entities import Entity, EntityType


Validator = Callable[[str], bool]


@dataclass(frozen=True, slots=True)
class Rule:
    entity_type: EntityType
    pattern: re.Pattern[str]
    selected: bool = True
    validator: Validator | None = None
    confidence: float = 1.0


class RegexRecognizer:
    def __init__(self, rules: tuple[Rule, ...] | None = None) -> None:
        self.rules = rules or DEFAULT_RULES

    def analyze(self, text: str) -> list[Entity]:
        candidates: list[Entity] = []
        for rule in self.rules:
            for match in rule.pattern.finditer(text):
                value = match.group(0)
                if rule.validator is not None and not rule.validator(value):
                    continue
                candidates.append(
                    Entity(
                        text=value,
                        entity_type=rule.entity_type,
                        start=match.start(),
                        end=match.end(),
                        confidence=rule.confidence,
                        source="regex",
                        selected=rule.selected,
                    )
                )
        return _resolve_overlaps(candidates)


def _resolve_overlaps(entities: list[Entity]) -> list[Entity]:
    priority = {
        EntityType.ID_CARD: 100,
        EntityType.CREDIT_CODE: 95,
        EntityType.BANK_CARD: 90,
        EntityType.PHONE: 85,
        EntityType.EMAIL: 80,
        EntityType.IP_ADDRESS: 75,
        EntityType.SECURITY_CODE: 60,
        EntityType.AMOUNT: 50,
        EntityType.DATE: 40,
    }
    ranked = sorted(
        entities,
        key=lambda item: (
            -priority.get(item.entity_type, 0),
            -(item.end - item.start),
            item.start,
        ),
    )
    accepted: list[Entity] = []
    for candidate in ranked:
        if any(
            candidate.start < item.end and item.start < candidate.end
            for item in accepted
        ):
            continue
        accepted.append(candidate)
    return sorted(accepted, key=lambda item: (item.start, item.end))


def _valid_mainland_id(value: str) -> bool:
    if not re.fullmatch(r"\d{17}[\dXx]", value):
        return False
    try:
        date(int(value[6:10]), int(value[10:12]), int(value[12:14]))
    except ValueError:
        return False
    weights = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
    checks = "10X98765432"
    expected = checks[sum(int(n) * w for n, w in zip(value[:17], weights)) % 11]
    return value[-1].upper() == expected


def _valid_luhn(value: str) -> bool:
    digits = [int(char) for char in value]
    checksum = 0
    parity = len(digits) % 2
    for index, digit in enumerate(digits):
        if index % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    return checksum % 10 == 0


def _valid_credit_code(value: str) -> bool:
    charset = "0123456789ABCDEFGHJKLMNPQRTUWXY"
    weights = (1, 3, 9, 27, 19, 26, 16, 17, 20, 29, 25, 13, 8, 24, 10, 30, 28)
    # In prose, an all-numeric 18-character value is far more likely to be an
    # identity number. Requiring a letter is a deliberate false-positive guard.
    if (
        len(value) != 18
        or not any(char.isalpha() for char in value[:17])
        or any(char not in charset for char in value)
    ):
        return False
    check_index = (31 - sum(charset.index(c) * w for c, w in zip(value[:17], weights)) % 31) % 31
    return value[-1] == charset[check_index]


def _valid_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def _valid_date(value: str) -> bool:
    numbers = [int(part) for part in re.findall(r"\d+", value)]
    if len(numbers) != 3:
        return False
    try:
        date(numbers[0], numbers[1], numbers[2])
        return True
    except ValueError:
        return False


DEFAULT_RULES = (
    Rule(
        EntityType.EMAIL,
        re.compile(
            r"(?<![A-Za-z0-9.!#$%&'*+/=?^_`{|}~-])"
            r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+"
            r"(?:\.[A-Za-z0-9-]+)+(?![A-Za-z0-9.-])"
        ),
    ),
    Rule(
        EntityType.CREDIT_CODE,
        re.compile(r"(?<![0-9A-Z])[0-9A-HJ-NPQRTUWXY]{18}(?![0-9A-Z])"),
        validator=_valid_credit_code,
    ),
    Rule(
        EntityType.ID_CARD,
        re.compile(r"(?<!\d)\d{17}[\dXx](?![\dXx])"),
        validator=_valid_mainland_id,
    ),
    Rule(
        EntityType.PHONE,
        re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    ),
    Rule(
        EntityType.BANK_CARD,
        re.compile(r"(?<!\d)\d{12,19}(?!\d)"),
        validator=_valid_luhn,
    ),
    Rule(
        EntityType.IP_ADDRESS,
        re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])"),
        validator=_valid_ip,
    ),
    Rule(
        EntityType.AMOUNT,
        re.compile(
            r"(?<![A-Za-z0-9_.])(?:人民币\s*)?[¥￥]\s?\d[\d,]*(?:\.\d{1,2})?"
            r"|(?<![A-Za-z0-9_.])(?:人民币\s*)?\d[\d,]*(?:\.\d{1,2})?"
            r"\s?(?:元|万元|亿元|人民币)(?!\w)"
        ),
        selected=False,
    ),
    Rule(
        EntityType.DATE,
        re.compile(r"(?<!\d)\d{4}(?:年|[-/.])\d{1,2}(?:月|[-/.])\d{1,2}日?(?!\d)"),
        selected=False,
        validator=_valid_date,
    ),
    Rule(
        EntityType.SECURITY_CODE,
        re.compile(r"(?<!\d)(?:000|001|002|003|300|301|600|601|603|605|688|689)\d{3}(?!\d)"),
        selected=False,
        confidence=0.9,
    ),
)
