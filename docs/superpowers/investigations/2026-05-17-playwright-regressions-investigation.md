# 2026-05-17 Playwright Regressions Investigation

## Scope

- User-requested repo-wide close-out validation after Ruff and `ty` cleanup.
- Investigated full Playwright failures after static validation was already green.

## Verified Root Causes

- Feed API failures came from `apps/core/services/feed_service.py` filtering family membership with the wrong literal (`"JOINED"`) instead of `FamilyMember.Status.JOINED` (`"joined"`).
- Docusafe temporary-share failures came from `apps/docusafe/services/share_projection_service.py` comparing string `file_ids` against UUID values from `TemporaryShareFile`, which immediately cleared `is_shared` back to `False`.
- Calendar date-window failures were amplified by stale data because `tests/playwright/tests/calendar/calendar.spec.ts` cleanup built malformed detail URLs like `/api/v1/calendar/events<uuid>` and `/api/v1/calendar/tasks<uuid>` instead of including the slash.

## Fixes Applied

- Replaced feed membership status literals with `FamilyMember.Status.JOINED` in all task/feed membership checks.
- Normalized `file_ids` to strings inside Docusafe share projection before shared/unshared set comparisons.
- Fixed the calendar Playwright cleanup helper to delete `/events/{id}` and `/tasks/{id}` correctly.

## Validation

- Focused Playwright reruns passed for:
  - `tests/feed/feed.spec.ts`
  - `tests/docusafe/docusafe.spec.ts`
  - `tests/assistant/docusafe_chat.spec.ts`
  - `tests/calendar/calendar.spec.ts`
- Repo close-out checks passed:
  - `ruff check . --output-format concise`
  - `ty check`
- Full Playwright suite passed:
  - `220 passed`
