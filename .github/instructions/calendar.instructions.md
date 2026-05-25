---
description: "Use when working in the calendar app: events, tasks, comments, recurring events with RRULE, or the unified calendar view."
applyTo: "apps/calendar/**"
---

# Calendar App Conventions

## Session Close-Out

After Python code changes, follow the repo-level close-out validation in [AGENTS.md](../../AGENTS.md). Run `source ~/.zshrc && source .venv/bin/activate && ruff check . --output-format concise && ty check` from the repo root, and fix any failures before handoff.

## URL Structure

```
v1/calendar/                          # unified view: events + tasks by date range
v1/calendar/events/                   # event list/create
v1/calendar/events/{id}/              # event detail/update/delete
v1/calendar/events/{id}/comments/     # nested event comments (list/create)
v1/calendar/tasks/                    # task list/create
v1/calendar/tasks/{id}/               # task detail/update/delete
v1/calendar/tasks/{id}/comments/      # nested task comments (list/create)
v1/calendar/comments/{id}/            # comment delete only (top-level endpoint)
```

Comments are **created** via the nested parent endpoint but **deleted** via the top-level `/comments/{id}/` endpoint. Do not add delete to the nested endpoint.

## Unified Calendar View

`UnifiedCalendarView` returns both events and tasks for a given date range in a single response. When adding new calendar item types, update this view and its underlying `calendar.py` service.

## Recurring Events (RRULE)

Recurring events are stored as RRULE strings on the `Event` model. The `rrule.py` serializer handles serialization/deserialization and the `services/rrule.py` service handles recurrence expansion (generating event instances from the rule).

- Do **not** store individual recurrence instances as separate DB rows — expand them at query time.
- When modifying a recurring event, confirm with the user whether the edit applies to one occurrence or all.

## Models

| Model | Key Fields |
|-------|-----------|
| `Event` | date/time, recurrence (RRULE string), owner, attendee metadata |
| `Task` | due date, priority, status choices, owner |
| `Comment` | generic — attaches to both events and tasks via `content_type`/`object_id` or direct FK |

All models use `AuditModel` — audit fields require request context (same as core app pattern).

## Enums

Priority, status choices, and repeat types use `models.TextChoices` / `models.IntegerChoices`. Add new choices to the enum class, not as raw strings in the model field.

## Key Pitfalls

- The unified calendar view must stay consistent — adding a new item type requires updating the unified query in `services/calendar.py`.
- RRULE expansion should happen in the service layer, not in serializers or views.
- Comment deletion must go through `CommentDestroyView` at the top-level URL — do not duplicate delete logic in nested comment endpoints.
