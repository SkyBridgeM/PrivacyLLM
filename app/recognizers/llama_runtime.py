from __future__ import annotations

import atexit
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import threading
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DIR = PROJECT_ROOT / ".runtime"
DEFAULT_MODEL = RUNTIME_DIR / "models" / "semantic.gguf"


class SemanticUnavailable(RuntimeError):
    pass


class LlamaRuntime:
    """Own one loopback-only llama.cpp process; never connect to an external service."""

    def __init__(self) -> None:
        self.process: subprocess.Popen | None = None
        self.base_url = ""
        self.api_key = secrets.token_urlsafe(32)
        self.error = "尚未启动本地语义模型"
        self._lock = threading.Lock()
        # Local model traffic must not be routed through HTTP_PROXY.
        self._opener = build_opener(ProxyHandler({}))

    @property
    def model_path(self) -> Path:
        return Path(os.getenv("PRIVACYLLM_MODEL_PATH", str(DEFAULT_MODEL))).expanduser()

    def request(
        self, path: str, payload: dict[str, Any] | None = None, timeout: float = 180
    ) -> dict[str, Any]:
        if not self.base_url or self.process is None or self.process.poll() is not None:
            raise SemanticUnavailable(self.error or "本地推理进程已退出，请重启应用")
        request = Request(
            f"{self.base_url}{path}",
            data=None if payload is None else json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="GET" if payload is None else "POST",
        )
        try:
            with self._opener.open(request, timeout=timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            # Server errors may contain input text. Do not expose response bodies.
            raise SemanticUnavailable("本地语义模型请求失败，可能正在加载、输入过长或内存不足") from exc
        if not isinstance(body, dict):
            raise SemanticUnavailable("本地语义模型返回了无法识别的数据")
        return body

    def start(self, timeout: float = 120) -> None:
        with self._lock:
            if self.process is not None and self.process.poll() is None:
                return
            binary = Path(os.getenv(
                "PRIVACYLLM_LLAMA_SERVER", str(RUNTIME_DIR / "llama.cpp" / "llama-server")
            )).expanduser()
            if not binary.is_file() or not self.model_path.is_file():
                self.error = "尚未安装推理引擎或模型，请运行 uv run python scripts/setup_llama.py"
                return
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                port = listener.getsockname()[1]
            self.base_url = f"http://127.0.0.1:{port}"
            self.error = "本地语义模型正在加载"
            try:
                self.process = subprocess.Popen(
                    [str(binary), "--model", str(self.model_path),
                     "--host", "127.0.0.1", "--port", str(port),
                     "--alias", "privacyllm-local", "--ctx-size", "32768",
                     "--parallel", "1", "--gpu-layers", "99",
                     "--jinja", "--reasoning-budget", "0",
                     "--no-webui", "--log-disable",
                     "--api-key", self.api_key],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    # Do not inherit llama.cpp model/server overrides from the shell.
                    env={key: value for key, value in os.environ.items()
                         if not key.startswith("LLAMA_")},
                )
            except OSError:
                self.error = "无法启动本地推理引擎，请重新运行安装脚本并检查 macOS 执行权限"
                return
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if self.process.poll() is not None:
                    self.error = f"本地推理引擎启动失败（退出码 {self.process.returncode}），请检查模型兼容性和可用内存"
                    return
                try:
                    if self.request("/health", timeout=1).get("status") == "ok":
                        self.error = ""
                        return
                except SemanticUnavailable:
                    pass
                time.sleep(0.25)
            self.error = "本地语义模型加载超时，请检查模型和可用内存后重启应用"
            self._stop_process()

    def _stop_process(self) -> None:
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
            self.process = None
        self.base_url = ""

    def stop(self) -> None:
        with self._lock:
            self._stop_process()
            self.error = "本地语义模型已停止"

    def status(self) -> dict[str, Any]:
        available = False
        message = self.error
        if not self.error:
            try:
                available = self.request("/health", timeout=2).get("status") == "ok"
                message = "本地语义模型已就绪" if available else "本地语义模型暂不可用"
            except SemanticUnavailable as exc:
                message = str(exc) or "本地推理进程已退出，请重启应用"
        return {
            "available": available,
            "provider": "llama.cpp",
            "model": self.model_path.name,
            "message": message,
        }


runtime = LlamaRuntime()
atexit.register(runtime.stop)
