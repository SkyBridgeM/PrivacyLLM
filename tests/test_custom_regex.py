import pytest

from app.config.models import CustomRegexRule
from app.core.entities import EntityType
from app.recognizers.custom_regex_recognizer import (
    CustomRegexTimeout,
    CustomRegexRecognizer,
    InvalidCustomRule,
)


def test_named_custom_rule_and_samples() -> None:
    rule = CustomRegexRule(
        name="project_number",
        pattern=r"YX-\d{4}-\d{3}",
        entity_type=EntityType.CUSTOM,
        test_samples=("YX-2026-001", "invalid"),
    )
    recognizer = CustomRegexRecognizer([rule])
    entities = recognizer.analyze("编号 YX-2026-001 已立项")
    assert len(entities) == 1
    assert entities[0].source == "custom_regex:project_number"
    assert recognizer.validate_samples() == {
        "project_number": [True, False]
    }


def test_rejects_invalid_or_empty_matching_pattern() -> None:
    with pytest.raises(InvalidCustomRule, match="invalid syntax"):
        CustomRegexRecognizer(
            [CustomRegexRule(name="broken", pattern="[")]
        )
    with pytest.raises(InvalidCustomRule, match="empty string"):
        CustomRegexRecognizer(
            [CustomRegexRule(name="empty", pattern=r"\d*")]
        )


def test_catastrophic_pattern_is_stopped_by_timeout() -> None:
    recognizer = CustomRegexRecognizer(
        [CustomRegexRule(name="slow", pattern=r"(a+)+$")],
        timeout_seconds=0.000001,
    )
    with pytest.raises(CustomRegexTimeout, match="execution limit"):
        recognizer.analyze("a" * 10_000 + "!")
