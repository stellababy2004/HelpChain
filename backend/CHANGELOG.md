# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

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
