---
description: "Use when writing, running, or debugging Playwright API tests, including test setup, API client usage, or fixture patterns."
applyTo: "tests/**"
---

# Test Conventions

## Session Close-Out

After Python code changes, follow the repo-level close-out validation in [AGENTS.md](../../AGENTS.md). Run `source ~/.zshrc && source .venv/bin/activate && ruff check . --output-format concise && ty check` from the repo root, and fix any failures before handoff.

## Running Playwright Tests

**Always run from `tests/playwright/`**, not the repo root:

```bash
cd tests/playwright
npx playwright test
```

Running from the repo root will resolve the wrong Playwright package version and cause suite-loading errors.

## Prerequisite: Pending Migrations

The Playwright webServer checks the `/health/` endpoint at startup. `MigrationsHealthCheck` is part of that check and will **fail startup** if there are unapplied migrations.

Before running tests:
```bash
python manage.py migrate --settings=settings.development
```

## webServer and Health Check

`playwright.config.ts` waits for `/health/` to return 200 before running any tests. This means:
- The Django server must be running with `ENABLE_HEALTHCHECKS=True`.
- Migrations must be applied — a pending migration causes the health check to fail, which blocks all tests.

## API Client

The TypeScript API client lives in `tests/playwright/utils/api-client.ts`. Use it for all HTTP calls in tests rather than raw `fetch`/`axios` to ensure consistent auth headers and base URL handling.

## Test Organization

Tests mirror the app structure under `tests/playwright/tests/`:

```
tests/playwright/tests/
    assistant/
    auth/
    docusafe/
    calendar/
    family/
    feed/
    membership/
    profile/
    upload/
    workflows/     # multi-step cross-module flows
```

Add new tests to the matching module folder. Use `workflows/` for end-to-end scenarios that span multiple apps.

Backend automated coverage lives only under `tests/playwright/tests/` in this repo. Do **not** add Django or other Python test files under `apps/**/tests`.

## After API Changes

When a backend change affects request payloads, response bodies, status codes, or auth semantics:
1. Update the corresponding Playwright test in `tests/playwright/tests/<module>/`.
2. Update the Bruno request under `bruno/`.
3. After significant changes, ask the user whether to run the Playwright API tests now.
