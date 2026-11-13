# PrivacyLLM

[简体中文](README.md) | English

[![Release](https://img.shields.io/github/v/release/SkyBridgeM/PrivacyLLM)](https://github.com/SkyBridgeM/PrivacyLLM/releases/latest)
[![Tests](https://github.com/SkyBridgeM/PrivacyLLM/actions/workflows/tests.yml/badge.svg)](https://github.com/SkyBridgeM/PrivacyLLM/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-167469.svg)](LICENSE)

PrivacyLLM is a local tool for reversible text redaction. Replace names, contact details, organizations, projects, and business secrets with placeholders before sharing text with ChatGPT, Claude, or another external AI service. When the AI replies, use the mapping kept on your computer to restore the original values.

```text
Original: 张敏负责北辰计划，联系电话 13812345678。
Redacted: [PERSON_001]负责[PROJECT_001]，联系电话 [PHONE_001]。
Restore: Replace the placeholders in the AI reply with their original values.
```

Version 0.2.0 introduces a Tauri + Rust + Svelte desktop app. Once installed, open it directly. You do not need Python, Node.js, uv, Ollama, or a separately managed model server.

## Download and install

| Platform             | Download                                                                                                              | Requirements                                          |
| -------------------- | --------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| macOS, Apple Silicon | [Download v0.2.0 DMG](https://github.com/SkyBridgeM/PrivacyLLM/releases/download/v0.2.0/PrivacyLLM_0.2.0_aarch64.dmg) | M-series Mac, macOS 13.3 or later                     |
| Other platforms      | No installer available                                                                                                | Intel Mac, Windows, and Linux have not been validated |

The app currently has a Chinese interface. This README keeps the Chinese control names so you can find them in the app.

1. Download the DMG and drag PrivacyLLM into Applications.
2. Open the app and paste your text. Quick detection, redaction, and restoration work without a model.
3. For semantic detection, open Settings & models (`设置与模型`) and download the default model or import a compatible GGUF file.

The installer is about 29 MB and includes the llama.cpp inference engine. The model is a separate download. The default model is about 2.74 GB; once installed, it can run offline.

> Version 0.2.0 uses an ad hoc signature. It does not have an Apple Developer ID signature or notarization. If macOS blocks the app, confirm that it came from this repository's Release page and check the file checksum before allowing it in Privacy & Security. Do not disable system security protections. See [Apple's instructions](https://support.apple.com/en-us/102445).

Download the DMG and `SHA256SUMS` from the same Release, put them in the same directory, and run:

```bash
shasum -a 256 -c SHA256SUMS
```

[All releases and checksums](https://github.com/SkyBridgeM/PrivacyLLM/releases) · [Changelog (Chinese)](CHANGELOG.md)

## Features

- Use format rules to find mobile numbers, email addresses, ID numbers, bank card numbers, Unified Social Credit Codes, stock codes, amounts, dates, and IP addresses. Some types also undergo validation checks.
- Add project names, client names, departments, and internal identifiers through a business dictionary and custom regular expressions.
- Optionally use llama.cpp and a local model to identify people, organizations, projects, departments, addresses, and business secrets.
- Review individual matches, change their types and boundaries, and resolve overlaps. Select missed text in the original or redacted output to add it manually.
- Reuse a placeholder when the same value and type appear again. New placeholders do not reuse names already present in the source.
- Export mapping JSON, restore text with the current session's mapping, or import an existing mapping. The app reports unknown placeholders and unused mappings.
- Download a model with pause and resume support, or import one you already have. Load and unload it as needed. Quick mode does not load a model, and quitting the app stops the inference process it started.

The built-in rules for mobile numbers, ID numbers, Unified Social Credit Codes, and stock codes focus on mainland China. Other types also have format limits. Amounts, dates, and stock codes are not selected for redaction by default; you can change this in settings. Dictionary matching and format rules do not require a model.

## How to use it

1. Paste the original text into the redaction workspace (`脱敏工作台`). Choose quick detection (`快速识别`) or semantic detection (`语义增强`).
2. Click Detect sensitive information (`识别敏感信息`) and review the matches. Select missed text to add it manually.
3. Click Generate redacted text (`生成脱敏文本`). Review the output before copying it to an external AI service. Export the mapping if you need to restore the text later.
4. Paste the AI reply into Restore text (`恢复文本`). Use the current session's mapping or import the matching JSON file.
5. Click Restore text (`恢复文本`) and check the result, including any unknown-placeholder warnings.

The app does not send text to an external AI service for you. If the AI changes or removes a placeholder, the corresponding content may not be recoverable.

## Local models

The default download is [Qwen3.5-4B Q4_K_M GGUF](https://huggingface.co/unsloth/Qwen3.5-4B-GGUF). The bundled engine is pinned to [llama.cpp b12340](https://github.com/ggml-org/llama.cpp/releases/tag/b12340). The default download checks the file size and SHA-256 hash.

- Quick mode works independently. The app loads the model when you first use semantic detection.
- Unload the model in Settings & models (`设置与模型`) to release inference memory.
- Importing an existing GGUF leaves the original file unchanged. Load an imported model to check that it works with the bundled engine.
- The context limit is 32,768 tokens, including the prompt and output. Split long documents into sections. The 50,000-character input limit does not mean the model can process that much text in one request.
- Models and context consume additional memory. Speed depends on your hardware, model, and input length. Memory savings and inference speedups have not been measured in a controlled comparison.

## Data, privacy, and migration

The desktop interface calls Rust through Tauri commands. It does not start Python or an application HTTP server. For semantic detection, the app starts llama.cpp on `127.0.0.1` and generates a new API key for each launch. Local inference requests bypass HTTP proxies and do not go to a remote service. The interface loads no external fonts or CDN assets. The app does not collect telemetry or log model input or output.

Model downloads and the initial development setup require internet access. Text processing, mappings, and restoration work offline after setup.

User data is stored separately from the app:

```text
~/Library/Application Support/com.privacyllm.desktop/
├── config/
│   ├── dictionary.json
│   ├── custom_regex_rules.json
│   └── settings.json
└── models/
    └── semantic.gguf
```

Configuration saves use atomic replacement and retain the previous version as a `.bak` file. Updating the app does not overwrite this directory. To migrate from the older version, import the original project's `config` folder in Settings & models (`设置与模型`). Mapping JSON files with `"version": 1` remain compatible.

Mapping files are plain JSON and contain the original sensitive values. Keep them private, and do not send them to an external AI service alongside the redacted text. Detection can miss sensitive content, so review the output before sharing it. See the [security policy](SECURITY.md).

## Run from source

You need macOS, Node.js 22.12 or later, Rust 1.96 or later, and Xcode Command Line Tools. You do not need Python to develop or build the desktop app.

```bash
git clone https://github.com/SkyBridgeM/PrivacyLLM.git
cd PrivacyLLM
npm ci
npm run desktop:dev
```

The first run downloads and verifies the pinned Mac inference engine. Download or import a model through the app.

To build the `.app` and `.dmg`:

```bash
npm run desktop:build
```

Build output is in `src-tauri/target/release/bundle/`. Run `npm run dev` to preview the interface in a browser; text processing requires the desktop app.

### Tests

```bash
npm run build
npm test
cargo test --locked --manifest-path src-tauri/Cargo.toml
cargo clippy --locked --manifest-path src-tauri/Cargo.toml --all-targets -- -D warnings
cargo fmt --manifest-path src-tauri/Cargo.toml -- --check
```

Rust tests cover detection, merging, character offsets, redaction and restoration, configuration migration, process management, and Tauri command dispatch. 15 Python reference cases check migration behavior. Tests that load a real model run only when explicitly enabled. See the [development and verification notes (Chinese)](docs/desktop.md). CI does not download large models.

### Legacy Python version

The FastAPI/browser version remains available for behavior comparisons. The desktop app does not depend on it. To run it, you need Python 3.11+ and uv:

```bash
uv sync --extra dev
uv run python scripts/run_local.py
```

The browser opens at `http://127.0.0.1:8765`, which listens on loopback only. See the [Python version notes (Chinese)](docs/python.md) for optional model setup, environment variables, and test commands.

## Stack and licenses

The desktop app uses Tauri 2 and Rust. Svelte 5, TypeScript, and Vite build the interface, which runs in the system WebView. The bundled llama.cpp engine handles local inference, with models downloaded or imported separately. The legacy app uses Python, FastAPI, and Pydantic.

PrivacyLLM source code is available under the [MIT License](LICENSE). The bundled engine and optional models have their own licenses.
