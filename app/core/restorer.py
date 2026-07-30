from __future__ import annotations

from dataclasses import dataclass
import re

from .mapping import MappingDocument


PLACEHOLDER_PATTERN = re.compile(r"\[[A-Z][A-Z_]*_\d{3,}\]")


@dataclass(frozen=True, slots=True)
class RestoreResult:
    text: str
    replaced: tuple[str, ...]
    unused_mappings: tuple[str, ...]
    unknown_placeholders: tuple[str, ...]


def restore(text: str, mapping: MappingDocument) -> RestoreResult:
    replacements = {item.placeholder: item.original for item in mapping.mappings}
    seen: set[str] = set()
    unknown: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        placeholder = match.group(0)
        original = replacements.get(placeholder)
        if original is None:
            unknown.add(placeholder)
            return placeholder
        seen.add(placeholder)
        return original

    restored = PLACEHOLDER_PATTERN.sub(replace, text)
    return RestoreResult(
        text=restored,
        replaced=tuple(sorted(seen)),
        unused_mappings=tuple(sorted(set(replacements) - seen)),
        unknown_placeholders=tuple(sorted(unknown)),
    )

