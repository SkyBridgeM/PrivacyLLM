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

- The WebUI listens on `127.0.0.1` by default.
- Semantic analysis is sent only to the configured Ollama endpoint.
- Mapping exports are currently plaintext JSON and must be protected by the
  user.
- Detection is not guaranteed to find every sensitive item. Review results
  before sending text to an external service.
