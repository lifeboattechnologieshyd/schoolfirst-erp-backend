# Docusafe Phase 2 Local Referential Integrity Design

## Goal

Implement Phase 2 of the Docusafe roadmap by replacing UUID-only local
relationships with database-enforced foreign keys where records share lifecycle,
while preserving UUID references to Core-owned records.

This phase is intentionally behavior-preserving at the API layer. The primary
outcome is stronger local integrity inside Docusafe, not endpoint changes.

## Scope

In scope:

- convert `DocusafeFile.folder_id` to a foreign key to `DocusafeFolder`
- convert `TemporaryShareFile.share_id` to a foreign key to `TemporaryFileShare`
- convert `TemporaryShareFile.file_id` to a foreign key to `DocusafeFile`
- convert `ShareViewLog.share_id` to a foreign key to `TemporaryFileShare`
- convert `DocusafeFileAccess.file_id` to a foreign key to `DocusafeFile`
- clean orphaned local Docusafe rows in migration before enforcing constraints
- keep service changes narrow and compatibility-oriented

Out of scope:

- changing `owner_id`, `family_id`, or `user_id` to foreign keys
- API contract changes
- unrelated Docusafe refactors

## Local Vs Cross-App Boundaries

These references remain UUIDs because they cross app or ownership boundaries:

- `DocusafeFolder.owner_id`
- `DocusafeFile.owner_id`
- `TemporaryFileShare.owner_id`
- `DocusafeFileAccess.family_id`
- `DocusafeFileAccess.user_id`
- `DocusafeFileAccess.owner_id`

These references become foreign keys because they are local Docusafe
relationships with shared lifecycle:

- file -> folder
- share membership -> share
- share membership -> file
- share view log -> share
- file access grant -> file

## Target Model Changes

### `DocusafeFile`

- replace UUID-only `folder_id` with `folder = models.ForeignKey(...)`
- keep the database column name as `folder_id` using `db_column="folder_id"`
- preserve stable service code by continuing to allow `folder_id` access where
  helpful

### `TemporaryShareFile`

- replace `share_id` with a foreign key to `TemporaryFileShare`
- replace `file_id` with a foreign key to `DocusafeFile`
- keep the current database column names with `db_column`

### `ShareViewLog`

- replace `share_id` with a foreign key to `TemporaryFileShare`
- keep the database column name as `share_id`

### `DocusafeFileAccess`

- replace `file_id` with a foreign key to `DocusafeFile`
- keep the database column name as `file_id`

## Delete Semantics

This phase distinguishes between database-owned local dependents and
application-owned soft-delete flows.

Use database-owned lifecycle for purely dependent local records:

- `TemporaryShareFile`
- `ShareViewLog`
- `DocusafeFileAccess`

Those rows should cascade from their local parent records.

Keep service-layer orchestration as the real lifecycle path for folders and
files because soft delete, storage behavior, and projection updates remain
application concerns.

## Migration Strategy

Use a direct migration on the existing columns rather than a temporary-field
backfill strategy.

Migration sequence:

1. Run a cleanup data migration to remove orphaned local Docusafe rows.
2. Alter the existing UUID columns into foreign keys on the same columns.
3. Update model metadata and the touched services to rely on the FK-backed
   integrity.

## Orphan Cleanup Policy

Phase 2 cleans orphaned local rows in migration rather than failing and asking
for manual cleanup.

Cleanup targets:

- files pointing at missing folders
- temporary-share membership rows pointing at missing shares or files
- share view logs pointing at missing shares
- file-access rows pointing at missing files

This is intentionally limited to local Docusafe integrity. Cross-app UUIDs are
not part of the cleanup scope.

## Service Impact

Phase 2 should not become a broad rewrite from raw ID filters to object-level
navigation.

Preferred service posture:

- keep existing service APIs stable
- keep current `*_id` usage where that minimizes churn
- remove only the manual assumptions that were compensating for missing DB
  constraints
- rely on the database to guarantee local parent-child existence

## Validation Plan

1. Run editor diagnostics on touched models, services, and migration files.
2. Run `source .venv/bin/activate && ruff check apps/docusafe/models apps/docusafe/services`.
3. Run `source .venv/bin/activate && python manage.py makemigrations`.
4. Run `source .venv/bin/activate && python manage.py migrate --settings=settings.development`.
5. Run `cd tests/playwright && npx playwright test tests/docusafe/docusafe.spec.ts tests/docusafe/docusafe_access.spec.ts tests/docusafe/search.spec.ts`.

## Expected Outcome

After Phase 2:

- local Docusafe parent-child integrity is enforced by the database
- local orphaned rows are removed during migration instead of surviving as raw
  UUID drift
- service code no longer has to compensate for missing local DB constraints
- cross-app boundaries remain loose where they should remain loose
