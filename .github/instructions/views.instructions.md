---
description: "Use when creating or editing DRF views, viewsets, URL patterns, permissions, throttling, or API response formatting."
applyTo: "apps/**/views/**"
---

# View And URL Conventions

## Session Close-Out

After Python code changes, follow the repo-level close-out validation in [AGENTS.md](../../AGENTS.md). Run `source ~/.zshrc && source .venv/bin/activate && ruff check . --output-format concise && ty check` from the repo root, and fix any failures before handoff.

## Imports

**Always** import DRF generics from the custom module, not from `rest_framework.generics`:

```python
# Correct
from shared.mixins.drf_views import ListCreateAPIView, RetrieveUpdateDestroyAPIView

# Wrong — do not use
from rest_framework.generics import ListCreateAPIView
```

The custom generics include `build_response()` and enforce the standard response shape.

## Response Shape

All endpoints must use `build_response()` to produce the standard shape `{success, message, data, error, meta}`:

```python
# Success
return self.build_response(
    success=True,
    data=serializer.data,
    status=status.HTTP_200_OK,
)

# Validation error
return self.build_response(
    success=False,
    error={
        "code": GlobalAPIMessageCodes.VALIDATION_ERROR,
        "message": GlobalAPIMessageCodes.VALIDATION_ERROR.label,
        "details": [{"type": "field", "field": "email", "message": "Required"}],
    },
    status=status.HTTP_400_BAD_REQUEST,
)
```

## Permissions

Default permissions come from `settings/auth.py`. Rules:
- **Authenticated endpoints**: no declaration needed (default applies).
- **Public endpoints**: must explicitly declare `permission_classes = [AllowAny]`.
- **Admin endpoints**: must explicitly declare staff or custom permission class.

## Throttling

Set `throttle_scope` on rate-limited endpoints. Defined scopes in `settings/auth.py`:
- `chat_message`, `login`, `invite_validate`, `membership_application`

> OTP send limits (cooldown, hourly cap) are business logic enforced in `OTPService.create()` — do not model them as throttle scopes.

```python
throttle_scope = "chat_message"
```

## ViewSets vs Generic Views

- Use `DefaultRouter` + `ViewSet` for full CRUD APIs.
- Use `ListCreateAPIView`, `RetrieveUpdateDestroyAPIView` etc. for simpler endpoints.
- Keep URL names descriptive for reverse lookups.

## File Organization

Use feature subdirectories when the app already has them:

```
apps/core/views/
    auth/
        login.py
    family/
        family.py
    profile.py
```

## Common Pitfalls

- Do **not** import from `rest_framework.generics` — always use `shared.mixins.drf_views`.
- Do **not** return raw DRF `Response` — use `build_response()`.
- Do **not** forget `permission_classes = [AllowAny]` on public endpoints.
- Do **not** put business logic in views — delegate to services.
