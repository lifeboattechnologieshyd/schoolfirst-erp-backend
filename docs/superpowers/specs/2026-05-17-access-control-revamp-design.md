# Access Control Revamp Design

## Goal

Replace the `access_close_group` boolean field and the associated reverse-lookup
access pattern with an explicit `access_close_group_ids` list field across the
`AccessControlMixin`. Restructure the `CloseGroup` module to mirror the family
API shape and be ready for future multiple-close-group support. Rewrite the
`CalendarAccessPolicy` / `SocialGraphService` access filter to a simple
three-way overlap query. Scope is limited to the calendar module migrations;
other modules (docusafe) inherit the mixin change without their own migrations
until their own revamp phase.

---

## Current Problems

1. `CloseGroup.owner` is a `OneToOneField` — hard-blocks future multiple groups.
2. `access_close_group = BooleanField` requires a painful reverse lookup:
   find owners whose group the viewer belongs to, then match against `creator_id`.
3. `SocialGraphService.get_close_group_owner_ids()` returns creator user IDs, not
   close group IDs — the two concepts are conflated.
4. `CalendarAccessPolicy.build_filter()` constructs a composite `Q` over
   `access_close_group=True, creator_id__in=[...]` which breaks down with multiple
   groups and is hard to extend.
5. Close group member endpoints are not scoped to a group ID in the URL, making
   them incompatible with multi-group support.
6. `AccessType` only has `GROUP` which conflates "share with everyone" and "share
   with a subset."
7. A separate `SPECIFIC` type was unnecessary given that `MIXED` already accepts
   explicit user IDs alongside family and close group selections.

---

## Scope

**In scope:**

- `CloseGroup` model: `OneToOneField` → `ForeignKey`, add `name` field.
- New `GET v1/close-group` list endpoint and `GET v1/close-group/<id>` detail endpoint.
- Restructure close group member URLs to include `<close_group_id>`.
- `AccessControlMixin`: remove `access_close_group`, add `access_close_group_ids`.
- `AccessType` enum: replace `GROUP` with `ALL` and `MIXED`; remove `SPECIFIC`.
- `SocialGraphScope` + `SocialGraphService`: replace `close_group_owner_ids` with
  `close_group_membership_ids`.
- `CalendarAccessPolicy` + `AccessResolver`: full rewrite to use overlap queries.
- Calendar serializer input fields: replace `access_close_group` with
  `access_close_group_ids`.
- Calendar migrations: schema + data.
- Core migration: model change only (no data loss).
- Bruno request files updated to reflect new request/response shapes.

**Out of scope:**

- Docusafe or other app migrations (they inherit the mixin change but do not
  migrate until their own revamp).
- Close group CRUD (no POST/PUT/DELETE on the group resource — read-only).
- Frontend; only backend contract changes are described here.

---

## 1. CloseGroup Model Change

### Model (apps/core/models/close_group.py)

| Field | Before | After |
|---|---|---|
| `owner` | `OneToOneField(UserMaster, related_name="close_group")` | `ForeignKey(UserMaster, related_name="close_groups", on_delete=CASCADE)` |
| `name` | — | `CharField(max_length=100)` ← new |
| `member_count` | — | `PositiveIntegerField(default=0)` ← new, denormalized |
| `is_active` | unchanged | unchanged |

Existing rows receive `name = "Default"` and `member_count = 0` via the migration
defaults. `member_count` should be backfilled by counting JOINED members per group
in the data migration if existing member data exists.

### CloseGroupService changes (apps/core/services/close_group_service.py)

- `get_or_create_group(user)` renamed to `get_or_create_default_group(user)`.
  Creates with `name="Default"` if no group exists for the user.
- `add_member(user, email, close_group_id)` — service fetches the group by ID,
  asserts `group.owner == user`, raises `PermissionDenied` if not. Increments
  `group.member_count` when the member is created with `status=JOINED`. For
  `INVITED` rows, `member_count` is not incremented until invite converts to JOINED.
- `remove_member(user, member_id, close_group_id)` — service fetches group,
  asserts ownership, decrements `group.member_count` only if removed member had
  `status=JOINED`.
- `resolve_pending_invites(email, user)` — unchanged in query logic. Increments
  `member_count` on each group where an INVITED row is converted to JOINED.
- `list_members(user, close_group_id)` — service fetches group, asserts ownership,
  returns member queryset filtered to that group.
- `get_own_close_group_member_user_ids(user)` — updated to use `close_groups`
  (plural) related name to aggregate JOINED members across all owned groups.

**Ownership check pattern:** Service methods receive `user` + `close_group_id`
and perform `CloseGroup.objects.get(id=close_group_id, owner=user)` internally,
raising `PermissionDenied` (403) when the group is not owned by the user. Views
pass `close_group_id` from URL kwargs and `request.user` as-is.

