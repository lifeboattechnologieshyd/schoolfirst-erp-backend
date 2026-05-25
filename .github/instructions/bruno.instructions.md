---
description: "Use when updating or creating Bruno API request files after backend API changes to request payloads, response shapes, status codes, or auth semantics."
applyTo: "bruno/**"
---

# Bruno API Request Conventions

## Session Close-Out

If the session also changed Python code, follow the repo-level close-out validation in [AGENTS.md](../../AGENTS.md). Run `source ~/.zshrc && source .venv/bin/activate && ruff check . --output-format concise && ty check` from the repo root, and fix any failures before handoff.

## When to Update Bruno Files

Update Bruno requests whenever a backend change affects:
- Request payloads (new/removed/renamed fields)
- Response body structure
- HTTP status codes
- Authentication behavior
- Documented endpoint URLs

**Always update Bruno in the same change that modifies the API** — do not defer it.

## File Format

Each request is a `.yml` file in the module folder. The format follows the Bruno collection schema (`opencollection.yml` at the collection root).

## Organization

Bruno requests mirror the API module structure:

```
bruno/
    Auth/           — login, signup, OTP, token refresh, password reset
    Assistant/      — threads, chat, messages
    Docusafe/       — folders, files, access, shares, search
    Calendar/       — events, tasks, comments
    Family/         — family CRUD and invitations
    Feed/           — feed, comments, reactions
    Profile/        — profile update
    Upload/         — file upload
    Membership/     — membership applications
    Invitation Codes/ — invitation management
    Close Group/    — close group membership
    environments/   — auth tokens, base URLs (per environment)
```

## Environment Variables

Request files reference Bruno environment variables (e.g. `{{baseUrl}}`, `{{accessToken}}`). Keep `environments/` files updated when new auth flows or base URL patterns change.

## Keeping in Sync with Playwright

Bruno (manual/exploratory) and Playwright (automated) test the same endpoints. After updating Bruno, check whether the matching Playwright test in `tests/playwright/tests/` also needs updating.
