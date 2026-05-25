---
name: backend-debugging
description: Debugging loop for backend failures starting from a concrete symptom.
---

# Backend Debugging

## Session Close-Out

After Python code changes, follow the repo-level close-out validation in [AGENTS.md](../../../AGENTS.md). Run `source ~/.zshrc && source .venv/bin/activate && ruff check . --output-format concise && ty check` from the repo root, and fix any failures before handoff.

Use this skill when the task starts from a concrete failure such as:

- a traceback,
- a failing test,
- a broken endpoint,
- an unexpected status code,
- a serializer validation error,
- a log entry or production symptom with a known code path.

## Debugging Loop

1. Capture the exact failing behavior first.
2. Identify one local hypothesis about where the behavior is controlled.
3. Pick the cheapest discriminating check that could falsify that hypothesis.
4. Make the smallest edit or probe that tests it.
5. Rerun the same focused check immediately.

If the result falsifies the hypothesis, step one hop closer to the controlling code. Do not reopen broad repo exploration unless the nearby path is exhausted.

## Good Anchors In This Repo

- Django logs under `logs/`
- the owning DRF view or serializer
- Bruno requests for the endpoint
- Playwright endpoint specs in `tests/playwright/tests`
- model methods and service classes behind the view

## Repo-Specific Failure Traps

- wrong generic import instead of `shared.mixins.drf_views`
- missing `build_response()` shape
- `blank=True` or serializer optionality mistakes
- database routing assumptions that bypass `AppRouter`
- forgotten `settings.development` on local Django commands
- API changes that were not mirrored in Bruno or Playwright
- adding backend Python or Django tests under `apps/**/tests` instead of keeping coverage in `tests/playwright/tests`

## Stop Conditions

Escalate instead of guessing when:

- the same issue survives 3 distinct attempts,
- the root cause is ambiguous between multiple business rules,
- a fix would require destructive schema or data changes.

When the ambiguity is a non-sensitive question the user can answer directly, use VS Code's `vscode_askQuestions` tool to gather that clarification instead of guessing.
