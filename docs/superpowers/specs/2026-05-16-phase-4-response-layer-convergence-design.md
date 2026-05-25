# Phase 4 Response Layer Convergence Design

## Goal

Implement Phase 4 of the roadmap by converging backend response construction on
one canonical path while preserving the current live API responses.

This phase is intentionally behavior-preserving at the contract layer. The
primary outcome is response construction consistency inside the codebase, not a
schema rewrite for clients.

## Scope

In scope:

- treat `build_response(...)` as the only preferred response-construction path
- make `successResponse(...)` and `errorResponse(...)` temporary compatibility
  shims over the canonical path
- migrate the remaining application-level legacy helper callers in:
  - `apps/docusafe/views/temporary_share.py`
  - `apps/docusafe/views/file_access.py`
  - `apps/docusafe/views/file.py`
- preserve current response bodies for touched endpoints, including any legacy
  top-level fields already emitted today
- confirm repo-wide that direct legacy-helper usage in application views is
  shrinking to zero

Out of scope:

- changing endpoint business logic
- changing status codes, permissions, or service behavior
- intentionally normalizing all responses to a new public schema
- removing the legacy helper names entirely in this phase
- broad unrelated view refactors

## Current Inconsistency

The shared response layer currently exposes two patterns in
`shared/mixins/drf_views.py`:

- `build_response(...)` for the standard `{success, message, data, error, meta}`
  shape
- `successResponse(...)` and `errorResponse(...)` for legacy callers

This creates inconsistent call-site style across the backend and even within the
same feature area. For example, some Docusafe views already use
`build_response(...)` for validation errors while still using `successResponse(...)`
for success cases.

The result is a response layer that is already partially converged in practice
but still split in source-level conventions.

## Canonical Response Path

Phase 4 defines `build_response(...)` as the only preferred API for response
construction in application code.

Target end state:

- new and touched application code uses `build_response(...)`
- `successResponse(...)` and `errorResponse(...)` remain only as temporary
  compatibility wrappers
- the shared layer has one canonical construction path even if legacy names
  still exist for a migration window

This keeps the design aligned with existing repository guidance that endpoints
should use `build_response(...)` and the standard response shape.

## Response Contract Preservation

Phase 4 must preserve current live response bodies.

That constraint matters because the legacy helpers currently emit more than the
standard top-level fields. Existing callers may still expose fields such as:

- `errorCode`
- `description`
- `total`

Because the user asked to keep API responses the same, these fields must remain
present on endpoints that already return them today, even after those endpoints
move to the canonical construction path.

Preservation rules:

- keep current success and error payload shape for touched endpoints
- keep current `message` semantics where callers already rely on `description`
- keep current `status` behavior
- do not silently move legacy top-level fields into `meta` in this phase
- do not drop legacy fields unless a later, explicit API contract change is
  approved

## Migration Mechanics

Phase 4 should use a shim-first migration.

### Shared Layer

Update `shared/mixins/drf_views.py` so that `successResponse(...)` and
`errorResponse(...)` translate into `build_response(...)` rather than remaining
parallel construction paths.

This creates one canonical path without forcing all callers to change at once.

### Application Call Sites

Migrate the remaining legacy helper callers to `build_response(...)` in small
batches.

For migrated callers:

- express success and error responses through `build_response(...)`
- pass through any legacy compatibility fields required to preserve the current
  wire contract
- avoid changing serializer, service, or exception behavior unless required for
  response consistency

### Migration Boundary

At the end of this phase:

- application views should no longer call `successResponse(...)` or
  `errorResponse(...)` directly
- the legacy names may still exist in `shared/mixins/drf_views.py` as temporary
  wrappers for compatibility

This is intentionally narrower than full legacy-helper removal.

## Validation Plan

1. Run editor diagnostics on `shared/mixins/drf_views.py` and the touched
  Docusafe views.
2. Run `source .venv/bin/activate && ruff check shared/mixins apps/docusafe/views`.
3. Run targeted Playwright smoke coverage:
  `cd tests/playwright && npx playwright test tests/docusafe/docusafe.spec.ts tests/docusafe/docusafe_access.spec.ts`.
4. Run repo-wide grep to confirm direct application call sites for
   `successResponse(...)` and `errorResponse(...)` have been reduced to zero.

## Break Risks

The primary risk in this phase is not runtime logic; it is accidental response
shape drift.

The most likely regressions are:

- dropping legacy top-level fields on endpoints that currently emit them
- changing `message` or `error` semantics while translating helper calls
- altering status codes while touching response branches
- leaving both response styles as first-class patterns after the phase ends

These risks are controlled by keeping the migration narrow, preserving current
payloads, and validating affected endpoints directly.

## Expected Outcome

After Phase 4:

- backend response construction converges on one preferred path
- touched application views use `build_response(...)`
- legacy helper names remain only as temporary shared-layer shims
- live API responses stay unchanged for affected endpoints
- the codebase becomes easier to reason about because response construction is
  consistent across success and error branches
