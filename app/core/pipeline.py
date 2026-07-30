from __future__ import annotations

from app.recognizers.base import Recognizer

from .entities import Entity
from .merger import merge_entities


class DetectionPipeline:
    def __init__(self, recognizers: list[Recognizer]) -> None:
        self.recognizers = tuple(recognizers)

    def analyze(self, text: str) -> list[Entity]:
        return merge_entities(
            [recognizer.analyze(text) for recognizer in self.recognizers]
        )

