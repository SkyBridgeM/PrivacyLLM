# PrivacyLLM

面向个人使用的本地可逆脱敏工具。在把文本发送给外部 AI 前，先在本机识别并替换敏感信息；外部 AI 返回结果后，再使用当前会话映射恢复原文。

## 功能

- 常见格式化敏感信息识别；
- 本地 JSON 业务词典和自定义规则；
- 通过本机 Ollama 与 `qwen3.5:4b` 进行语义增强识别；
- 识别结果复核、冲突处理和手动补充脱敏；
- 稳定、可读的占位符；
- 明文 JSON 映射；
- 对外部 AI 改写文本进行精确恢复；
- 本地 FastAPI 服务和原生 WebUI；
- 业务词典和默认脱敏策略管理。

当前暂未包含 DOCX 和映射加密。

## 安装

要求：

- Python 3.11 或更高版本；
- [uv](https://docs.astral.sh/uv/)；
- 可选：[Ollama](https://ollama.com/) 和 `qwen3.5:4b`。

```bash
git clone <your-repository-url>
cd PrivacyLLM
uv sync --extra dev
```

如需语义增强：

```bash
ollama pull qwen3.5:4b
```

## 本地启动

```bash
uv run python scripts/run_local.py
```

应用只监听 `127.0.0.1:8765`，启动后会打开本机浏览器。WebUI 不引用 CDN、外部字体、遥测或其他网络资源。

语义增强默认连接 `http://127.0.0.1:11434`，使用 `qwen3.5:4b`。可通过 `PRIVACYLLM_OLLAMA_URL` 和 `PRIVACYLLM_OLLAMA_MODEL` 环境变量覆盖。

## 本地配置

业务词典与自定义规则配置分别保存在：

- `config/dictionary.json`
- `config/custom_regex_rules.json`

配置写入组件会先完成结构校验，再原子替换原文件，并保留一份
`.bak` 备份。自定义规则使用带执行时限的正则引擎。

## 测试

```bash
uv run --extra dev python -m pytest
```

## 安全说明

- 映射文件当前是明文 JSON，请勿上传到公共仓库或发送给外部服务。
- 自动识别无法保证覆盖全部敏感信息，发送前仍需人工复核。
- 若把 Ollama 地址改为远程服务，语义增强文本将发送到该地址。
- 报告安全问题时请使用合成数据，详见 [SECURITY.md](SECURITY.md)。

## 许可证

本项目使用 [MIT License](LICENSE)。
