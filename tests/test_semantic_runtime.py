import json
import subprocess

import pytest

from app.recognizers import llama_runtime, semantic_recognizer
from app.recognizers.llama_runtime import LlamaRuntime, SemanticUnavailable
from app.recognizers.semantic_recognizer import SemanticRecognizer


def test_missing_runtime_keeps_quick_mode_available(tmp_path, monkeypatch):
    monkeypatch.setenv("PRIVACYLLM_LLAMA_SERVER", str(tmp_path / "missing"))
    runtime = LlamaRuntime()
    runtime.start()
    assert runtime.status()["available"] is False
    assert "setup_llama.py" in runtime.status()["message"]
    with pytest.raises(SemanticUnavailable):
        runtime.request("/v1/chat/completions", {})


def test_runtime_owns_local_process_and_stops_it(tmp_path, monkeypatch):
    binary = tmp_path / "llama-server"
    model = tmp_path / "model.gguf"
    binary.touch()
    model.touch()
    monkeypatch.setenv("PRIVACYLLM_LLAMA_SERVER", str(binary))
    monkeypatch.setenv("PRIVACYLLM_MODEL_PATH", str(model))
    monkeypatch.setenv("LLAMA_ARG_HOST", "0.0.0.0")
    calls = []

    class Process:
        returncode = None
        terminated = False

        def poll(self):
            return self.returncode

        def terminate(self):
            self.terminated = True
            self.returncode = 0

        def wait(self, timeout=None):
            return self.returncode

    process = Process()

    def spawn(args, **kwargs):
        calls.append((args, kwargs))
        return process

    monkeypatch.setattr(llama_runtime.subprocess, "Popen", spawn)
    runtime = LlamaRuntime()
    monkeypatch.setattr(runtime, "request", lambda *args, **kwargs: {"status": "ok"})
    runtime.start()
    runtime.start()
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args[args.index("--host") + 1] == "127.0.0.1"
    assert args[args.index("--model") + 1] == str(model)
    assert args[args.index("--api-key") + 1] == runtime.api_key
    assert kwargs["stderr"] == subprocess.DEVNULL
    assert "LLAMA_ARG_HOST" not in kwargs["env"]
    assert runtime.status()["available"] is True
    runtime.stop()
    runtime.stop()
    assert process.terminated
    assert runtime.base_url == ""
    assert runtime.status()["available"] is False


def test_runtime_reports_process_start_failure(tmp_path, monkeypatch):
    binary = tmp_path / "llama-server"
    model = tmp_path / "model.gguf"
    binary.touch()
    model.touch()
    monkeypatch.setenv("PRIVACYLLM_LLAMA_SERVER", str(binary))
    monkeypatch.setenv("PRIVACYLLM_MODEL_PATH", str(model))

    def fail(*args, **kwargs):
        raise PermissionError("cannot execute")

    monkeypatch.setattr(llama_runtime.subprocess, "Popen", fail)
    runtime = LlamaRuntime()
    runtime.start()
    assert "无法启动" in runtime.status()["message"]
    runtime.stop()


def test_semantic_protocol_and_offset_validation(monkeypatch):
    source = "联系人张敏负责北辰计划。"

    def request(path, payload):
        assert path == "/v1/chat/completions"
        assert payload["response_format"]["json_schema"]["strict"] is True
        assert payload["chat_template_kwargs"]["enable_thinking"] is False
        return {"choices": [{"message": {"content": json.dumps({"entities": [
            {"text": "张敏", "entity_type": "PERSON", "start": 99, "end": 101,
             "confidence": 0.95, "reason": "联系人"},
            {"text": "虚构名称", "entity_type": "PROJECT", "start": 0, "end": 4,
             "confidence": 0.9, "reason": "错误候选"},
        ]})}}]}

    monkeypatch.setattr(semantic_recognizer.runtime, "request", request)
    entities = SemanticRecognizer().analyze(source)
    assert [(e.text, e.start, e.end, e.source) for e in entities] == [
        ("张敏", 3, 5, "semantic")
    ]


@pytest.mark.parametrize("response", [{}, {"choices": []}, {"choices": [{"message": {"content": "invalid"}}]}])
def test_semantic_invalid_response_is_safe_error(monkeypatch, response):
    monkeypatch.setattr(semantic_recognizer.runtime, "request", lambda *args: response)
    with pytest.raises(SemanticUnavailable, match="返回格式无效"):
        SemanticRecognizer().analyze("联系人张敏")


def test_startup_timeout_reaps_unready_process(tmp_path, monkeypatch):
    binary = tmp_path / "llama-server"
    model = tmp_path / "model.gguf"
    binary.touch()
    model.touch()
    monkeypatch.setenv("PRIVACYLLM_LLAMA_SERVER", str(binary))
    monkeypatch.setenv("PRIVACYLLM_MODEL_PATH", str(model))

    class Process:
        returncode = None
        killed = False

        def poll(self):
            return self.returncode

        def terminate(self):
            pass

        def wait(self, timeout=None):
            if not self.killed:
                raise subprocess.TimeoutExpired("llama-server", timeout)
            return self.returncode

        def kill(self):
            self.killed = True
            self.returncode = -9

    process = Process()
    monkeypatch.setattr(llama_runtime.subprocess, "Popen", lambda *args, **kwargs: process)
    runtime = LlamaRuntime()
    runtime.start(timeout=0)
    assert process.killed
    assert runtime.process is None
    assert runtime.base_url == ""
    assert "加载超时" in runtime.status()["message"]
