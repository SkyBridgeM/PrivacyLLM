from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from app.api import routes
from app.config.models import CustomRegexRule, DictionaryEntry
from app.config.settings import SettingsStore
from app.config.store import JsonConfigStore
from app.core.entities import EntityType
from app.main import app


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    dictionary_store = JsonConfigStore(
        tmp_path / "dictionary.json",
        DictionaryEntry.from_dict,
        DictionaryEntry.to_dict,
    )
    rule_store = JsonConfigStore(
        tmp_path / "custom_regex_rules.json",
        CustomRegexRule.from_dict,
        CustomRegexRule.to_dict,
    )
    settings_store = SettingsStore(tmp_path / "settings.json")
    dictionary_store.save(
        [DictionaryEntry("渝西专项", EntityType.PROJECT)]
    )
    rule_store.save([])
    monkeypatch.setattr(routes, "dictionary_store", dictionary_store)
    monkeypatch.setattr(routes, "custom_rule_store", rule_store)
    monkeypatch.setattr(routes, "settings_store", settings_store)
    return TestClient(app)


def test_home_has_local_security_headers(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "PrivacyLLM" in response.text
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert response.headers["referrer-policy"] == "no-referrer"


def test_analyze_anonymize_and_restore_round_trip(client: TestClient) -> None:
    source = "渝西专项联系人13812345678，金额人民币 12.50万元。"
    analyzed = client.post(
        "/api/v1/analyze/text",
        json={"text": source, "use_llm": False},
    )
    assert analyzed.status_code == 200
    entities = analyzed.json()["entities"]
    assert [item["text"] for item in entities] == [
        "渝西专项",
        "13812345678",
        "人民币 12.50万元",
    ]
    amount = next(item for item in entities if item["entity_type"] == "AMOUNT")
    assert amount["selected"] is False

    redacted = client.post(
        "/api/v1/anonymize/text",
        json={"text": source, "entities": entities},
    )
    assert redacted.status_code == 200
    payload = redacted.json()
    assert payload["text"].startswith("[PROJECT_001]联系人[PHONE_001]")
    assert "人民币 12.50万元" in payload["text"]

    restored = client.post(
        "/api/v1/restore/text",
        json={
            "text": f"建议继续推进：{payload['text']}",
            "mapping": payload["mapping"],
        },
    )
    assert restored.status_code == 200
    assert restored.json()["text"] == f"建议继续推进：{source}"


def test_semantic_mode_merges_local_model_results(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = "联系人张敏负责星河计划。"

    def fake_semantic_analyze(self: object, text: str) -> list[object]:
        assert text == source
        from app.core.entities import Entity

        return [
            Entity(
                text="张敏",
                entity_type=EntityType.PERSON,
                start=3,
                end=5,
                confidence=0.93,
                source="qwen",
            )
        ]

    monkeypatch.setattr(
        routes.OllamaRecognizer, "analyze", fake_semantic_analyze
    )
    response = client.post(
        "/api/v1/analyze/text",
        json={"text": source, "use_llm": True},
    )
    assert response.status_code == 200
    assert response.json()["semantic_available"] is True
    assert response.json()["entities"][0]["text"] == "张敏"
    assert response.json()["entities"][0]["source"] == "qwen"


def test_semantic_mode_discards_guesses_over_structured_rule_matches(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = "联系人13812345678，邮箱liwenbo@example.com。"

    def fake_semantic_analyze(self: object, text: str) -> list[object]:
        assert text == source
        from app.core.entities import Entity

        return [
            Entity(
                text="13812345678",
                entity_type=EntityType.BUSINESS_SECRET,
                start=3,
                end=14,
                confidence=0.8,
                source="qwen",
            ),
            Entity(
                text="liwenbo@example.com",
                entity_type=EntityType.PERSON,
                start=17,
                end=36,
                confidence=0.8,
                source="qwen",
            ),
        ]

    monkeypatch.setattr(
        routes.OllamaRecognizer, "analyze", fake_semantic_analyze
    )
    response = client.post(
        "/api/v1/analyze/text",
        json={"text": source, "use_llm": True},
    )
    assert response.status_code == 200
    entities = response.json()["entities"]
    assert [(item["text"], item["entity_type"]) for item in entities] == [
        ("13812345678", "PHONE"),
        ("liwenbo@example.com", "EMAIL"),
    ]
    assert all(item["conflict"] is False for item in entities)


def test_text_limit_is_enforced(client: TestClient) -> None:
    response = client.post(
        "/api/v1/analyze/text",
        json={"text": "字" * 50_001, "use_llm": False},
    )
    assert response.status_code == 422


def test_dictionary_and_settings_are_local_and_validated(
    client: TestClient,
) -> None:
    dictionary = [
        {
            "value": "重庆某城投集团",
            "entity_type": "ORGANIZATION",
            "enabled": True,
            "selected": True,
        }
    ]
    saved = client.put("/api/v1/dictionary", json=dictionary)
    assert saved.status_code == 200
    assert client.get("/api/v1/dictionary").json() == dictionary

    settings = client.get("/api/v1/settings").json()
    settings["entity_defaults"]["AMOUNT"] = True
    updated = client.put("/api/v1/settings", json=settings)
    assert updated.status_code == 200
    assert updated.json()["entity_defaults"]["AMOUNT"] is True


def test_invalid_mapping_returns_safe_error(client: TestClient) -> None:
    response = client.post(
        "/api/v1/restore/text",
        json={"text": "[PHONE_001]", "mapping": {"version": 999}},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "映射文件格式无效或版本不受支持"
