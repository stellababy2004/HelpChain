# HelpChain application package

`backend/helpchain_backend/` is an internal Python package of the HelpChain repository. It is not a standalone repository or independently deployed application.

The application factory and runtime configuration are under `backend/helpchain_backend/src/`. Application configuration is defined in `backend/helpchain_backend/src/config.py`.

## Setup

Run setup commands from the repository root:

```pwsh
pip install -r requirements.txt
Copy-Item .env.example .env
```

`requirements.txt` is the canonical runtime dependency manifest. `.env.example` is the canonical environment template; review its placeholder values before starting the application.

## Local execution

From the repository root:

```pwsh
python run.py
```

## Tests

Run tests from the repository root so the canonical root `pytest.ini` is used:

```pwsh
pytest
```
