import uuid

from django.db.models import Prefetch, Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.bulletin.models import Bulletin, BulletinAttachment
from shared.mixins import CustomResponse, CustomPageNumberPagination
from shared.utils.logger import application_logger


class BulletinLISTAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            school = request.school

            category_id = request.query_params.get("category_id")
            search = request.query_params.get("search")
            is_pinned = request.query_params.get("is_pinned")

            # ----------------------------------------------------------
            # GET BULLETINS
            # ----------------------------------------------------------

            bulletins = (
                Bulletin.objects
                .filter(
                    school=school,
                    is_active=True,
                    category__is_active=True,
                    status=Bulletin.Status.PUBLISHED
                )
                .select_related("category")
                .prefetch_related(
                    Prefetch(
                        "attachments",
                        queryset=BulletinAttachment.objects.filter(
                            is_active=True
                        ).order_by("-created_at"),
                    )
                )
                .order_by(
                    "-is_pinned",
                    "-created_at",
                )
            )

            # ----------------------------------------------------------
            # CATEGORY FILTER
            # ----------------------------------------------------------

            if category_id:
                try:
                    category_id = uuid.UUID(str(category_id))
                except (ValueError, TypeError):
                    return CustomResponse.errorResponse(
                        "Invalid category_id."
                    )

                bulletins = bulletins.filter(
                    category_id=category_id
                )

            # ----------------------------------------------------------
            # SEARCH
            # ----------------------------------------------------------

            if search:
                bulletins = bulletins.filter(
                    Q(title__icontains=search)
                    | Q(summary__icontains=search)
                    | Q(banner_headline__icontains=search)
                )

            # ----------------------------------------------------------
            # PINNED FILTER
            # ----------------------------------------------------------

            if is_pinned is not None:
                if str(is_pinned).lower() == "true":
                    bulletins = bulletins.filter(
                        is_pinned=True
                    )

                elif str(is_pinned).lower() == "false":
                    bulletins = bulletins.filter(
                        is_pinned=False
                    )

            # ----------------------------------------------------------
            # PAGINATION
            # ----------------------------------------------------------

            paginator = CustomPageNumberPagination()

            page = paginator.paginate_queryset(
                bulletins,
                request,
            )

            # ----------------------------------------------------------
            # RESPONSE DATA
            # ----------------------------------------------------------

            data = []

            for bulletin in page:
                data.append({
                    "id": str(bulletin.id),

                    "category": {
                        "id": str(bulletin.category.id),
                        "name": bulletin.category.name,
                    },

                    "title": bulletin.title,

                    "summary": bulletin.summary,

                    "message_body": bulletin.message_body,

                    "banner": {
                        "label": bulletin.banner_label,
                        "headline": bulletin.banner_headline,
                        "sub_text": bulletin.banner_sub_text,
                        "banner_color": bulletin.banner_color,
                    },

                    "is_pinned": bulletin.is_pinned,

                    "attachments": [
                        {
                            "id": str(attachment.id),
                            "name": attachment.name,
                            "pdf": attachment.pdf,
                        }
                        for attachment in bulletin.attachments.all()
                    ],

                    "created_at": bulletin.created_at,
                })

            application_logger.info(
                "Bulletins fetched successfully. "
                "school_id=%s page=%s",
                school.id,
                request.query_params.get("page", 1),
            )

            # ----------------------------------------------------------
            # PAGINATED RESPONSE
            # ----------------------------------------------------------

            return CustomResponse.successResponse(
                {
                    "count": paginator.page.paginator.count,
                    "next": paginator.get_next_link(),
                    "previous": paginator.get_previous_link(),
                    "results": data,
                },
                "Bulletins fetched successfully.",
            )

        except Exception as exc:
            application_logger.exception(
                "Error fetching bulletins: %s",
                exc,
            )

            return CustomResponse.errorResponse(
                "Unable to fetch bulletins."
            )