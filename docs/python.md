# Python 对照版本

原 Python / FastAPI 版本继续保留，便于对照迁移行为或使用本机浏览器流程。主桌面应用的安装和运行不需要这些依赖。

## 安装和启动

需要 Python 3.11+ 和 [uv](https://docs.astral.sh/uv/)。

```bash
git clone https://github.com/SkyBridgeM/PrivacyLLM.git
cd PrivacyLLM
uv sync --extra dev
uv run python scripts/run_local.py
```

浏览器会在服务就绪后自动打开 `http://127.0.0.1:8765`。应用仅监听本机回环地址。

## 可选语义增强

```bash
uv run python scripts/setup_llama.py
uv run python scripts/run_local.py
```

安装脚本下载并校验固定版本的 llama.cpp 和 Qwen3.5-4B Q4_K_M GGUF。也可复制已有兼容模型：

```bash
uv run python scripts/setup_llama.py --model-file /absolute/path/model.gguf
```

原文件保持不变。推理引擎与模型存放在项目 `.runtime/`，正常运行不需要 Ollama。模型默认上下文为 32,768 token，长文请分段。

可选覆盖本地文件路径：

```bash
PRIVACYLLM_LLAMA_SERVER=/absolute/path/llama-server \
PRIVACYLLM_MODEL_PATH=/absolute/path/model.gguf \
uv run python scripts/run_local.py
```

模型不可用时，快速模式仍可使用。引擎加载完成前不会打开浏览器；加载失败或超时后会保留快速模式。

## 配置与测试

本地配置位于项目 `config/`：词典 `dictionary.json`、自定义规则 `custom_regex_rules.json`、默认策略 `settings.json`。迁移桌面版时可在“设置与模型”中选择此目录导入。

```bash
uv run --extra dev python -m pytest
```

单独运行真实模型测试：

```bash
PRIVACYLLM_TEST_LOCAL_MODEL=1 uv run --extra dev python -m pytest -s tests/test_local_model.py
```

正文仅发送到应用管理的本机推理进程，映射导出包含原文。相关限制见 [安全政策](../SECURITY.md)。
