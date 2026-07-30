from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from app.config.models import CustomRegexRule, DictionaryEntry
from app.config.settings import SettingsStore
from app.config.store import JsonConfigStore
from app.core.anonymizer import anonymize
from app.core.entities import Entity, EntityType
from app.core.mapping import MappingDocument
from app.core.merger import merge_entities
from app.core.pipeline import DetectionPipeline
from app.core.restorer import restore
from app.recognizers import (
    CustomRegexRecognizer,
    DictionaryRecognizer,
    RegexRecognizer,
)
from app.recognizers.custom_regex_recognizer import (
    CustomRegexTimeout,
    InvalidCustomRule,
)
from app.recognizers.ollama_recognizer import (
    OllamaRecognizer,
    OllamaUnavailable,
    model_status as get_ollama_status,
)
from app.schemas.api import (
    AnalyzeTextRequest,
    AnalyzeTextResponse,
    AnonymizeTextRequest,
    AnonymizeTextResponse,
    DictionaryEntryPayload,
    EntityPayload,
    RestoreTextRequest,
    RestoreTextResponse,
    SettingsPayload,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"
dictionary_store = JsonConfigStore(
    CONFIG_DIR / "dictionary.json",
    DictionaryEntry.from_dict,
    DictionaryEntry.to_dict,
)
custom_rule_store = JsonConfigStore(
    CONFIG_DIR / "custom_regex_rules.json",
    CustomRegexRule.from_dict,
    CustomRegexRule.to_dict,
)
settings_store = SettingsStore(CONFIG_DIR / "settings.json")

router = APIRouter(prefix="/api/v1")

STRUCTURED_ENTITY_TYPES = {
    EntityType.PHONE,
    EntityType.ID_CARD,
    EntityType.BANK_CARD,
    EntityType.EMAIL,
    EntityType.CREDIT_CODE,
    EntityType.SECURITY_CODE,
    EntityType.AMOUNT,
    EntityType.DATE,
    EntityType.IP_ADDRESS,
}


def _entity_payload(entity: Entity) -> EntityPayload:
    return EntityPayload(
        id=entity.id,
        text=entity.text,
        entity_type=entity.entity_type,
        start=entity.start,
        end=entity.end,
        confidence=entity.confidence,
        source=entity.source,
        selected=entity.selected,
        replacement=entity.replacement,
        reason=entity.reason,
        conflict=entity.conflict,
    )


def _entity_model(payload: EntityPayload) -> Entity:
    return Entity(**payload.model_dump())


def _load_pipeline() -> DetectionPipeline:
    try:
        dictionary = dictionary_store.load()
        custom_rules = custom_rule_store.load()
        custom_recognizer = CustomRegexRecognizer(custom_rules)
    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
        InvalidCustomRule,
    ) as exc:
        raise HTTPException(
            status_code=422,
            detail=f"本地识别配置无效：{exc}",
        ) from exc
    return DetectionPipeline(
        [
            RegexRecognizer(),
            DictionaryRecognizer(dictionary),
            custom_recognizer,
        ]
    )


def _filter_semantic_duplicates(
    semantic_entities: list[Entity],
    rule_entities: list[Entity],
) -> list[Entity]:
    """Drop model guesses that overlap high-confidence structured matches."""
    protected = [
        entity
        for entity in rule_entities
        if entity.entity_type in STRUCTURED_ENTITY_TYPES
        and "regex" in entity.source
    ]
    return [
        entity
        for entity in semantic_entities
        if not any(
            entity.start < rule.end and rule.start < entity.end
            for rule in protected
        )
    ]


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "processing": "local"}


@router.get("/model/status")
def model_status() -> dict[str, Any]:
    return get_ollama_status()


@router.post("/analyze/text", response_model=AnalyzeTextResponse)
def analyze_text(request: AnalyzeTextRequest) -> AnalyzeTextResponse:
    try:
        rule_entities = _load_pipeline().analyze(request.text)
        entities = rule_entities
        if request.use_llm:
            semantic_entities = OllamaRecognizer().analyze(request.text)
            semantic_entities = _filter_semantic_duplicates(
                semantic_entities, rule_entities
            )
            entities = merge_entities([rule_entities, semantic_entities])
        defaults = settings_store.load()
    except OllamaUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail=f"语义增强不可用：{exc}",
        ) from exc
    except CustomRegexTimeout as exc:
        raise HTTPException(
            status_code=422,
            detail=f"自定义规则执行超时：{exc}",
        ) from exc
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=422,
            detail=f"本地设置无效：{exc}",
        ) from exc

    entities = [
        entity.with_updates(
            selected=False
            if entity.conflict
            else defaults.get(entity.entity_type, entity.selected)
        )
        for entity in entities
    ]
    return AnalyzeTextResponse(
        text=request.text,
        entities=[_entity_payload(entity) for entity in entities],
        semantic_available=request.use_llm,
    )


@router.post("/anonymize/text", response_model=AnonymizeTextResponse)
def anonymize_text(
    request: AnonymizeTextRequest,
) -> AnonymizeTextResponse:
    try:
        result = anonymize(
            request.text,
            [_entity_model(entity) for entity in request.entities],
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return AnonymizeTextResponse(
        text=result.text,
        entities=[_entity_payload(entity) for entity in result.entities],
        mapping=result.mapping.to_dict(),
    )


@router.post("/restore/text", response_model=RestoreTextResponse)
def restore_text(request: RestoreTextRequest) -> RestoreTextResponse:
    try:
        mapping = MappingDocument.from_json(
            json.dumps(request.mapping, ensure_ascii=False)
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=422,
            detail="映射文件格式无效或版本不受支持",
        ) from exc
    result = restore(request.text, mapping)
    return RestoreTextResponse(
        text=result.text,
        replaced=list(result.replaced),
        unused_mappings=list(result.unused_mappings),
        unknown_placeholders=list(result.unknown_placeholders),
    )


@router.get(
    "/dictionary",
    response_model=list[DictionaryEntryPayload],
)
def get_dictionary() -> list[DictionaryEntryPayload]:
    try:
        return [
            DictionaryEntryPayload(**entry.to_dict())
            for entry in dictionary_store.load()
        ]
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=422, detail=f"词典文件无效：{exc}"
        ) from exc


@router.put(
    "/dictionary",
    response_model=list[DictionaryEntryPayload],
)
def put_dictionary(
    entries: list[DictionaryEntryPayload],
) -> list[DictionaryEntryPayload]:
    try:
        models = [
            DictionaryEntry.from_dict(entry.model_dump(mode="json"))
            for entry in entries
        ]
        dictionary_store.save(models)
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=422, detail=f"无法保存词典：{exc}"
        ) from exc
    return entries


@router.get("/settings", response_model=SettingsPayload)
def get_settings() -> SettingsPayload:
    try:
        return SettingsPayload(entity_defaults=settings_store.load())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=422, detail=f"设置文件无效：{exc}"
        ) from exc


@router.put("/settings", response_model=SettingsPayload)
def put_settings(settings: SettingsPayload) -> SettingsPayload:
    try:
        settings_store.save(settings.entity_defaults)
        return SettingsPayload(entity_defaults=settings_store.load())
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=422, detail=f"无法保存设置：{exc}"
        ) from exc
