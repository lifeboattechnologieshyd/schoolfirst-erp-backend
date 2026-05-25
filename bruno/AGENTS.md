# Bruno API Collection — Agent Guidelines

This file documents the conventions used in this Bruno collection so that agents and developers keep every request consistent.

## Session Close-Out

If the session also changed Python code, follow the repo-level close-out validation in [AGENTS.md](../AGENTS.md). Run `source ~/.zshrc && source .venv/bin/activate && ruff check . --output-format concise && ty check` from the repo root, and fix any failures before handoff.

## Auth Strategy

### How it works

Auth is configured **once at the collection level** in `opencollection.yml`:

```yaml
request:
  auth:
    type: bearer
    token: "{{access_token}}"
```

Every folder and every authenticated request inherits this via `auth: inherit`. No request should ever hardcode a token.

### Rules

| Situation | What to put in the request file |
| --- | --- |
| Authenticated endpoint (the default) | `auth: inherit` in the `http:` block. No top-level `auth:` block. |
| Public endpoint (login, signup, OTP, password reset, public share access) | Omit the `auth:` field entirely. Do NOT write `auth: none`. |
| Folder `folder.yml` | Always include `request: auth: inherit`. |

**Never use `auth: bearer` with an explicit `auth: bearer: token:` block on individual requests.** That pattern duplicates the collection-level token and breaks when the token rotates.

## Folder Structure

Each folder must have a `folder.yml` with at minimum:

```yaml
info:
  name: <Folder Name>
  type: folder
  seq: <number>

request:
  auth: inherit
```

Subfolders follow the same rule (see `Docusafe/Temporary File Sharing/folder.yml`).

## Variables

All variables are set at collection or environment scope. Never hardcode values.

### Two variable scopes and when to use each

| Scope | How to set | How to read | Editable in UI? | Use for |
| --- | --- | --- | --- | --- |
| Collection | `bru.setVar(key, val)` | `bru.getVar(key)` | **No** — shows as "read-only" | `access_token`, `refresh_token` only |
| Environment | `bru.setEnvVar(key, val)` | `bru.getEnvVar(key)` | **Yes** — editable in the Env panel | All resource IDs (`folder_id`, `file_id`, etc.) |

**Rule**: Resource IDs auto-populated by scripts must use `bru.setEnvVar()`, not `bru.setVar()`. This lets the script auto-fill after a create request *and* lets you manually override the value in the Environments panel when you want to target a specific existing resource.

`bru.setVar()` is reserved for `access_token` and `refresh_token` because those are referenced by the collection-level auth block and should rotate automatically without manual interference.

### Variable reference

| Variable | Scope | Source | Description |
| --- | --- | --- | --- |
| `{{base_url}}` | Environment | env file | Base URL with trailing slash, e.g. `http://localhost:8000/` |
| `{{email}}` | Environment | env file | User email for auto-login on token expiry |
| `{{password}}` | Environment | env file | Password for auto-login on token expiry |
| `{{access_token}}` | Collection | Login/signup scripts (`setVar`) | JWT access token — auto-refreshed, no manual edit needed |
| `{{refresh_token}}` | Collection | Login/signup scripts (`setVar`) | JWT refresh token |
| `{{folder_id}}` | Environment | Create Folder script (`setEnvVar`) | UUID of active Docusafe folder — editable |
| `{{file_id}}` | Environment | Upload File scripts (`setEnvVar`) | UUID of active Docusafe file — editable |
| `{{share_id}}` | Environment | Create Temporary Share script (`setEnvVar`) | UUID of active temporary share — editable |
| `{{thread_id}}` | Environment | Create Thread script (`setEnvVar`) | UUID of active assistant thread — editable |
| `{{invite_code}}` | Environment | set manually | Invitation code string — editable |
| `{{member_id}}` | Environment | set manually | UUID of family/close-group member — editable |
| `{{family_id}}` | Environment | set manually | UUID of active family — editable |

To override any environment variable mid-session: open the **Environments** panel (top-right), select the active environment, and edit the value directly. The next request will pick up the new value.

## Token Lifecycle

### After login (`Auth/Email Login.yml`)

The login request has an `after-response` script that saves tokens:

```js
bru.setVar("access_token", response.data.access_token);
bru.setVar("refresh_token", response.data.refresh_token);
```

Run the **Email Login** request first in any manual test session to hydrate the token.

### Auto-refresh on expiry

The collection-level `after-response` script in `opencollection.yml` detects `token_not_valid` in any response and automatically re-logs in using `{{email}}` and `{{password}}` from the active environment, then updates `{{access_token}}`.

### Signup flows

`Invitation Codes/Verify Signup OTP.yml` also saves tokens after successful signup — same pattern as login.

## Public (Unauthenticated) Endpoints

These intentionally have no `auth:` field:

- `Auth/Email Login.yml`
- `Auth/Access Token.yml` (refresh token)
- `Auth/Password Reset - OTP.yml`
- `Auth/Password Reset.yml`
- `Invitation Codes/Validate Invite Code.yml`
- `Invitation Codes/Signup with Invite Code.yml`
- `Invitation Codes/Verify Signup OTP.yml`
- `Docusafe/Temporary File Sharing/Access Temporary Share.yml`
- `Docusafe/Temporary File Sharing/Download Shared File.yml`

## Environments

Environments live in `environments/`. Each environment sets at minimum:

```yaml
variables:
  - name: base_url
    value: <url with trailing slash>
  - name: email
    value: <user email for auto-login>
  - name: password
    value: <password for auto-login>
```

Never commit real production credentials to `environments/Production.yml`. Use placeholders and fill them in locally.

## Request File Checklist (for agents)

When adding or modifying a request file:

1. Set `auth: inherit` in the `http:` block — unless it is a public endpoint.
2. Do not add a top-level `auth:` block.
3. Use `{{base_url}}` for the URL prefix.
4. Use named collection variables (`{{family_id}}` etc.) instead of hardcoded IDs.
5. Add a `description:` under `info:` if the endpoint has non-obvious behavior (constraints, side effects, response shape changes).
6. If a new folder is created, add a `folder.yml` with `request: auth: inherit`.
7. Keep `seq:` values sequential and unique within each folder.

## Request File Checklist (for agents) — After API Contract Changes

When a backend API change affects request payloads, response bodies, status codes, or auth behavior:

1. Update the relevant Bruno request body or docs.
2. Update the `description:` in `info:` if behavior changed.
3. Run the relevant Playwright spec under `tests/playwright/tests/` to confirm the contract.
