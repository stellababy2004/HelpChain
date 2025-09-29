# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

No changes yet.

## [v0.1.0] - 2025-09-29

### Added

- Refactored and stabilized unit tests:
  - Mocked HTTP requests for chatbot tests (no running server required).
  - Added fixtures for session/message and a conftest.py fix for PYTHONPATH.
- Safe welcome email test via SMTP mocking (no external SMTP calls).
- Added full MIT LICENSE and created tag `v0.1.0`.
- Configured and validated pre-commit hooks (black, ruff).

### Tests

- 13 tests passed locally (pytest).
- pre-commit checks passing locally.

[v0.1.0]: https://github.com/stellababy2004/HelpChain.bg/releases/tag/v0.1.0
[v0.1.0-compare]: https://github.com/stellababy2004/HelpChain.bg/compare/v0.1.0...HEAD
