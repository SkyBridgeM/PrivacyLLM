"""Opt-in smoke test: PRIVACYLLM_TEST_LOCAL_MODEL=1 uv run python -m pytest -s tests/test_local_model.py"""
import os
import time

from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.recognizers.llama_runtime import runtime


@pytest.mark.skipif(
    os.getenv("PRIVACYLLM_TEST_LOCAL_MODEL") != "1",
    reason="requires an installed local llama.cpp engine and GGUF model",
)
def test_local_model_round_trip_and_shutdown():
    started = time.monotonic()
    process = None
    try:
        with TestClient(app) as client:
            status = client.get("/api/v1/model/status").json()
            print(f"\nModel startup: {time.monotonic() - started:.2f}s; {status}", flush=True)
            assert status["available"], status["message"]
            assert status["provider"] == "llama.cpp"
            process = runtime.process
            source = "张敏是星河科技有限公司的项目经理，负责北辰计划。联系电话13812345678。"
            started = time.monotonic()
            response = client.post(
                "/api/v1/analyze/text", json={"text": source, "use_llm": True}
            )
            assert response.status_code == 200, response.json()
            entities = response.json()["entities"]
            print(f"Inference: {time.monotonic() - started:.2f}s; entities: "
                  f"{[(e['text'], e['entity_type'], e['source']) for e in entities]}", flush=True)
            assert any(e["source"] == "semantic" and e["text"] == "张敏" for e in entities)
            assert all(source[e["start"]:e["end"]] == e["text"] for e in entities)
            redacted = client.post(
                "/api/v1/anonymize/text", json={"text": source, "entities": entities}
            )
            assert redacted.status_code == 200
            payload = redacted.json()
            assert "张敏" not in payload["text"]
            assert "13812345678" not in payload["text"]
            restored = client.post(
                "/api/v1/restore/text", json={"text": payload["text"], "mapping": payload["mapping"]}
            )
            assert restored.status_code == 200
            assert restored.json()["text"] == source
    finally:
        if process is not None:
            assert process.poll() is not None, "application-owned inference process was not stopped"
