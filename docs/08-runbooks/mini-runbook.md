# Mini Runbook

Use this short runbook for a quick confidence check after a local change or controlled deployment.

1. Run `pytest tests/test_request_flow_smoke.py`.
2. Run `pytest tests/test_system_health_smoke.py`.
3. Open `/health` and confirm the service responds correctly.
4. Open `/admin/login` and confirm the admin entry point renders.
