# SamsR Backend - Repository Instructions

This file owns repository-specific guidance for AI agents working in this codebase.

- Use [AGENTS.md](../AGENTS.md) for workflow, autonomy, escalation, and validation order.
- Use task skills in [../.agents/skills](../.agents/skills) for focused recipes.
- Keep this file about the codebase itself: architecture, conventions, commands, and integration requirements.

## Repository Snapshot

- Django REST Framework backend on Django 5.2 and DRF 3.16.
- PostgreSQL with multi-database routing.
- OAuth2 and JWT authentication.
- OpenTelemetry, structlog, RabbitMQ, and S3-compatible object storage.
- Docker-based deployment with API, cron, and combined runtime modes.

## Shared Agent Context Docs

Shared agent context for this repository lives under [docs/superpowers/](../docs/superpowers/).

- [docs/superpowers/README.md](../docs/superpowers/README.md) describes the canonical layout and write rules.
- [docs/superpowers/specs/](../docs/superpowers/specs/) holds approved design docs.
- [docs/superpowers/plans/](../docs/superpowers/plans/) holds active implementation plans and handoff notes. Use `YYYY-MM-DD-topic-plan.md` names.
- [docs/superpowers/memory/repo-facts.md](../docs/superpowers/memory/repo-facts.md) holds verified repo facts and conventions worth reusing.
- [docs/superpowers/memory/technical-preferences.md](../docs/superpowers/memory/technical-preferences.md) holds non-sensitive technical user preferences that affect work in this repo.
- [docs/superpowers/memory/open-questions-and-risks.md](../docs/superpowers/memory/open-questions-and-risks.md) holds unresolved questions, risks, and follow-up decisions.
- [docs/superpowers/decisions/](../docs/superpowers/decisions/) holds durable decisions and constraints. Use `YYYY-MM-DD-topic-decision.md` names when a decision deserves its own file.
- [docs/superpowers/investigations/](../docs/superpowers/investigations/) holds debugging and root-cause notes. Use `YYYY-MM-DD-topic-investigation.md` names.
- Prefer updating an existing context doc over creating a new file when the same topic is still active.
- Keep entries terse, technical, and safe to commit.

## High-Signal App Map

- `apps/core`: user model, auth flows, profile, invitations, uploads, family, close groups, and membership.
- `apps/feed`: social feed posts, comments, reactions, shares, and visibility.
- `apps/assistant`: chat threads, messages, intents, graph logic, and LLM provider orchestration (AWS Bedrock + LangGraph).
- `apps/docusafe`: files, folders, hybrid search, temporary sharing, access control, and document workflows.
- `apps/calendar`: events, tasks, comments, recurring events (RRULE), and unified calendar view.

Module-specific coding rules are in [.github/instructions/](./instructions/) Files with `applyTo` patterns load automatically when you work in the matching directory.

## Architectural Invariants

### Settings layout

Settings are intentionally split under `settings/`.

- `base.py`: shared config, feature flags, installed apps.
- `development.py`: local dev overrides.
- `production.py`: production overrides.
- `auth.py`: DRF, JWT, CORS, OAuth, throttling.
- `databases.py`: database config and routing.
- `llm.py`: AWS Bedrock inference profile IDs and LLM configuration.
- `vector_store.py`: Qdrant vector DB connection.
- `crons.py`: scheduled jobs.
- `queue.py`: broker configuration (RabbitMQ / Azure Service Bus).
- `object_storage.py`: S3-compatible file storage configuration.
- `integrations.py`: email (SMTP), OAuth secrets, and third-party API keys.
- `urls.py`: top-level URL composition.

### Database routing

- `config/db_router.AppRouter` routes database operations by app label using `APP_TO_DB_MAPPING`.
- Do not manually force `.using()` for normal model operations.
- Avoid cross-database relations and joins.
- When a model change affects routing assumptions, verify the app label and migration target.

### Service-layer pattern

- Business logic should live in app services when it would otherwise bloat views, serializers, or models.
- External integrations use provider abstractions. Example: assistant LLM providers and OAuth providers.

### Loose coupling across apps

- When tight coupling is undesirable, prefer `UUIDField` references over cross-app `ForeignKey` usage.
- Assistant thread and message ownership already follow this pattern.

## Model Conventions

- Prefer `AuditModel` for full timestamp and user tracking.
- Use `TimeAuditModel` only when request user audit fields are not needed.
- Use `UUIDField` primary keys with `default=uuid.uuid4`.
- Set explicit `db_table` names in snake_case.
- Add explicit indexes for lookup and filter fields.
- Use `models.TextChoices` or `models.IntegerChoices` for enums.
- Never use `blank=True` on model fields.
- Use `null=True` for optional database columns.

Audit behavior depends on `crum` request context. If a change touches audit assumptions, verify middleware expectations before changing model save behavior.

## Serializer Conventions

- Keep serializers in `apps/<app>/serializers/`, grouped by feature when helpful.
- Never use `blank=True` on serializer fields.
- Use `required=False` for optional fields.
- Use `allow_blank=True` only for optional string inputs.
- Use `allow_null=True` only for explicitly nullable inputs.
- Use nested serializers for structured client or device metadata instead of loose dicts.
- Use `ChoiceField` with shared enums when the values are already standardized.

