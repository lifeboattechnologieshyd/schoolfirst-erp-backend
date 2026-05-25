import uuid
from typing import cast

from django.db.models import F
from django.utils import timezone

from apps.calendar.enums import CommentParentType
from apps.calendar.models import Comment, Event, Task
from apps.calendar.services.access import AccessResolver, assert_is_creator


class CommentService:
    def __init__(self, user):
        self.user = user
        self._resolver = AccessResolver(user)

    def _assert_parent_access(self, parent_type: str, parent_id: uuid.UUID):
        """Raise PermissionError if the user cannot see the parent record."""
        access_filter = self._resolver.build_access_filter()

        if parent_type == CommentParentType.EVENT:
            if not Event.objects.filter(access_filter, pk=parent_id).exists():
                raise PermissionError("You do not have access to this event.")
        elif parent_type == CommentParentType.TASK:
            if not Task.objects.filter(access_filter, pk=parent_id).exists():
                raise PermissionError("You do not have access to this task.")
        else:
            raise ValueError(f"Unknown parent_type: {parent_type}")

    def _get_parent_model(self, parent_type: str):
        if parent_type == CommentParentType.EVENT:
            return Event
        if parent_type == CommentParentType.TASK:
            return Task
        raise ValueError(f"Unknown parent_type: {parent_type}")

    def _adjust_comment_count(self, parent_type: str, parent_id: uuid.UUID, delta: int):
        self._get_parent_model(parent_type).objects.filter(pk=parent_id).update(
            comment_count=F("comment_count") + delta
        )

    def create(self, parent_type: str, parent_id: uuid.UUID, body: str) -> Comment:
        self._assert_parent_access(parent_type, parent_id)
        comment = Comment.objects.create(
            parent_type=parent_type,
            parent_id=parent_id,
            user_id=self.user.id,
            body=body,
        )
        self._adjust_comment_count(parent_type, parent_id, 1)
        return comment

    def list_for_parent(self, parent_type: str, parent_id: uuid.UUID):
        self._assert_parent_access(parent_type, parent_id)
        return Comment.objects.filter(
            parent_type=parent_type,
            parent_id=parent_id,
            deleted_at__isnull=True,
        ).order_by("created_at")

    def soft_delete(self, comment: Comment):
        assert_is_creator(self.user, comment, id_field="user_id")
        comment.deleted_at = timezone.now()
        comment.save()
        self._adjust_comment_count(str(comment.parent_type), cast(uuid.UUID, comment.parent_id), -1)
