# Access Control Revamp — Implementation Plan

Spec: [docs/superpowers/specs/2026-05-17-access-control-revamp-design.md](../specs/2026-05-17-access-control-revamp-design.md)

Execute phases in order. Each phase is independently validatable. Do not skip ahead.

---

## Phase 1 — Core: CloseGroup Model + Migration

### 1.1 Update `apps/core/models/close_group.py`

- Change `owner` from `OneToOneField` to `ForeignKey(UserMaster, related_name="close_groups", on_delete=models.CASCADE)`.
- Add `name = models.CharField(max_length=100)` (no blank, no null — required field).
- Add `member_count = models.PositiveIntegerField(default=0)`.
- Add `name` to the `Meta.indexes` list alongside `owner`.
- Remove `unique_together` or `unique` constraint that enforced one-per-user if any exists on `owner`.

### 1.2 Create core migration

Run `python manage.py makemigrations core --settings=settings.development`.

The generated migration must include:
- `AlterField` for `owner` (OneToOne → FK).
- `AddField` for `name` with `default="Default"`.
- `AddField` for `member_count` with `default=0`.
- A `RunPython` forward step to backfill `member_count`:

```python
def backfill_member_count(apps, schema_editor):
    CloseGroup = apps.get_model("core", "CloseGroup")
    CloseGroupMember = apps.get_model("core", "CloseGroupMember")
    for group in CloseGroup.objects.all():
        group.member_count = CloseGroupMember.objects.filter(
            close_group=group, status="joined"
        ).count()
        group.save(update_fields=["member_count"])

def noop(apps, schema_editor):
    pass
```

### 1.3 Update `apps/core/services/close_group_service.py`

- Rename `get_or_create_group(user)` → `get_or_create_default_group(user)`.
  Pass `defaults={"name": "Default"}` in `get_or_create`. Update all internal callers in the same file.

- Update `add_member(user, email)` signature to `add_member(user, email, close_group_id)`:
  - Fetch group: `group = get_object_or_404(CloseGroup, id=close_group_id, owner=user)`.
  - Existing duplicate/self-add checks unchanged.
  - After `CloseGroupMember.objects.create(...)` with `status=JOINED`: `CloseGroup.objects.filter(id=group.id).update(member_count=F("member_count") + 1)`.
  - `INVITED` rows do NOT increment `member_count`.

- Update `remove_member(user, member_id)` signature to `remove_member(user, member_id, close_group_id)`:
  - Fetch group: `group = get_object_or_404(CloseGroup, id=close_group_id, owner=user)`.
  - After hard-delete: if deleted member had `status=JOINED`, do `CloseGroup.objects.filter(id=group.id).update(member_count=F("member_count") - 1)`.

- Update `list_members(user)` signature to `list_members(user, close_group_id)`:
  - Fetch group with ownership check, return `CloseGroupMember.objects.filter(close_group=group)` (includes INVITED).

- Update `resolve_pending_invites(email, user)`:
  - After bulk-updating INVITED → JOINED rows, increment `member_count` for each group touched:
    ```python
    CloseGroup.objects.filter(
        members__user=user, members__status=CloseGroupMember.Status.JOINED
    ).update(member_count=F("member_count") + 1)
    ```
  - Alternatively use `F()` expressions per-group if the existing loop structure allows.

### 1.4 Update `apps/core/services/social_graph_service.py`

- Rename `get_close_group_owner_ids(user)` → `get_close_group_membership_ids(user)`.
  New implementation:
  ```python
  ids = CloseGroupMember.objects.filter(
      user=user, status=CloseGroupMember.Status.JOINED
  ).values_list("close_group_id", flat=True)
  return [str(cg_id) for cg_id in ids]
  ```

- Update `get_own_close_group_member_user_ids(user)`:
  Change `close_group__owner=user` to `close_group__in=CloseGroup.objects.filter(owner=user)`.

- Rename `get_specific_access_candidate_user_ids(user)` → `get_access_user_id_candidates(user)`.
  Logic unchanged.

- Add `get_owned_close_group_ids(user)`:
  ```python
  @staticmethod
  def get_owned_close_group_ids(user: UserMaster) -> list[str]:
      """Return UUIDs of CloseGroups owned by this user."""
      ids = CloseGroup.objects.filter(owner=user).values_list("id", flat=True)
      return [str(cg_id) for cg_id in ids]
  ```

