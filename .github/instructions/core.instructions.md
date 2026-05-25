---
description: "Use when working in the core app: user model, authentication, OTP, invitations, family, close groups, feed, membership, profile, or file uploads."
applyTo: "apps/core/**"
---

# Core App Conventions

## Session Close-Out

After Python code changes, follow the repo-level close-out validation in [AGENTS.md](../../AGENTS.md). Run `source ~/.zshrc && source .venv/bin/activate && ruff check . --output-format concise && ty check` from the repo root, and fix any failures before handoff.

## User Model

The custom user model is `apps.core.models.UserMaster` — never reference Django's default `User`.

- Authentication supports both email and mobile (OTP-based).
- Use `get_user_model()` in code that references the user model indirectly.

## Audit Models

All core models that track ownership use `AuditModel` (from `shared/mixins/base_model.py`).

`AuditModel` sets `created_by` / `updated_by` automatically via the `crum` middleware — it reads the current request user. This **requires** the request context to be active. Batch operations, management commands, and signal handlers that run outside a request must handle `crum` context explicitly or the audit fields will be null.

## OTP Flow

OTP logic lives in `services/otp_service.py` and `shared/helpers/otp.py`. The `OTP` model (in `models/user.py`) tracks purpose, expiry, and verification state.

- Purposes are defined in `shared/enums/base.py` → `OTPPurpose`.
- Do **not** add new OTP purposes without adding them to the enum.

## URL Structure

All URLs are explicitly versioned:

```
v1/auth/*           — login, signup, OTP, password reset, token refresh
v1/membership/*     — membership applications (public-facing)
v1/user/profile/    — profile management
v1/family/*         — family CRUD and member invitations
v1/close-group/*    — close group membership
v1/users/lookup/    — user discovery
v1/feed/*           — family feed, comments, reactions
v1/upload/          — file uploads
```

## Invitation Codes

`InvitationCode` and `SignupSession` track the invite-based onboarding flow. `InvitationCode` is consumed on successful signup — do **not** allow reuse.

## Membership

`MembershipApplication` lives in `apps/core/models/user.py`. The status choices are in `shared/enums/base.py` → `ApplicationStatus`.

## Key Pitfalls

- `AuditModel` saves outside a request context (e.g. management commands) will not set `created_by`/`updated_by` — add explicit `crum` context if user tracking is required.
- Do **not** use `blank=True` on any model field — use `null=True` for optional columns.
- Invitation codes are single-use; do not re-enable without confirming business intent.
- Email delivery requires SMTP settings in `settings/integrations.py` — `.env` values alone are inert. For local dev with Mailpit, leave `EMAIL_HOST_USER`/`EMAIL_HOST_PASSWORD` empty.
