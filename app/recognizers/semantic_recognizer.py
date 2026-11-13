from __future__ import annotations

import json

from app.core.entities import Entity, EntityType
from app.recognizers.llama_runtime import SemanticUnavailable, runtime


SEMANTIC_TYPES = {
    EntityType.PERSON,
    EntityType.ORGANIZATION,
    EntityType.PROJECT,
    EntityType.DEPARTMENT,
    EntityType.LOCATION,
    EntityType.BUSINESS_SECRET,
}


def model_status() -> dict:
    return runtime.status()


class SemanticRecognizer:
    def analyze(self, text: str) -> list[Entity]:
        schema = {
            "type": "object",
            "properties": {
                "entities": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string"},
                            "entity_type": {
                                "type": "string",
                                "enum": sorted(item.value for item in SEMANTIC_TYPES),
                            },
                            "start": {"type": "integer", "minimum": 0},
                            "end": {"type": "integer", "minimum": 1},
                            "confidence": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 1,
                            },
                            "reason": {"type": "string"},
                        },
                        "required": [
                            "text",
                            "entity_type",
                            "start",
                            "end",
                            "confidence",
                            "reason",
                        ],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["entities"],
            "additionalProperties": False,
        }
        prompt = (
            "识别下方文本中仅靠格式规则难以发现的敏感信息。"
            "只标记确实应在发送给外部 AI 前隐藏的内容，避免泛化。"
            "text 必须逐字复制原文，start/end 是 Python 字符索引，end 不包含末位。"
            "类型仅使用 PERSON、ORGANIZATION、PROJECT、DEPARTMENT、LOCATION、"
            "BUSINESS_SECRET。不要识别泛称、普通日期、金额或公开常识。\n\n"
            f"<document>\n{text}\n</document>"
        )
        response = runtime.request(
            "/v1/chat/completions",
            {
                "model": "privacyllm-local",
                "stream": False,
                "chat_template_kwargs": {"enable_thinking": False},
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "entities", "strict": True, "schema": schema,
                    },
                },
                "max_tokens": 8192,
                "temperature": 0,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        try:
            content = response["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            candidates = parsed["entities"]
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise SemanticUnavailable("语义模型返回格式无效") from exc
        if not isinstance(candidates, list):
            raise SemanticUnavailable("语义模型返回格式无效")
        return self._validated_entities(text, candidates)

    @staticmethod
    def _validated_entities(
        source: str, candidates: list[object]
    ) -> list[Entity]:
        result: list[Entity] = []
        seen: set[tuple[int, int, EntityType]] = set()
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            try:
                value = str(candidate["text"])
                entity_type = EntityType(str(candidate["entity_type"]))
                start = int(candidate["start"])
                end = int(candidate["end"])
                confidence = float(candidate["confidence"])
            except (KeyError, TypeError, ValueError):
                continue
            if entity_type not in SEMANTIC_TYPES or not value:
                continue
            if start < 0 or end > len(source) or source[start:end] != value:
                occurrences = [
                    index
                    for index in range(len(source))
                    if source.startswith(value, index)
                ]
                if len(occurrences) != 1:
                    continue
                start = occurrences[0]
                end = start + len(value)
            key = (start, end, entity_type)
            if key in seen:
                continue
            seen.add(key)
            result.append(
                Entity(
                    text=value,
                    entity_type=entity_type,
                    start=start,
                    end=end,
                    confidence=max(0.0, min(1.0, confidence)),
                    source="semantic",
                    selected=True,
                    reason=str(candidate.get("reason") or "本地语义模型识别"),
                )
            )
        return result