- Update `SocialGraphScope` dataclass:
  - Rename field `close_group_owner_ids` → `close_group_membership_ids`.
  - Rename field `specific_access_candidate_user_ids` → `access_user_id_candidates`.

- Update `build_visibility_scope(user)` to populate the renamed fields.

---

## Phase 2 — Core: Close Group Serializers + Views + URLs

### 2.1 Update `apps/core/serializers/close_group.py`

Add `CloseGroupSerializer`:
```python
class CloseGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = CloseGroup
        fields = ["id", "name", "member_count"]
```

Existing serializers (`CloseGroupMemberAddSerializer`, `CloseGroupMemberSerializer`,
`CloseGroupAddedMeSerializer`) are unchanged.

### 2.2 Update `apps/core/views/close_group/members.py`

- `CloseGroupMemberListCreateView`:
  - Add `close_group_id = self.kwargs["close_group_id"]` extraction.
  - `get_queryset`: call `CloseGroupService.list_members(user=self.request.user, close_group_id=close_group_id)`.
  - `create`: pass `close_group_id` to `CloseGroupService.add_member(user, email, close_group_id)`.

- `CloseGroupMemberDeleteView`:
  - Add `close_group_id = self.kwargs["close_group_id"]` extraction.
  - `perform_destroy`: call `CloseGroupService.remove_member(user=self.request.user, member_id=instance.id, close_group_id=close_group_id)`.
  - Update `get_queryset` to scope by `close_group_id`.

- `CloseGroupAddedMeView`: unchanged.

### 2.3 Create `apps/core/views/close_group/groups.py`

New file with two view classes:

```python
class CloseGroupListView(CustomListAPIView):
    """GET v1/close-group — list all close groups owned by the requesting user."""
    permission_classes = [IsAuthenticated]
    serializer_class = CloseGroupSerializer

    def get_queryset(self):
        return CloseGroup.objects.filter(owner=self.request.user, is_active=True)

    def list(self, request, *args, **kwargs):
        # auto-creates default group if user has none
        CloseGroupService.get_or_create_default_group(request.user)
        return super().list(request, *args, **kwargs)


class CloseGroupDetailView(CustomRetrieveUpdateDestroyAPIView):
    """GET v1/close-group/<close_group_id> — single group detail (owner only)."""
    permission_classes = [IsAuthenticated]
    serializer_class = CloseGroupSerializer
    lookup_url_kwarg = "close_group_id"

    def get_queryset(self):
        return CloseGroup.objects.filter(owner=self.request.user, is_active=True)

    def get(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return self.build_response(success=True, data=serializer.data, status=status.HTTP_200_OK)

    # Block PUT/PATCH/DELETE — not supported
    http_method_names = ["get", "head", "options"]
```

### 2.4 Update `apps/core/views/close_group/__init__.py`

Export `CloseGroupListView` and `CloseGroupDetailView`.

### 2.5 Update `apps/core/urls.py`

Replace the three existing flat close group paths with the new nested layout:

```python
# Remove:
path("v1/close-group/members", ...)
path("v1/close-group/added-me", ...)
path("v1/close-group/members/<uuid:member_id>", ...)

# Add:
path("v1/close-group", CloseGroupListView.as_view(), name="close-group-list"),
path("v1/close-group/added-me", CloseGroupAddedMeView.as_view(), name="close-group-added-me"),
path("v1/close-group/<uuid:close_group_id>", CloseGroupDetailView.as_view(), name="close-group-detail"),
path("v1/close-group/<uuid:close_group_id>/members", CloseGroupMemberListCreateView.as_view(), name="close-group-member-list-create"),
path("v1/close-group/<uuid:close_group_id>/members/<uuid:member_id>", CloseGroupMemberDeleteView.as_view(), name="close-group-member-delete"),
```

`added-me` must be registered before `<uuid:close_group_id>` (already handled by ordering above).

---

## Phase 3 — Calendar: Enum + Mixin + Migration

### 3.1 Update `apps/calendar/enums/access.py`

Replace the `AccessType` enum:
```python
class AccessType(models.TextChoices):
    ONLY_ME = "only_me", "Only Me"
    ALL     = "all",     "All"
    MIXED   = "mixed",   "Mixed"
```