---

## 2. Close Group URL Layout

Mirrors the family API shape. No CRUD on the group resource itself.

```
GET    v1/close-group                                               CloseGroupListView
GET    v1/close-group/<uuid:close_group_id>                        CloseGroupDetailView
GET    v1/close-group/<uuid:close_group_id>/members                CloseGroupMemberListCreateView (list)
POST   v1/close-group/<uuid:close_group_id>/members                CloseGroupMemberListCreateView (add)
DELETE v1/close-group/<uuid:close_group_id>/members/<uuid:member_id>  CloseGroupMemberDeleteView
GET    v1/close-group/added-me                                     CloseGroupAddedMeView
```

`added-me` is a global read (not scoped to a close group). It returns users who
added the requesting user to *their* close group.

URL registration order: `added-me` must be registered before
`<uuid:close_group_id>` in the URLconf. Django's UUID converter means there is no
runtime conflict, but explicit ordering keeps intent clear.

### Response shapes

**GET v1/close-group** — list of owned close groups

```json
{
  "success": true,
  "data": [
    { "id": "<uuid>", "name": "Default", "member_count": 3 }
  ]
}
```

**GET v1/close-group/<id>** — single group detail

```json
{
  "success": true,
  "data": { "id": "<uuid>", "name": "Default", "member_count": 3 }
}
```

Member list, add member, remove member, and added-me shapes are unchanged from
current behaviour. Member list includes INVITED (pending) members so the owner
can see who is yet to join.

**Removed URLs:** The previous flat endpoints (`v1/close-group/members`,
`v1/close-group/members/<id>`) are removed entirely. No backwards-compat aliases.

### New/updated views

| View | Change |
|---|---|
| `CloseGroupListView` | New — `GET v1/close-group`, returns `CloseGroupSerializer` list |
| `CloseGroupDetailView` | New — `GET v1/close-group/<id>`, verifies `owner == request.user` |
| `CloseGroupMemberListCreateView` | Updated — reads `close_group_id` from URL kwargs; calls updated service signatures |
| `CloseGroupMemberDeleteView` | Updated — reads `close_group_id` from URL kwargs |
| `CloseGroupAddedMeView` | Unchanged |

### New/updated serializers

- `CloseGroupSerializer` (new) — `id`, `name`, `member_count` (read directly
  from the denormalized model field, no annotation needed).
- `CloseGroupMemberAddSerializer` — unchanged (`email` field only).
- `CloseGroupMemberSerializer` — unchanged.

---

## 3. AccessControlMixin + AccessType

### AccessType enum (apps/calendar/enums/access.py)

Three values only.

| Value | Meaning | Validation rule |
|---|---|---|
| `only_me` | Private to creator | All three access arrays must be empty |
| `all` | All connections — frontend sends all family IDs and all close group IDs | No array constraints; user with no connections sends empty arrays |
| `mixed` | Any combination — families, close groups, and/or explicit user IDs | At least one entry in any of the three arrays |

`SPECIFIC` is dropped. Any sharing that was previously `SPECIFIC` (explicit user
IDs only) is now expressed as `MIXED` with only `access_user_ids` populated.
`GROUP` is also removed. Existing `GROUP` rows migrate to `MIXED`; existing
`SPECIFIC` rows also migrate to `MIXED` (data migration in the calendar migration).

The frontend is responsible for sending all IDs for `ALL` — backend stores and
validates only; it does not resolve "all" semantically.

### AccessControlMixin (apps/calendar/mixins/access_control.py)

```python
class AccessControlMixin(models.Model):
    access_type            = CharField(choices=AccessType, default=AccessType.ONLY_ME)
    access_family_ids      = JSONField(default=list, null=True)   # unchanged
    access_close_group_ids = JSONField(default=list, null=True)   # replaces access_close_group bool
    access_user_ids        = JSONField(default=list, null=True)   # unchanged

    class Meta:
        abstract = True
```

`access_close_group = BooleanField` is removed. Default changes from `GROUP` to
`ONLY_ME` — new records are private unless the creator explicitly sets a sharing
policy.

---

## 4. SocialGraphService + SocialGraphScope

### SocialGraphScope dataclass (apps/core/services/social_graph_service.py)

```python
@dataclass(frozen=True)
class SocialGraphScope:
    family_ids:                  list[str]
    close_group_membership_ids:  list[str]   # was: close_group_owner_ids
    access_user_id_candidates:   list[str]   # was: specific_access_candidate_user_ids
```

### SocialGraphService method changes

