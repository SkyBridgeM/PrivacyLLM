# PrivacyLLM

简体中文 | [English](README_EN.md)

[![Release](https://img.shields.io/github/v/release/SkyBridgeM/PrivacyLLM)](https://github.com/SkyBridgeM/PrivacyLLM/releases/latest)
[![Tests](https://github.com/SkyBridgeM/PrivacyLLM/actions/workflows/tests.yml/badge.svg)](https://github.com/SkyBridgeM/PrivacyLLM/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-167469.svg)](LICENSE)

PrivacyLLM 是一款在本机运行的可逆文本脱敏工具。你可以把姓名、联系方式、机构、项目和业务秘密替换为占位符，再将处理后的文本交给 ChatGPT、Claude 等外部 AI。收到回复后，用保存在本地的映射恢复原文。

```text
原文：张敏负责北辰计划，联系电话 13812345678。
脱敏：[PERSON_001]负责[PROJECT_001]，联系电话 [PHONE_001]。
恢复：将 AI 回复中的占位符替换回原始内容。
```

v0.2.0 提供 Tauri + Rust + Svelte 桌面版。安装后双击打开即可使用，不需要安装 Python、Node.js、uv 或 Ollama，也不用另行启动模型服务。

## 下载与安装

| 平台                  | 安装包                                                                                                            | 要求                               |
| --------------------- | ----------------------------------------------------------------------------------------------------------------- | ---------------------------------- |
| macOS · Apple Silicon | [下载 v0.2.0 DMG](https://github.com/SkyBridgeM/PrivacyLLM/releases/download/v0.2.0/PrivacyLLM_0.2.0_aarch64.dmg) | M 系列芯片，macOS 13.3 或更高版本  |
| 其他平台              | 暂未提供安装包                                                                                                    | Intel Mac、Windows、Linux 尚未验收 |

当前 App 界面为中文，英文使用说明见 [README_EN.md](README_EN.md)。

1. 下载 DMG，将 PrivacyLLM 拖入“应用程序”。
2. 打开 App，粘贴文本，即可使用快速识别、脱敏和恢复功能。
3. 如需语义增强，进入“设置与模型”，下载默认模型或导入兼容 GGUF。

安装包约 29 MB，包含 llama.cpp 推理引擎，模型另行下载。默认模型约 2.74 GB，下载完成后可离线使用。

> v0.2.0 使用 ad hoc 签名，尚未完成 Developer ID 签名和 Apple 公证。如果 macOS 阻止打开，请先确认文件来自本仓库 Release，并核对校验值，再按“隐私与安全性”中的提示允许打开。不要关闭系统安全保护。具体步骤见 [Apple 官方说明](https://support.apple.com/zh-cn/102445)。

从同一条 Release 下载 DMG 和 `SHA256SUMS`，放在同一目录后运行：

```bash
shasum -a 256 -c SHA256SUMS
```

[全部版本与 SHA-256 校验文件](https://github.com/SkyBridgeM/PrivacyLLM/releases) · [更新记录](CHANGELOG.md)

## 主要功能

- 用格式规则识别手机号、邮箱、身份证、银行卡、统一社会信用代码、证券代码、金额、日期和 IP 地址，并对部分类型执行校验。
- 维护业务词典和自定义正则，补充项目名、客户名、部门和内部编号等专有内容。
- 可选用 llama.cpp 和本地模型识别人名、机构、项目、部门、地址及业务秘密。
- 逐项勾选或取消候选内容，修改类型和边界，处理重叠冲突。漏识别时，可以从原文或脱敏结果选中文字，手动补充。
- 同一类型的相同内容使用同一占位符，同时避让原文中已有的占位符。
- 导出映射 JSON，或用当前会话映射、导入的映射恢复文本。应用会提示未知占位符和未使用的映射。
- 下载、暂停续传或导入模型，按需加载和卸载。快速模式不加载模型，退出应用时会清理自建的推理进程。

手机号、身份证、统一社会信用代码和证券代码的内置规则主要面向中国大陆，其他类型也有各自的格式限制。金额、日期和证券代码默认不勾选，可在设置中调整。词典和格式规则均可在不安装模型的情况下使用。

## 使用流程

1. 在“脱敏工作台”粘贴原始文本，选择快速识别或语义增强。
2. 点击“识别敏感信息”，逐项复核候选内容；有漏项时选中文字手动补充。
3. 点击“生成脱敏文本”，复核结果后复制给外部 AI。如果稍后还要恢复文本，请导出映射文件。
4. 在“恢复文本”粘贴 AI 返回内容，使用当前会话映射或导入对应映射文件。
5. 点击“恢复文本”，检查恢复结果及未知占位符提示。

应用不会自动向外部 AI 发送文本。如果 AI 改写或删除了占位符，对应内容可能无法恢复。

## 本地模型

默认下载模型为 [Qwen3.5-4B Q4_K_M GGUF](https://huggingface.co/unsloth/Qwen3.5-4B-GGUF)，推理引擎固定为 [llama.cpp b12340](https://github.com/ggml-org/llama.cpp/releases/tag/b12340)。默认下载会校验文件大小与 SHA-256。

- 快速模式始终可以独立使用；首次选择语义增强时才加载模型。
- 可在“设置与模型”卸载模型，释放推理占用的内存。
- 已有 GGUF 可以导入，原文件保持不变；自选模型的兼容性需要实际加载验证。
- 默认上下文为 32,768 token，包含提示词和输出。长文应分段；50,000 字符输入上限不代表模型能处理等量文本。
- 模型与上下文会额外占用内存，实际速度取决于设备、模型及文本长度。尚未做完整的内存和速度对照测试，因此不提供固定的内存降幅或提速数据。

## 数据、隐私与旧版迁移

桌面版通过 Tauri 命令调用 Rust，不启动 Python 或应用 HTTP 服务。语义增强由应用管理的本机 llama.cpp 进程处理。这个进程只监听 `127.0.0.1`，每次启动生成新密钥。本机推理请求不经过 HTTP 代理，正文也不会发给远程推理服务。界面不使用外部字体或 CDN 资源。应用不收集遥测，也不记录模型输入输出。

模型下载和首次准备开发环境需要联网；安装完成后的文本处理、映射和恢复不需要联网。

用户数据与安装包分开存放：

```text
~/Library/Application Support/com.privacyllm.desktop/
├── config/
│   ├── dictionary.json
│   ├── custom_regex_rules.json
│   └── settings.json
└── models/
    └── semantic.gguf
```

保存配置时采用原子替换，并保留上一版本 `.bak` 备份。更新 App 不会覆盖这个目录。旧版用户可在“设置与模型”选择原项目的 `config` 文件夹导入；version 1 映射 JSON 可继续使用。

映射文件以明文 JSON 保存，包含原始敏感信息，请妥善保管，不要连同脱敏文本一起发送给外部 AI。自动识别可能漏项，发送前需要人工复核。更多说明见 [安全政策](SECURITY.md)。

## 从源码运行

需要 macOS、Node.js 22.12 或更高版本、Rust 1.96 或更高版本及 Xcode Command Line Tools。桌面版开发和构建均不需要 Python。

```bash
git clone https://github.com/SkyBridgeM/PrivacyLLM.git
cd PrivacyLLM
npm ci
npm run desktop:dev
```

首次运行会下载并校验固定版本的 Mac 推理引擎。模型通过 App 下载或导入。

构建 `.app` 和 `.dmg`：

```bash
npm run desktop:build
```

输出位于 `src-tauri/target/release/bundle/`。仅查看前端可运行 `npm run dev`；普通浏览器提供界面预览，实际文本处理使用桌面版。

### 测试

```bash
npm run build
npm test
cargo test --locked --manifest-path src-tauri/Cargo.toml
cargo clippy --locked --manifest-path src-tauri/Cargo.toml --all-targets -- -D warnings
cargo fmt --manifest-path src-tauri/Cargo.toml -- --check
```

Rust 测试覆盖识别、实体合并、字符边界、脱敏恢复、配置迁移、进程管理与 Tauri 命令分发；15 组 Python 对照样例用于核对迁移行为。真实模型测试需要单独启用，见 [开发与验证说明](docs/desktop.md)。CI 不下载大型模型。

### 保留的 Python 版本

原 FastAPI/浏览器版本保留用于行为对照，桌面版不依赖它。需要 Python 3.11+ 和 uv：

```bash
uv sync --extra dev
uv run python scripts/run_local.py
```

浏览器地址为 `http://127.0.0.1:8765`，仅监听本机。可选模型安装、环境变量与旧版测试命令见 [Python 版说明](docs/python.md)。

## 技术栈与许可

桌面版使用 Tauri 2 和 Rust，界面由 Svelte 5、TypeScript 和 Vite 构建，在系统 WebView 中运行。本地推理由随应用分发的 llama.cpp 执行，模型单独下载或导入。保留的旧版使用 Python、FastAPI 和 Pydantic。

PrivacyLLM 源码使用 [MIT License](LICENSE)。随附引擎和可选模型分别遵循各自许可证。
