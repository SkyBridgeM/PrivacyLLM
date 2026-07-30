from __future__ import annotations

import regex

from app.config.models import CustomRegexRule
from app.core.entities import Entity


class InvalidCustomRule(ValueError):
    pass


class CustomRegexTimeout(RuntimeError):
    pass


class CustomRegexRecognizer:
    def __init__(
        self,
        rules: list[CustomRegexRule],
        *,
        timeout_seconds: float = 0.05,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("Regex timeout must be positive")
        self.timeout_seconds = timeout_seconds
        self.rules = tuple(rule for rule in rules if rule.enabled)
        self._compiled = tuple(self._compile(rule) for rule in self.rules)

    def analyze(self, text: str) -> list[Entity]:
        entities: list[Entity] = []
        for rule, pattern in zip(self.rules, self._compiled):
            try:
                matches = pattern.finditer(text, timeout=self.timeout_seconds)
                for match in matches:
                    value = match.group(0)
                    if not value:
                        raise InvalidCustomRule(
                            f"Rule {rule.name!r} produced an empty match"
                        )
                    entities.append(
                        Entity(
                            text=value,
                            entity_type=rule.entity_type,
                            start=match.start(),
                            end=match.end(),
                            confidence=1.0,
                            source=f"custom_regex:{rule.name}",
                            selected=rule.selected,
                        )
                    )
            except TimeoutError as exc:
                raise CustomRegexTimeout(
                    f"Rule {rule.name!r} exceeded its execution limit"
                ) from exc
        return sorted(entities, key=lambda item: (item.start, item.end))

    def validate_samples(self) -> dict[str, list[bool]]:
        results: dict[str, list[bool]] = {}
        for rule, pattern in zip(self.rules, self._compiled):
            matches: list[bool] = []
            for sample in rule.test_samples:
                try:
                    matches.append(
                        pattern.fullmatch(
                            sample, timeout=self.timeout_seconds
                        )
                        is not None
                    )
                except TimeoutError as exc:
                    raise CustomRegexTimeout(
                        f"Rule {rule.name!r} timed out on a test sample"
                    ) from exc
            results[rule.name] = matches
        return results

    @staticmethod
    def _compile(rule: CustomRegexRule) -> regex.Pattern[str]:
        try:
            pattern = regex.compile(rule.pattern)
        except regex.error as exc:
            raise InvalidCustomRule(
                f"Rule {rule.name!r} has invalid syntax: {exc}"
            ) from exc
        if pattern.match("") is not None:
            raise InvalidCustomRule(
                f"Rule {rule.name!r} must not match an empty string"
            )
        return pattern