| Old method | New method | Change |
|---|---|---|
| `get_close_group_owner_ids(user)` | `get_close_group_membership_ids(user)` | Returns `CloseGroup` UUIDs (as strings) where `user` is a JOINED `CloseGroupMember`. No longer returns owner user IDs. |
| `get_own_close_group_member_user_ids(user)` | same name | Filter updated to use `close_groups` (plural FK) — aggregates members across all owned groups. |
| `get_specific_access_candidate_user_ids(user)` | `get_access_user_id_candidates(user)` | Renamed to match scope field; logic unchanged — returns JOINED family members + owned close group members. |
| `build_visibility_scope(user)` | same name | Populates `close_group_membership_ids` and `access_user_id_candidates`. |
| — | `get_owned_close_group_ids(user)` | New — returns CloseGroup UUIDs owned by user. Used only in write-path validation (`validate_access_ids_ownership`); not part of `SocialGraphScope`. |

```python
@staticmethod
def get_close_group_membership_ids(user: UserMaster) -> list[str]:
    """CloseGroup IDs where this user is a JOINED member (not owner)."""
    ids = CloseGroupMember.objects.filter(
        user=user,
        status=CloseGroupMember.Status.JOINED,
    ).values_list("close_group_id", flat=True)
    return [str(cg_id) for cg_id in ids]
```

---

## 5. CalendarAccessPolicy + AccessResolver Rewrite

### CalendarAccessScope (apps/calendar/services/access_policy.py)

```python
@dataclass(frozen=True)
class CalendarAccessScope:
    user_id:                     uuid.UUID
    family_ids:                  tuple[str, ...]
    close_group_membership_ids:  tuple[str, ...]   # was: close_group_owner_ids
    access_user_id_candidates:   tuple[str, ...] = ()   # was: specific_access_candidate_user_ids
```

### CalendarAccessPolicy.build_filter()

```python
@staticmethod
def build_filter(scope: CalendarAccessScope) -> Q:
    user_id_str = str(scope.user_id)

    own = Q(creator_id=scope.user_id)

    shared_conditions = Q(access_user_ids__contains=[user_id_str])
    if scope.family_ids:
        shared_conditions |= Q(access_family_ids__overlap=list(scope.family_ids))
    if scope.close_group_membership_ids:
        shared_conditions |= Q(access_close_group_ids__overlap=list(scope.close_group_membership_ids))

    shared = ~Q(access_type=AccessType.ONLY_ME) & shared_conditions

    return own | shared
```

`ONLY_ME`, `ALL`, and `MIXED` collapse into one unified filter. For records where
only `access_user_ids` is populated (formerly `SPECIFIC`), the overlap branches
return no matches and only `access_user_ids__contains` fires. No per-type
branching in the query.

### validate_access_configuration() update

```python
def validate_access_configuration(*, access_type, access_family_ids,
                                   access_close_group_ids, access_user_ids):
    if access_type == AccessType.ONLY_ME:
        if access_family_ids or access_close_group_ids or access_user_ids:
            return error("All access arrays must be empty for only_me.")

    # ALL: no array constraints — a user with no connections sends empty arrays.
    # elif access_type == AccessType.ALL: pass

    elif access_type == AccessType.MIXED:
        if not (access_family_ids or access_close_group_ids or access_user_ids):
            return error("At least one ID required in any access array for mixed access.")

    return None
```

### validate_access_ids_ownership() — new

Applies whenever `access_family_ids` or `access_close_group_ids` is non-empty.
Prevents a creator from naming IDs they do not own.

```python
def validate_access_ids_ownership(*, creator, access_family_ids, access_close_group_ids,
                                   creator_family_ids, creator_close_group_ids):
    if access_family_ids:
        invalid = set(access_family_ids) - set(creator_family_ids)
        if invalid:
            return error(f"Family IDs not in creator's families: {invalid}")
    if access_close_group_ids:
        invalid = set(access_close_group_ids) - set(creator_close_group_ids)
        if invalid:
            return error(f"Close group IDs not owned by creator: {invalid}")
    return None
```

`creator_family_ids` comes from `SocialGraphService.get_user_family_ids(user)`.
`creator_close_group_ids` comes from `SocialGraphService.get_owned_close_group_ids(user)`
(new method, returns UUIDs of groups the creator owns). Both are fetched only on
write paths (create/update), not on reads.

### validate_access_user_ids() — renamed, now applies to MIXED and ALL

Was `validate_specific_access_targets()`. Applies whenever `access_user_ids` is
non-empty, regardless of access type. Allowed pool is
`get_access_user_id_candidates(user)` — JOINED family members + JOINED members of
the creator's owned close groups (aggregated across all groups via the plural FK).
This prevents a creator from granting access to arbitrary strangers.

### AccessResolver changes (apps/calendar/services/access.py)

- `get_close_group_owner_ids()` → `get_close_group_membership_ids()` (delegates
  to `SocialGraphService.get_close_group_membership_ids`).
