---
description: "Use when creating or editing DRF serializers, including nested serializers, field validation, choice fields, or input parsing."
applyTo: "apps/**/serializers/**"
---

# Serializer Conventions

## Session Close-Out

After Python code changes, follow the repo-level close-out validation in [AGENTS.md](../../AGENTS.md). Run `source ~/.zshrc && source .venv/bin/activate && ruff check . --output-format concise && ty check` from the repo root, and fix any failures before handoff.

## Field Rules

| Scenario | Correct Approach |
|----------|-----------------|
| Optional field | `required=False` |
| Nullable input | `allow_null=True` |
| Optional string input | `allow_blank=True` |
| Choice field | `ChoiceField(choices=MyChoices.choices)` |
| **Never** | `blank=True` on any serializer field |

## Nested Serializers

Use nested serializers for structured sub-objects instead of flat dicts or `JSONField`:

```python
class ThreadSettingsSerializer(serializers.Serializer):
    enabled_web_search = serializers.BooleanField(required=False)

class ThreadSerializer(serializers.ModelSerializer):
    settings = ThreadSettingsSerializer(required=False)
```

## Shared Enums

Use `ChoiceField` backed by enums from `shared/enums/`:

```python
from shared.enums.base import ApplicationStatus

status = serializers.ChoiceField(choices=ApplicationStatus.choices)
```

## File Organization

Keep serializers in `apps/<app>/serializers/`. When an app has many features, split by feature:

```
apps/assistant/serializers/
    thread.py
    message.py
    content_block.py
    attachment.py
    thread_settings.py
```

## Validation Errors

Use the standard error shape in `raise serializers.ValidationError(...)` or return via `build_response`:

```python
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

## Common Pitfalls

- Do **not** use `blank=True` — it is banned on serializer fields.
- Do **not** use loose `dict` or `JSONField` for structured inputs — use nested serializers.
- Do **not** put business logic in serializers — keep it in services.