Remove `GROUP = "group"` and `SPECIFIC = "specific"`.

### 3.2 Update `apps/calendar/mixins/access_control.py`

```python
class AccessControlMixin(models.Model):
    access_type            = models.CharField(
        max_length=20, choices=AccessType.choices, default=AccessType.ONLY_ME
    )
    access_family_ids      = models.JSONField(default=list, null=True)
    access_close_group_ids = models.JSONField(default=list, null=True)   # new
    access_user_ids        = models.JSONField(default=list, null=True)

    class Meta:
        abstract = True
```

Remove the `access_close_group = BooleanField` line.

### 3.3 Create calendar migration

Run `python manage.py makemigrations calendar --settings=settings.development`.

The generated migration must include for both `Event` and `Task`:
- `AddField` for `access_close_group_ids` (JSONField, default=list, null=True).
- `RemoveField` for `access_close_group`.
- `AlterField` for `access_type` (updated choices, default changes to `only_me`).
- A `RunPython` data migration step:

```python
def migrate_access_types(apps, schema_editor):
    Event = apps.get_model("calendar", "Event")
    Task  = apps.get_model("calendar", "Task")
    for Model in (Event, Task):
        Model.objects.filter(access_type__in=["group", "specific"]).update(access_type="mixed")

def reverse_migrate_access_types(apps, schema_editor):
    Event = apps.get_model("calendar", "Event")
    Task  = apps.get_model("calendar", "Task")
    for Model in (Event, Task):
        Model.objects.filter(access_type="mixed").update(access_type="group")
```

Place `RunPython(migrate_access_types, reverse_migrate_access_types)` AFTER the
`AddField` and `RemoveField` operations but BEFORE the `AlterField` that removes
`group` and `specific` from choices.

---

## Phase 4 — Calendar: Access Layer Rewrite

### 4.1 Rewrite `apps/calendar/services/access_policy.py`

Replace entire file contents:

**`CalendarAccessScope` dataclass** — rename fields:
```python
@dataclass(frozen=True)
class CalendarAccessScope:
    user_id:                    uuid.UUID
    family_ids:                 tuple[str, ...]
    close_group_membership_ids: tuple[str, ...]
    access_user_id_candidates:  tuple[str, ...] = ()
```

**`validate_access_configuration()`** — new signature and logic:
```python
def validate_access_configuration(
    *, access_type, access_family_ids, access_close_group_ids, access_user_ids
):
    if access_type == AccessType.ONLY_ME:
        if access_family_ids or access_close_group_ids or access_user_ids:
            return {"access_type": "All access arrays must be empty for only_me."}
    elif access_type == AccessType.MIXED:
        if not (access_family_ids or access_close_group_ids or access_user_ids):
            return {"access_type": "At least one ID is required for mixed access."}
    # ALL: no array constraints
    return None
```

**`validate_access_ids_ownership()`** — new function:
```python
def validate_access_ids_ownership(
    *, access_family_ids, access_close_group_ids,
    creator_family_ids, creator_close_group_ids
):
    if access_family_ids:
        invalid = sorted(set(str(i) for i in access_family_ids) - set(creator_family_ids))
        if invalid:
            return {"access_family_ids": f"Not in creator's families: {invalid}"}
    if access_close_group_ids:
        invalid = sorted(set(str(i) for i in access_close_group_ids) - set(creator_close_group_ids))
        if invalid:
            return {"access_close_group_ids": f"Not owned by creator: {invalid}"}
    return None
```

**`validate_access_user_ids()`** — renamed from `validate_specific_access_targets`:
```python
def validate_access_user_ids(*, access_user_ids, allowed_user_ids):
    if not access_user_ids:
        return None
    invalid = sorted({str(uid) for uid in access_user_ids} - set(allowed_user_ids))
    if invalid:
        return {"access_user_ids": f"Users not reachable by creator: {invalid}"}
    return None
```

**`CalendarAccessPolicy.build_filter()`** — new implementation:
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

### 4.2 Update `apps/calendar/services/access.py`

- Rename `get_close_group_owner_ids()` → `get_close_group_membership_ids()`.
  Delegates to `SocialGraphService.get_close_group_membership_ids`.