## View And Response Conventions

- Import DRF generics from `shared.mixins.drf_views`, not from `rest_framework.generics`.
- Use the custom response helpers and preserve the standard response shape: `{success, message, data, error, meta}`.
- Default permission behavior comes from settings; public endpoints must declare `permission_classes = [AllowAny]` explicitly.
- Set `throttle_scope` on rate-limited endpoints when appropriate.
- Use routers for `ViewSet` CRUD APIs.
- Keep URL names descriptive for reverse lookups.

Preferred success response pattern:

```python
return self.build_response(
    success=True,
    data=serializer.data,
    status=status.HTTP_200_OK,
)
```

Preferred validation error pattern:

```python
return self.build_response(
    success=False,
    error={
        "code": GlobalAPIMessageCodes.VALIDATION_ERROR,
        "message": GlobalAPIMessageCodes.VALIDATION_ERROR.label,
        "details": [{"type": "field", "field": "email", "message": "Required"}],
    },
    status=status.HTTP_400_BAD_REQUEST,
)
```

## URL And API Layout

- Keep APIs explicitly versioned where that pattern already exists, such as `/api/v1/auth/`.
- `settings/urls.py` conditionally loads app URLs from `INSTALLED_APPS`.
- Prefer `DefaultRouter` for `ViewSet` registrations.
- Keep app-local URL modules focused and feature-oriented.

## Environment And Feature Flags

- Always read environment variables via `shared.utils.get_from_env()`.
- Do not access `os.environ` directly in project code.
- Use `type_cast=str_to_bool` for booleans and explicit type casts for numerics.
- Mark optional environment variables with `optional=True`.

Feature flags are centered in `settings/base.py`.

- `ENABLE_DOCS`
- `ENABLE_METRICS`
- `ENABLE_TRACING`
- `ENABLE_SILK`
- `ENABLE_HEALTHCHECKS`
- `ENABLE_EMAIL`

If a feature is optional, verify both the setting and the conditional URL or middleware loading path before changing behavior.

## Authentication And Integrations

### Authentication

- Custom user model: `apps.core.models.UserMaster`.
- JWT is provided by `rest_framework_simplejwt` with refresh rotation and blacklist support.
- Google OAuth is implemented through the shared OAuth provider abstraction and returns a normalized `OAuthUserInfo` payload.

### Observability

- OpenTelemetry wiring lives under `config/metrics.py` and related settings.
- Structured logging uses `structlog` and `django-structlog`.
- Trace and metrics behavior are feature-flag controlled.

### Storage And Queueing

- Object storage configuration lives in `settings/object_storage.py`.
- Queue and broker configuration lives in `settings/queue.py`.
- Deployment behavior is controlled by `DEPLOYMENT_MODE` in the Docker entrypoint.

## Required Validation Behavior

### Python environment

Before running Python or Django commands in a terminal:

1. Create `.venv` if it is missing: `python3.14 -m venv .venv`
2. Activate it: `source .venv/bin/activate`
3. Install local dependencies: `pip install -r requirements/development.txt`

### Common commands

```bash
python manage.py runserver --settings=settings.development
python manage.py makemigrations
python manage.py migrate --settings=settings.development
ruff check --fix .
ruff format .
```

### Mandatory session close-out

After any session that changes Python code or fixes diagnostics, run these commands from the repo root and fix any failures before handoff:

```bash
source ~/.zshrc
source .venv/bin/activate
ruff check . --output-format concise
ty check
```

### API contract changes

If a backend change affects request payloads, response bodies, status codes, auth behavior, or documented endpoint semantics:

- Update the relevant Bruno requests under `bruno/`.
- Update the corresponding Playwright API coverage under `tests/playwright/tests`.
- After significant backend API changes, ask the user whether to run the Playwright API tests now.

## File Placement Conventions

- Views: `apps/<app>/views/<feature>/` when the app already uses feature subpackages.
- Models: `apps/<app>/models/` with one domain-oriented file per entity when practical.
- Serializers: `apps/<app>/serializers/` mirroring the feature split.
- Services: `apps/<app>/services/`.
- Management commands: `apps/<app>/management/commands/`.
- Tests: `tests/playwright/tests/` only for backend automated coverage. Do not add `apps/**/tests/` or other Python/Django test files for backend changes.

## Common Pitfalls

1. Do not skip virtualenv activation before Python and Django commands.
2. Do not import generics from `rest_framework.generics` when a custom generic from `shared.mixins.drf_views` is intended.
3. Do not use `blank=True` on models or serializers.
4. Do not access environment variables through `os.environ` directly.
5. Do not manually force database selection with `.using()` unless there is a rare, explicit routing reason.
6. Do not forget Bruno updates after API contract changes.
7. Do not add backend Python or Django tests under `apps/**/tests`; keep automated backend coverage in `tests/playwright/tests` and update those specs when API behavior changes.
8. Do not create extra summary markdown files such as `CHANGES.md` or `SUMMARY.md` after finishing work.

## Instruction Maintenance Note

When editing AI instructions in this repository:

- keep workflow policy in [AGENTS.md](../AGENTS.md),
- keep repo-specific engineering rules here,
- keep task recipes in [../.agents/skills](../.agents/skills),
- remove dead references instead of adding more cross-linked duplication.
