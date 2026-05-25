# Docusafe Phase 1 Share Boundary Design

## Goal

Implement Phase 1 of the Docusafe roadmap by splitting temporary sharing into
three explicit seams while preserving the existing API contract:

- owner-managed share lifecycle
- public share access and download verification
- `is_shared` projection and share-file cleanup

This phase migrates current callers directly to the new seams in one slice.
`DocusafeShareLinkService` is removed after migration instead of being kept as a
compatibility facade.

## Scope

In scope:

- create `share_owner_service.py`
- create `share_public_access_service.py`
- create `share_projection_service.py`
- migrate current share callers off `DocusafeShareLinkService`
- remove legacy share service facades if no callers remain
- preserve existing request and response shapes
- include narrow correctness fixes that fall directly out of the seam split

Out of scope:

- API contract changes
- model or migration changes
- broader Docusafe service architecture cleanup outside the share slice

## Current Problem

The current temporary-share flow is only nominally split. `TemporaryShareService`
and `TemporaryShareAccessService` are thin wrappers over one large
`DocusafeShareLinkService`, which currently owns:

- owner lifecycle mutations
- public password verification and access responses
- view logging
- `is_shared` projection updates
- share cleanup after file and folder deletion

That coupling makes share mutations, projection refreshes, and public access
state changes easy to change accidentally together.

## Target Service Boundaries

### `ShareOwnerService`

Owns share lifecycle mutations and owner-visible reads.

Public API:

- `list_shares(user_id)`
- `create_share(...)`
- `update_share(user_id, share_id, **data)`
- `delete_share(user_id, share_id)`
- `process_expired_shares()`

Responsibilities:

- validate owner file selection
- create and update `TemporaryFileShare` and `TemporaryShareFile`
- keep share membership changes explicit
- call `ShareProjectionService` after membership or active-status changes
- preserve current empty-share deletion behavior during owner updates

### `SharePublicAccessService`

Owns public verification, download access, and view logging.

Public API:

- `verify_and_access(...)`
- `verify_and_download(...)`

Responsibilities:

- validate password and share state
- mutate share state when access-time transitions occur
- log successful and failed attempts
- return the same access and download payloads as today
- call `ShareProjectionService` when access-time status transitions affect
  whether a share counts as active

### `ShareProjectionService`

Owns only derived share state and share-file cleanup.

Public API:

- `sync_shared_state(file_ids)`
- `remove_files(file_ids)`

Internal responsibilities:

- recompute `DocusafeFile.is_shared`
- recompute `DocusafeFolder.is_shared`
- remove `TemporaryShareFile` rows for deleted files
- reconcile `file_count`
- delete empty shares after cleanup

This service must remain small and explicit. It should not absorb owner or
public-access policy decisions.

## Migration Plan

1. Add `ShareProjectionService` by extracting the current shared-flag and
   deletion cleanup logic from `DocusafeShareLinkService`.
2. Add `ShareOwnerService` and move owner-side list/create/update/delete/expire
   logic into it.
3. Add `SharePublicAccessService` and move access/download/logging logic into it.
4. Migrate callers directly:
   - `apps/docusafe/views/temporary_share.py`
   - `apps/docusafe/views/file.py`
   - `apps/docusafe/serializers/temporary_share.py`
   - `apps/docusafe/services/file_service.py`
   - `apps/docusafe/services/folder_service.py`
   - `apps/docusafe/management/commands/cleanup_expired_shares.py`
5. Remove `share_link_service.py`, `temporary_share_service.py`, and
   `share_access_service.py` if they are no longer referenced.

## Key Behavior Rule

Projection refreshes must happen in the same transaction scope as the share
status or membership mutation that made them necessary.

This applies to:

- share create and update
- share delete
- file and folder deletion cleanup
- share expiry processing
- access-time transitions such as `ACTIVE -> EXPIRED` and `ACTIVE -> BLOCKED`

## Narrow Correctness Fix Included In Phase 1

When a public access attempt changes a share from `ACTIVE` to `EXPIRED` or
`BLOCKED`, the current code updates the share status but does not refresh the
derived `is_shared` projection for the affected files and folders.

Phase 1 includes fixing that gap by having `SharePublicAccessService` trigger
`ShareProjectionService` whenever an access-time transition causes a share to no
longer count as active.

## Validation Plan

1. Run editor diagnostics on all touched Docusafe service, serializer, view, and
   command files.
2. Run `source .venv/bin/activate && ruff check apps/docusafe/services apps/docusafe/views apps/docusafe/serializers apps/docusafe/management/commands`.
3. Run `source .venv/bin/activate && ruff format ...` only if formatting drift
   is introduced.
4. Run `cd tests/playwright && npx playwright test tests/docusafe/docusafe.spec.ts tests/docusafe/docusafe_access.spec.ts`.
5. Add or update one regression test proving that a file with exactly one active
   temporary share becomes unshared when that share is deactivated by an
   access-time transition.

## Expected Outcome

After Phase 1:

- owner lifecycle, public access, and projection logic are independently
  understandable
- file and folder deletion paths call a projector instead of a broad share
  lifecycle service
- access-time state transitions can no longer leave `is_shared` stale
- future Phase 2 FK work can rely on a clearer projection boundary
