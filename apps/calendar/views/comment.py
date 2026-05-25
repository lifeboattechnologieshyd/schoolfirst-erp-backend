from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.calendar.models import Comment
from apps.calendar.services.comment import CommentService
from shared.enums import GlobalAPIMessageCodes
from shared.mixins.drf_views import CustomResponse


class CommentDestroyView(APIView, CustomResponse):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        try:
            comment = Comment.objects.get(pk=pk, deleted_at__isnull=True)
        except Comment.DoesNotExist:
            return self.build_response(
                success=False,
                error={"code": GlobalAPIMessageCodes.NOT_FOUND, "message": GlobalAPIMessageCodes.NOT_FOUND.label},
                status=status.HTTP_404_NOT_FOUND,
            )
        service = CommentService(request.user)
        try:
            service.soft_delete(comment)
        except PermissionError:
            return self.build_response(
                success=False,
                error={"code": GlobalAPIMessageCodes.FORBIDDEN, "message": GlobalAPIMessageCodes.FORBIDDEN.label},
                status=status.HTTP_403_FORBIDDEN,
            )
        return self.build_response(success=True, message="Comment deleted successfully.", data={"deleted": True})