- `get_specific_access_candidate_user_ids()` → `get_access_user_id_candidates()`.
- `build_access_scope()` populates `close_group_membership_ids` and
  `access_user_id_candidates`.
- `build_access_filter()` — no logic changes; delegates to updated
  `CalendarAccessPolicy.build_filter()`.

---

## 6. Calendar Serializers

### EventWriteSerializer and TaskWriteSerializer

| Field | Before | After |
|---|---|---|
| `access_close_group` | `BooleanField(required=False)` | removed |
| `access_close_group_ids` | — | `ListField(child=UUIDField(), required=False, default=list)` |
| `access_type` choices | `ONLY_ME \| GROUP \| SPECIFIC` | `ONLY_ME \| ALL \| MIXED` |
| `access_type` default | `GROUP` | `ONLY_ME` |

`validate_access_configuration()`, `validate_access_ids_ownership()`, and
`validate_access_user_ids()` (renamed from `validate_specific_access_targets`)
called in `validate()` in this order. `validate_access_ids_ownership()` fires
whenever either family or close group IDs are non-empty. `validate_access_user_ids()`
fires whenever `access_user_ids` is non-empty.

---

## 7. Migration Plan

Four steps executed in order. Steps 2 and 3 may be combined into a single
migration file.

### Step 1 — apps/core

```
AlterField: CloseGroup.owner OneToOneField → ForeignKey
AddField:   CloseGroup.name         CharField(max_length=100, default="Default")
AddField:   CloseGroup.member_count PositiveIntegerField(default=0)
```

Existing rows get `name = "Default"` and `member_count = 0` from migration
defaults. Backfill `member_count` with a `RunPython` step:

```python
def backfill_member_count(apps, schema_editor):
    CloseGroup = apps.get_model("core", "CloseGroup")
    CloseGroupMember = apps.get_model("core", "CloseGroupMember")
    for group in CloseGroup.objects.all():
        group.member_count = CloseGroupMember.objects.filter(
            close_group=group, status="joined"
        ).count()
        group.save(update_fields=["member_count"])
```

No data loss. Run order: core migration first, then calendar (by convention; no
hard cross-DB dependency).

### Step 2 — apps/calendar (schema)

```
AddField: Event.access_close_group_ids JSONField(default=list, null=True)
AddField: Task.access_close_group_ids JSONField(default=list, null=True)
RemoveField: Event.access_close_group
RemoveField: Task.access_close_group
```

Existing `access_close_group=True` records: `access_close_group_ids` will be
`[]`. Access is effectively removed for those records (accepted trade-off).

### Step 3 — apps/calendar (data)

```python
def migrate_access_type(apps, schema_editor):
    Event = apps.get_model("calendar", "Event")
    Task  = apps.get_model("calendar", "Task")
    for Model in (Event, Task):
        Model.objects.filter(access_type__in=["group", "specific"]).update(access_type="mixed")
```

Both `group` and `specific` collapse to `mixed`. For former `specific` rows,
`access_family_ids` and `access_close_group_ids` are already empty — they remain
valid `MIXED` records whose only populated array is `access_user_ids`.

### Step 4 — apps/calendar (enum cleanup)

`AlterField` on `Event.access_type` and `Task.access_type` to remove `group` and
`specific` from the choices list after the data migration confirms no stale rows
remain.

---

## 8. Bruno Updates

Files to update after implementation:

- `bruno/Calendar/Events/Create Event.bru` — replace `access_close_group` field
  with `access_close_group_ids` array; add `ALL` and `MIXED` access type examples.
- `bruno/Calendar/Events/Update Event.bru` — same.
- `bruno/Calendar/Tasks/Create Task.bru` — same.
- `bruno/Calendar/Tasks/Update Task.bru` — same.
- New file: `bruno/Close Group/List Close Groups.bru` — `GET v1/close-group`.
- New file: `bruno/Close Group/Close Group Detail.bru` — `GET v1/close-group/<id>`.
- Existing member request files under `bruno/Close Group/` — update URLs to
  include `<close_group_id>`.

---

## 9. Future Multi-Group Path

The backend will be ready for multiple close groups when this design is
implemented:

- `CloseGroup` is now a `ForeignKey` — creating a second group for a user is a
  plain `CloseGroup.objects.create(owner=user, name=name)`.
- `get_close_group_membership_ids()` already returns a list — additional
  memberships are included automatically.
- `access_close_group_ids` is already a list — multiple group IDs can be sent.
- Frontend remains unaware: it calls `GET v1/close-group`, gets back one (or
  later many) groups, and passes the ID(s) in `access_close_group_ids`.
- No backend contract changes are needed when multi-group creation is enabled.
  Only a `POST v1/close-group` endpoint and a name input in the service need to
  be added.
