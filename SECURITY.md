# Security Policy

PrivacyLLM processes sensitive text and mapping files locally. Please do not
include real personal data, credentials, private mappings, or confidential
documents in public bug reports.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting feature when it is enabled for
the repository. Include:

- the affected version or commit;
- reproduction steps using synthetic data;
- expected and observed behavior;
- potential impact.

Do not open a public issue for vulnerabilities that could expose local files,
mapping contents, sensitive text, or arbitrary code execution.

## Scope and limitations

- The Rust desktop UI calls native Tauri commands and does not start a Python
  or HTTP application server. The legacy Python WebUI listens on `127.0.0.1`.
- Semantic analysis is sent only to the application-owned llama.cpp process on
  `127.0.0.1`, using a per-launch API key and bypassing HTTP proxies.
- Engine and model downloads happen during explicit setup; normal operation
  does not need network access. Model input and output are not logged.
- Mapping exports are currently plaintext JSON and must be protected by the
  user.
- Detection is not guaranteed to find every sensitive item. Review results
  before sending text to an external service.
