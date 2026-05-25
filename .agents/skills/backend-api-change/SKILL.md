---
name: backend-api-change
description: Checklist for adding or changing API-facing backend behavior in SamsR.
---

# Backend API Change

## Session Close-Out

After Python code changes, follow the repo-level close-out validation in [AGENTS.md](../../../AGENTS.md). Run `source ~/.zshrc && source .venv/bin/activate && ruff check . --output-format concise && ty check` from the repo root, and fix any failures before handoff.

Use this skill when a task changes any of the following:

- views or viewsets,
- serializers,
- URL routing,
- request payloads,
- response bodies,
- auth or permission behavior,
- API-facing model fields.

## Start From The Owning Surface

Anchor on the code that actually controls the contract.

- If you start from a URL, step to the owning view.
- If you start from a view, read the serializer and any nearby service it delegates to.
- If you start from a failing test, keep that test as the primary validation target.

Read the nearest Bruno request and relevant Playwright spec before editing if the endpoint already exists.

If a contract detail or business rule is ambiguous and the user can clarify it safely, use VS Code's `vscode_askQuestions` tool instead of guessing.

## Required Repo Rules

- Use generics from `shared.mixins.drf_views`.
- Preserve the standard custom response shape.
- Never add `blank=True` to models or serializers.
- Let `AppRouter` manage database routing.
- Use `get_from_env()` for new environment-backed settings.
- Keep backend automated coverage in `tests/playwright/tests` only. Do not add Django or other Python test files under `apps/**/tests`.

## Execution Checklist

1. Update the owning view, serializer, service, or model.
2. If models changed, create the correct migration work.
3. If the request or response contract changed, update Bruno under `bruno/`.
4. If the request or response contract changed, update the matching Playwright coverage under `tests/playwright/tests`.
5. Run the narrowest validation that exercises the changed contract.

## Validation Order

1. Existing failing test, endpoint call, or reproduction command.
2. Relevant Playwright endpoint spec for the touched contract, adding coverage there when it does not exist yet.
3. `ruff check` on the touched slice or a narrow project lint pass.
4. `makemigrations` and `migrate --settings=settings.development` when models changed.

## Done Criteria

The task is not done until all three of these are true:

1. Code matches the intended API behavior.
2. Bruno reflects the current contract.
3. Relevant Playwright coverage reflects the current contract.

After a significant backend API change, ask the user whether to run the Playwright API tests now.
