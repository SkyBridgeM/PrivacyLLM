# PrivacyLLM Mac 桌面版

已实现 Tauri 2 + Rust + Svelte 5 + TypeScript 桌面版。Python 版本继续保留作对照，桌面版运行不需要 Python、uv、Ollama、Node.js 或 Homebrew。

## 安装与使用

当前构建目标为 Apple Silicon Mac（macOS 13.3+）：

- App：`src-tauri/target/release/bundle/macos/PrivacyLLM.app`
- DMG：`src-tauri/target/release/bundle/dmg/PrivacyLLM_0.2.0_aarch64.dmg`

打开 DMG 后将 App 拖到“应用程序”，或直接双击构建目录里的 App。快速模式不加载模型；首次使用语义增强时加载，暂时不用时可在“设置与模型”卸载模型。

模型独立存放，不包含在安装包中。首次使用可在“设置与模型”下载默认 GGUF（约 2.74 GB），或导入兼容 GGUF。默认下载校验 SHA-256，支持暂停及断点续传；导入模型检查 GGUF 文件头，兼容性以实际加载为准。默认上下文为 32,768 token，包含提示词和输出，长文应分段。

当前包使用 ad hoc 签名，并通过 `codesign --verify --deep --strict` 校验。尚未使用 Developer ID 签名及 Apple 公证，不能视为已经完成公开分发认证。此版本实测目标是当前 Apple Silicon Mac，未验收 Intel / Windows / Linux。

## 数据和旧版迁移

应用数据位于：

```text
~/Library/Application Support/com.privacyllm.desktop/
├── config/
│   ├── dictionary.json
│   ├── custom_regex_rules.json
│   └── settings.json
└── models/
    └── semantic.gguf
```

安装包与数据独立，更新应用不会覆盖该目录。已有 Python 项目可在设置中选择原 `config` 文件夹导入。导入会保留当前配置备份，不修改旧项目文件。旧版映射 JSON（version 1）可直接使用。

旧版配置和模型不会包含在 Release 安装包中。可通过应用导入已有文件，或下载默认模型。

## 功能范围

- 规则、词典、自定义正则和可选语义识别。
- 实体逐项选择、边界与类型编辑、重叠检查、删除。
- 从原文或脱敏结果选中文字，补充自定义脱敏。
- 稳定占位符、重复实体复用、既有占位符避让。
- 映射导出、当前会话恢复、旧映射导入、未知占位符提示。
- 默认脱敏策略、原子配置写入与上一版本备份。
- 本地模型导入、下载、加载、卸载和退出时清理。

自定义正则使用 fancy-regex，支持常用环视与反向引用，但不保证支持全部 Python `regex` 语法；不支持的表达式会在保存时明确报错。资源限制使用回溯次数和表达式大小上限，不沿用旧版 50 毫秒计时规则。

## 从源码运行

需要 Node.js 22.12+（已在 25.9 验证）、npm、Rust 1.96+（已在 1.96.1 验证）及 macOS Command Line Tools。本机不需要完整 Xcode 即可构建此版本。

```bash
git clone https://github.com/SkyBridgeM/PrivacyLLM.git
cd PrivacyLLM
npm ci
npm run desktop:dev
```

开发与构建脚本通过 Node.js 下载并校验固定版本的 Mac llama.cpp 引擎，不需要 Python。第一次准备引擎需要联网，下载约 16 MB。模型通过桌面 App 下载或导入。

构建安装包：

```bash
npm run desktop:build
```

仅查看前端：

```bash
npm run dev
```

普通浏览器仅提供界面预览，处理文本需要 Tauri 桌面应用；生产版本没有浏览器 HTTP 后端。

## 结构

| 路径                          | 职责                               |
| ----------------------------- | ---------------------------------- |
| `src-tauri/src/core.rs`       | 实体、规则、合并、脱敏与恢复       |
| `src-tauri/src/store.rs`      | 配置校验、原子保存、备份和迁移     |
| `src-tauri/src/model.rs`      | llama.cpp 生命周期、下载与语义识别 |
| `src-tauri/src/lib.rs`        | Tauri 命令与应用生命周期           |
| `frontend/src/App.svelte`     | 脱敏与恢复工作区                   |
| `frontend/src/components/`    | 高亮、词典、设置与模型管理         |
| `scripts/setup_engine.mjs`    | 固定版本 Mac 引擎安装与校验        |
| `scripts/prepare_desktop.mjs` | 准备安装包内引擎资源               |

前后端实体边界统一使用 Unicode 码点索引；Rust 在切片时转换为 UTF-8 字节位置，前端在文本选择时转换 UTF-16 位置。测试包含 emoji、生僻字与组合字符。

## 验证

```bash
npm run check
npm test
cargo test --manifest-path src-tauri/Cargo.toml
cargo clippy --manifest-path src-tauri/Cargo.toml --all-targets -- -D warnings
```

真实模型测试（需要本地模型及 Metal 访问权限）：

```bash
cargo test --manifest-path src-tauri/Cargo.toml --test model \
  real_local_model_round_trip_and_unload -- --ignored --nocapture
```

测试默认读取项目 `.runtime`；可使用 `PRIVACYLLM_TEST_ENGINE_PATH` 和 `PRIVACYLLM_TEST_MODEL_PATH` 指定安装包内引擎与应用数据模型。

2026-11-13 验证结果：

- Rust 13 项常规测试通过；真实模型测试单独运行通过。
- Python 对照样例 15 组，逐项核对识别、脱敏文本与映射内容。
- Tauri 命令层完成真实命令分发、camelCase 参数、脱敏恢复及语义不可用检查。
- TypeScript / Svelte 零错误、零警告；前端 2 项字符位置测试通过。
- Playwright 连接测试专用适配器调用真实 Rust 核心，完成词典保存、emoji 文本识别、结果内手动补充与恢复；1440×1000 和 390×844 无横向溢出。测试适配器只在 `/tmp` 中运行，不进入产品。
- 设计参考 `desktop-concept.png` 与最新实现截图均经图像查看工具检查，核对三栏结构、侧栏、字体层级、白底与青绿色、控件间距及高亮；补充了必需的空状态、错误、预览和模型管理交互。修复了固定高度下面板溢出遮挡底部操作的问题。
- 已在本机启动打包 App，并使用包内引擎及独立数据目录中的模型完成真实推理和恢复；模型加载约 6 秒，短样本推理约 7 秒，非性能基准。

界面自动化服务两次超时，因此界面交互使用 Playwright 浏览器验证，原生文件选择、剪贴板和 Finder 拖拽安装未做完整自动化点击验收。模型下载流程尚未通过桌面 UI 重新下载完整的 2.74 GB 文件；现有模型通过独立目录与包内引擎实测。

未做同口径的完整应用内存对照，不能据此宣称降低了某个百分比。当前默认不加载模型、可手动卸载模型，以及去除 Python 服务均已实现。
