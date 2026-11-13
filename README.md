# PrivacyLLM

[![Release](https://img.shields.io/github/v/release/SkyBridgeM/PrivacyLLM)](https://github.com/SkyBridgeM/PrivacyLLM/releases/latest)
[![Tests](https://github.com/SkyBridgeM/PrivacyLLM/actions/workflows/tests.yml/badge.svg)](https://github.com/SkyBridgeM/PrivacyLLM/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-167469.svg)](LICENSE)

**把敏感信息留在本机，再把文本交给 AI。**

PrivacyLLM 是一款本地运行的可逆文本脱敏工具。发送内容给 ChatGPT、Claude 或其他外部 AI 之前，先将姓名、联系方式、机构、项目和业务秘密替换为稳定占位符；收到 AI 回复后，再用本地映射恢复原文。

```text
原文：张敏负责北辰计划，联系电话 13812345678。
脱敏：[PERSON_001]负责[PROJECT_001]，联系电话 [PHONE_001]。
恢复：将 AI 回复中的占位符替换回原始内容。
```

v0.2.0 将主应用迁移为 **Tauri + Rust + Svelte 桌面版**。安装后双击使用，无需 Python、Node.js、uv、Ollama 或另行启动模型服务。

## 下载与安装

| 平台                  | 安装包                                                                                                            | 要求                               |
| --------------------- | ----------------------------------------------------------------------------------------------------------------- | ---------------------------------- |
| macOS · Apple Silicon | [下载 v0.2.0 DMG](https://github.com/SkyBridgeM/PrivacyLLM/releases/download/v0.2.0/PrivacyLLM_0.2.0_aarch64.dmg) | M 系列芯片，macOS 13.3 或更高版本  |
| 其他平台              | 暂未提供安装包                                                                                                    | Intel Mac、Windows、Linux 尚未验收 |

1. 下载 DMG，将 **PrivacyLLM** 拖入“应用程序”。
2. 打开 App，粘贴文本，即可使用快速识别、脱敏和恢复功能。
3. 如需语义增强，进入“设置与模型”，下载默认模型或导入兼容 GGUF。

安装包约 **29 MB**，已包含 llama.cpp 推理引擎，**不包含模型**。默认模型另需下载约 **2.74 GB**；下载完成后可离线使用。

> v0.2.0 使用 ad hoc 签名，尚未完成 Developer ID 签名及 Apple 公证。如果 macOS 阻止打开，请先确认下载来自本仓库 Release、校验文件，再按系统“隐私与安全性”中的提示允许打开。不要关闭系统安全保护。[Apple 官方操作说明](https://support.apple.com/zh-cn/102445)。

在 Release 下载 DMG 和 `SHA256SUMS`，放在同一目录后可验证：

```bash
shasum -a 256 -c SHA256SUMS
```

[全部版本与 SHA-256 校验文件](https://github.com/SkyBridgeM/PrivacyLLM/releases) · [更新记录](CHANGELOG.md)

## 主要功能

- **快速识别**：手机号、邮箱、身份证、银行卡、统一社会信用代码、证券代码、金额、日期和 IP 地址，并对部分类型执行校验。
- **业务词典与自定义正则**：补充项目名、客户名、部门和内部编号等专有内容。
- **本地语义增强**：通过 llama.cpp 和本地模型识别人名、机构、项目、部门、地址及业务秘密。
- **逐项复核**：勾选或取消候选项，修改类型和边界，处理重叠冲突；从原文或脱敏结果选中文字，补充漏识别内容。
- **可逆替换**：同一类型的相同内容使用同一占位符，并避让原文中已有的占位符。
- **映射导出与恢复**：使用当前会话映射，或导入已有映射 JSON；提示未知占位符和未使用的映射。
- **按需管理模型**：支持下载、暂停续传、导入、加载与卸载；快速模式不加载模型，退出应用时清理自建推理进程。

金额、日期和证券代码默认不勾选，可在设置中调整。词典匹配与格式规则不要求安装模型。

## 使用流程

1. 在“脱敏工作台”粘贴原始文本，选择快速识别或语义增强。
2. 点击“识别敏感信息”，逐项复核候选内容；有漏项时选中文字手动补充。
3. 点击“生成脱敏文本”，复核结果后复制给外部 AI。需要稍后恢复时，导出映射文件。
4. 在“恢复文本”粘贴 AI 返回内容，使用当前会话映射或导入对应映射文件。
5. 点击“恢复文本”，检查恢复结果及未知占位符提示。

应用不会替你自动向外部 AI 发送文本。AI 若改写或删除占位符，对应部分可能无法恢复。

## 本地模型

默认下载模型为 [Qwen3.5-4B Q4_K_M GGUF](https://huggingface.co/unsloth/Qwen3.5-4B-GGUF)，推理引擎固定为 [llama.cpp b12340](https://github.com/ggml-org/llama.cpp/releases/tag/b12340)。默认下载会校验文件大小与 SHA-256。

- 快速模式始终可以独立使用；首次选择语义增强时才加载模型。
- 可在“设置与模型”卸载模型，释放推理占用的内存。
- 已有 GGUF 可以导入，原文件保持不变；自选模型的兼容性需要实际加载验证。
- 默认上下文为 32,768 token，包含提示词和输出。长文应分段；50,000 字符输入上限不代表模型能处理等量文本。
- 模型与上下文会额外占用内存，实际速度取决于设备、模型及文本长度。本次迁移未承诺固定的内存降幅或推理提速。

## 数据、隐私与旧版迁移

桌面版通过 Tauri 命令调用 Rust，不启动 Python 或应用 HTTP 服务。语义增强只调用应用管理的本机 llama.cpp 进程，监听 `127.0.0.1`、使用每次启动生成的密钥，正文不经过代理或远程推理地址。不使用外部字体、CDN、遥测，也不记录模型输入输出。

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

保存配置时采用原子替换，并保留上一版本 `.bak` 备份。更新 App 不覆盖该目录。旧版用户可在“设置与模型”选择原项目的 `config` 文件夹导入；version 1 映射 JSON 可继续使用。

**映射文件包含原始敏感信息，目前以明文 JSON 导出。** 请妥善保存，不要连同脱敏文本一起发送给外部 AI。识别无法保证覆盖全部敏感信息，发送前需要人工复核。更多说明见 [安全政策](SECURITY.md)。

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

原 FastAPI / 浏览器版本保留用于行为对照，桌面版不依赖它。需要 Python 3.11+ 和 uv：

```bash
uv sync --extra dev
uv run python scripts/run_local.py
```

浏览器地址为 `http://127.0.0.1:8765`，仅监听本机。可选模型安装、环境变量与旧版测试命令见 [Python 版说明](docs/python.md)。

## 技术栈与许可

- **桌面与后端**：Tauri 2、Rust。
- **界面**：Svelte 5、TypeScript、Vite，使用系统 WebView。
- **本地推理**：随应用分发的 llama.cpp；模型独立下载或导入。
- **旧版对照**：Python、FastAPI、Pydantic。

PrivacyLLM 源码使用 [MIT License](LICENSE)。随附引擎和可选模型分别遵循各自许可证。
