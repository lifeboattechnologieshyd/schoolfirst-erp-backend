---
description: "Use when modifying Django settings files, adding environment variables, changing feature flags, or configuring integrations, databases, queues, or storage."
applyTo: "settings/**"
---

# Settings Conventions

## Session Close-Out

After Python code changes, follow the repo-level close-out validation in [AGENTS.md](../../AGENTS.md). Run `source ~/.zshrc && source .venv/bin/activate && ruff check . --output-format concise && ty check` from the repo root, and fix any failures before handoff.

## File Responsibilities

| File | Owns |
|------|------|
| `base.py` | Core Django config, feature flags, installed apps, middleware |
| `development.py` | Local dev overrides (DEBUG, etc.) |
| `production.py` | Production security settings, compression, static files |
| `auth.py` | DRF defaults, JWT config, CORS, OAuth, throttle scopes |
| `databases.py` | PostgreSQL config + `AppRouter` multi-db routing |
| `llm.py` | AWS Bedrock inference profile IDs and LLM config |
| `vector_store.py` | Qdrant connection settings |
| `crons.py` | Django-crontab job definitions |
| `queue.py` | RabbitMQ / Azure Service Bus broker config |
| `object_storage.py` | S3-compatible storage (MinIO, AWS S3) |
| `integrations.py` | Email (SMTP), OAuth provider secrets, third-party API keys |
| `urls.py` | Top-level URL composition (conditionally loads apps from INSTALLED_APPS) |

## Environment Variables

Always read env vars via `shared.utils.get_from_env()` — **never** use `os.environ` directly:

```python
from shared.utils import get_from_env, str_to_bool

DEBUG = get_from_env("DEBUG", default=False, type_cast=str_to_bool)
SOME_KEY = get_from_env("SOME_KEY", optional=True)
```

## Feature Flags

Feature flags are in `base.py` and control conditional middleware/URL loading:

| Flag | Controls |
|------|---------|
| `ENABLE_DOCS` | API documentation endpoints |
| `ENABLE_METRICS` | OpenTelemetry metrics |
| `ENABLE_TRACING` | OpenTelemetry tracing |
| `ENABLE_SILK` | Django Silk profiling |
| `ENABLE_HEALTHCHECKS` | Health check endpoints (required by Playwright webServer) |
| `ENABLE_EMAIL` | SMTP email delivery |

When adding a new optional feature, add a flag here and gate its middleware/URL with `if settings.ENABLE_X`.

## Database Routing

`config/db_router.AppRouter` routes queries by app label using `APP_TO_DB_MAPPING` in `databases.py`. When a new app is added, ensure it appears in `APP_TO_DB_MAPPING`. Do not call `.using()` for normal queries.

## Adding New Integrations

Put API keys and secrets in `integrations.py`. Read them via `get_from_env()`. Document the variable name in `.env.example`.

## Email (Local Dev)

For local dev with Mailpit: leave `EMAIL_HOST_USER` and `EMAIL_HOST_PASSWORD` empty. Set `DEFAULT_FROM_EMAIL` explicitly in `integrations.py`. `.env` values alone are inert — the Django mail settings in `integrations.py` must be defined.
