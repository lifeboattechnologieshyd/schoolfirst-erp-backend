---
description: "Use when creating or editing Django models, including migrations, model choices, audit fields, indexing, or database routing."
applyTo: "apps/**/models/**"
---

# Model Conventions

## Session Close-Out

After Python code changes, follow the repo-level close-out validation in [AGENTS.md](../../AGENTS.md). Run `source ~/.zshrc && source .venv/bin/activate && ruff check . --output-format concise && ty check` from the repo root, and fix any failures before handoff.

## Base Classes

| Class | When to Use |
|-------|------------|
| `AuditModel` | Full tracking: `created_at`, `updated_at`, `created_by`, `updated_by` (via `crum`) |
| `TimeAuditModel` | Timestamps only, no user tracking (e.g. assistant Thread/Message) |

Import from `shared.mixins.base_model`. Do not use plain `models.Model` for app entities.

## Field Rules

- **Primary key**: `UUIDField(primary_key=True, default=uuid.uuid4, editable=False)`
- **Optional columns**: `null=True` — never `blank=True` on model fields
- **Enums**: `models.TextChoices` or `models.IntegerChoices` — never raw strings
- **Table names**: `db_table = "snake_case_name"` in `Meta` (always explicit)
- **Indexes**: add `db_index=True` or explicit `indexes = [...]` for fields used in filters/lookups

## Cross-App References

Prefer `UUIDField` over `ForeignKey` when referencing models in another app:

```python
# Good — loose coupling across apps
thread_id = models.UUIDField(db_index=True)

# Avoid — tight coupling with cross-app FK
thread = models.ForeignKey("assistant.Thread", ...)
```

## Migrations

- Run `python manage.py makemigrations` after every model change.
- Run `python manage.py migrate --settings=settings.development` before running Playwright tests.
- Do not manually edit auto-generated migration files unless squashing.
- Multi-database: migrations target the database the app is routed to in `APP_TO_DB_MAPPING` — do not add `--database` flag unless routing is confirmed.

## AuditModel and crum

`AuditModel` reads the current user from the `crum` request context set by middleware. If you save an `AuditModel` instance **outside** a request (management commands, signals, async tasks), the audit fields will be null unless you set the context explicitly.

## Common Pitfalls

- Do **not** use `blank=True` — it is banned on model fields.
- Do **not** add cross-app `ForeignKey` — use `UUIDField` references.
- Do **not** skip `db_table` — always set an explicit table name.
- Do **not** use raw string values for choice fields — use `TextChoices`/`IntegerChoices`.