- Rename `get_specific_access_candidate_user_ids()` → `get_access_user_id_candidates()`.
- Update `build_access_scope()` to use renamed fields:
  ```python
  return CalendarAccessScope(
      user_id=self.user.id,
      family_ids=tuple(self.get_user_family_ids()),
      close_group_membership_ids=tuple(self.get_close_group_membership_ids()),
      access_user_id_candidates=tuple(self.get_access_user_id_candidates()),
  )
  ```
- `build_access_filter()` — no change needed (delegates to updated policy).

---

## Phase 5 — Calendar: Serializers

### 5.1 Update `apps/calendar/serializers/event.py`

In `EventWriteSerializer`:
- Remove `access_close_group = serializers.BooleanField(required=False)`.
- Add `access_close_group_ids = serializers.ListField(child=serializers.UUIDField(), required=False, default=list)`.
- Update `access_type` field choices to reflect the new `AccessType` enum (will auto-update if using `ChoiceField` with the enum).
- In `validate()`:
  1. Call `validate_access_configuration(access_type=..., access_family_ids=..., access_close_group_ids=..., access_user_ids=...)`.
  2. If `access_family_ids` or `access_close_group_ids` are non-empty, fetch `creator_family_ids = SocialGraphService.get_user_family_ids(user)` and `creator_close_group_ids = SocialGraphService.get_owned_close_group_ids(user)`. Call `validate_access_ids_ownership(...)`.
  3. If `access_user_ids` is non-empty, fetch `allowed = SocialGraphService.get_access_user_id_candidates(user)`. Call `validate_access_user_ids(...)`.
  4. On any validation failure, raise `ValidationError` with the returned error dict.

### 5.2 Update `apps/calendar/serializers/task.py`

Apply the same changes as 5.1 to `TaskWriteSerializer`.

### 5.3 Remove stale references

Search for and remove all references to:
- `access_close_group` (field name) in serializers, views, and read serializers.
- `validate_specific_access_targets` function name.
- `CalendarAccessScope.close_group_owner_ids` usage.
- `CalendarAccessScope.specific_access_candidate_user_ids` usage.
- `AccessType.GROUP` and `AccessType.SPECIFIC` references.

---

## Phase 6 — Bruno Request Updates

### 6.1 Update calendar event/task requests

In each of the following files, replace `access_close_group: true/false` body field
with `access_close_group_ids: []` and update `access_type` examples to use
`only_me`, `all`, or `mixed`:

- `bruno/Calendar/Create Event.yml`
- `bruno/Calendar/Update Event.yml`
- `bruno/Calendar/Create Task.yml`
- `bruno/Calendar/Update Task.yml`

### 6.2 Update close group request files

- `bruno/Close Group/List Close Group Members.yml` — update URL to include `{{closeGroupId}}`.
- `bruno/Close Group/Add Close Group Member.yml` — update URL to include `{{closeGroupId}}`.
- `bruno/Close Group/Remove Close Group Member.yml` — update URL to include `{{closeGroupId}}`.
- `bruno/Close Group/folder.yml` — no change needed.

### 6.3 Add new close group request files

- `bruno/Close Group/List Close Groups.yml` — `GET {{baseUrl}}/v1/close-group`.
- `bruno/Close Group/Get Close Group.yml` — `GET {{baseUrl}}/v1/close-group/{{closeGroupId}}`.

---

## Phase 7 — Validation

Run in this order:

```bash
source ~/.zshrc && source .venv/bin/activate

# 1. Migrate core (run first by convention)
python manage.py makemigrations core --check --settings=settings.development
python manage.py migrate core --settings=settings.development

# 2. Migrate calendar
python manage.py makemigrations calendar --check --settings=settings.development
python manage.py migrate calendar --settings=settings.development

# 3. Lint and type-check
ruff check . --output-format concise
ty check
```

Fix all failures before handoff.

---

## Checklist

- [ ] Phase 1 — CloseGroup model + migration + service + social graph service
- [ ] Phase 2 — Serializers + views + URL restructure
- [ ] Phase 3 — AccessType enum + AccessControlMixin + calendar migration
- [ ] Phase 4 — CalendarAccessPolicy + AccessResolver rewrite
- [ ] Phase 5 — EventWriteSerializer + TaskWriteSerializer
- [ ] Phase 6 — Bruno updates
- [ ] Phase 7 — Migrate + ruff + ty check
