from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.entities import Entity, EntityType


OLLAMA_URL = os.getenv("PRIVACYLLM_OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("PRIVACYLLM_OLLAMA_MODEL", "qwen3.5:4b")
SEMANTIC_TYPES = {
    EntityType.PERSON,
    EntityType.ORGANIZATION,
    EntityType.PROJECT,
    EntityType.DEPARTMENT,
    EntityType.LOCATION,
    EntityType.BUSINESS_SECRET,
}


class OllamaUnavailable(RuntimeError):
    pass


def _request(path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        f"{OLLAMA_URL}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="GET" if payload is None else "POST",
    )
    try:
        with urlopen(request, timeout=180 if payload else 3) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise OllamaUnavailable(f"无法连接本机 Ollama：{exc}") from exc
    if not isinstance(body, dict):
        raise OllamaUnavailable("Ollama 返回了无法识别的数据")
    return body


def model_status() -> dict[str, Any]:
    try:
        payload = _request("/api/tags")
    except OllamaUnavailable as exc:
        return {
            "available": False,
            "provider": "ollama",
            "model": OLLAMA_MODEL,
            "message": str(exc),
        }
    names = {
        model.get("name")
        for model in payload.get("models", [])
        if isinstance(model, dict)
    }
    available = OLLAMA_MODEL in names
    return {
        "available": available,
        "provider": "ollama",
        "model": OLLAMA_MODEL,
        "message": (
            f"{OLLAMA_MODEL} 已就绪"
            if available
            else f"Ollama 正在运行，但尚未安装 {OLLAMA_MODEL}"
        ),
    }


class OllamaRecognizer:
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
        response = _request(
            "/api/chat",
            {
                "model": OLLAMA_MODEL,
                "stream": False,
                "think": False,
                "format": schema,
                "options": {"temperature": 0},
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        try:
            content = response["message"]["content"]
            parsed = json.loads(content)
            candidates = parsed["entities"]
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise OllamaUnavailable("语义模型返回格式无效") from exc
        if not isinstance(candidates, list):
            raise OllamaUnavailable("语义模型返回格式无效")
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
                    source="qwen",
                    selected=True,
                    reason=str(candidate.get("reason") or "本地语义模型识别"),
                )
            )
        return result
