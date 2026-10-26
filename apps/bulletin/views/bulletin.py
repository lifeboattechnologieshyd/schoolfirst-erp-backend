import uuid

from django.db import IntegrityError, transaction
from django.db.models import Prefetch, Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.bulletin.models import Bulletin, BulletinAttachment, BulletinRead, BulletinAudience
from apps.school.models.school import Student
from shared.mixins import CustomResponse, CustomPageNumberPagination
from shared.utils.logger import application_logger


class BulletinLISTAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            # ----------------------------------------------------------
            # SCHOOL
            # ----------------------------------------------------------

            school = request.school

            if not school:
                return CustomResponse.errorResponse(
                    "School not found."
                )

            # ----------------------------------------------------------
            # QUERY PARAMETERS
            # ----------------------------------------------------------

            student_id = request.query_params.get("student_id")
            category_id = request.query_params.get("category_id")
            search = request.query_params.get("search")
            is_pinned = request.query_params.get("is_pinned")

            # ----------------------------------------------------------
            # VALIDATE STUDENT ID
            # ----------------------------------------------------------

            if not student_id:
                return CustomResponse.errorResponse(
                    "student_id is required."
                )

            try:
                student_id = uuid.UUID(str(student_id))
            except (ValueError, TypeError):
                return CustomResponse.errorResponse(
                    "Invalid student_id."
                )

            # ----------------------------------------------------------
            # GET STUDENT
            # ----------------------------------------------------------

            student = (
                Student.objects
                .filter(
                    id=student_id,
                    school=school,
                    status=Student.Status.ACTIVE,
                )
                .select_related(
                    "grade",
                    "section",
                )
                .first()
            )

            if not student:
                return CustomResponse.errorResponse(
                    "Student not found."
                )

            # ----------------------------------------------------------
            # GET BULLETINS
            # ----------------------------------------------------------

            bulletins = (
                Bulletin.objects
                .filter(
                    school=school,
                    is_active=True,
                    category__is_active=True,
                    status=Bulletin.Status.PUBLISHED,
                )
                .filter(
                    # --------------------------------------------------
                    # ALL PARENTS
                    # --------------------------------------------------
                    Q(
                        audiences__audience_type=(
                            BulletinAudience.AudienceType.ALL_PARENTS
                        ),
                        audiences__is_active=True,
                    )

                    |

                    # --------------------------------------------------
                    # STUDENT'S GRADE
                    # --------------------------------------------------
                    Q(
                        audiences__audience_type=(
                            BulletinAudience.AudienceType.GRADE
                        ),
                        audiences__grade_id=student.grade_id,
                        audiences__is_active=True,
                    )

                    |

                    # --------------------------------------------------
                    # STUDENT'S SECTION
                    # --------------------------------------------------
                    Q(
                        audiences__audience_type=(
                            BulletinAudience.AudienceType.SECTION
                        ),
                        audiences__grade_id=student.grade_id,
                        audiences__section_id=student.section_id,
                        audiences__is_active=True,
                    )
                )
                .select_related(
                    "category",
                )
                .prefetch_related(
                    Prefetch(
                        "audiences",
                        queryset=(
                            BulletinAudience.objects
                            .filter(is_active=True)
                            .select_related(
                                "grade",
                                "section",
                            )
                        ),
                    ),
                    Prefetch(
                        "attachments",
                        queryset=(
                            BulletinAttachment.objects
                            .filter(is_active=True)
                            .order_by("-created_at")
                        ),
                    ),
                )
                .distinct()
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
                    category_id = uuid.UUID(
                        str(category_id)
                    )
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
            # GET READ STATUS
            # ----------------------------------------------------------
            # Fetch all bulletins read by the current parent in one query.
            # Avoids N+1 queries inside the response loop.

            bulletin_ids = [
                bulletin.id
                for bulletin in page
            ]

            read_bulletin_ids = set(
                BulletinRead.objects
                .filter(
                    bulletin_id__in=bulletin_ids,
                    parent=request.user,
                )
                .values_list(
                    "bulletin_id",
                    flat=True,
                )
            )

            # ----------------------------------------------------------
            # RESPONSE DATA
            # ----------------------------------------------------------

            data = []

            for bulletin in page:

                # ------------------------------------------------------
                # AUDIENCE DATA
                # ------------------------------------------------------

                audience_data = []

                for audience in bulletin.audiences.all():

                    audience_data.append({
                        "id": str(audience.id),

                        "audience_type": (
                            audience.audience_type
                        ),

                        "grade_id": (
                            str(audience.grade_id)
                            if audience.grade_id
                            else None
                        ),

                        "grade_name": (
                            audience.grade.name
                            if audience.grade
                            else None
                        ),

                        "section_id": (
                            str(audience.section_id)
                            if audience.section_id
                            else None
                        ),

                        "section_name": (
                            audience.section.name
                            if audience.section
                            else None
                        ),
                    })

                # ------------------------------------------------------
                # BULLETIN DATA
                # ------------------------------------------------------

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
                        "banner_color": bulletin.banner_color,
                    },

                    # "audiences": audience_data,

                    "is_pinned": bulletin.is_pinned,

                    "is_read": (
                        bulletin.id in read_bulletin_ids
                    ),

                    "attachments": [
                        {
                            "id": str(attachment.id),
                            "name": attachment.name,
                            "pdf": attachment.pdf,
                        }
                        for attachment in bulletin.attachments.all()
                    ],

                    "created_at": bulletin.created_at,

                    "status": bulletin.status,
                })

            # ----------------------------------------------------------
            # LOG
            # ----------------------------------------------------------

            application_logger.info(
                "Student bulletins fetched successfully.",
                extra={
                    "school_id": str(school.id),
                    "student_id": str(student.id),
                    "parent_id": str(request.user.id),
                    "page": request.query_params.get("page", 1),
                    "bulletin_count": len(data),
                },
            )

            # ----------------------------------------------------------
            # RESPONSE
            # ----------------------------------------------------------

            return CustomResponse.successResponse(
                {
                    "data": data,
                },
                "Bulletins fetched successfully.",
            )

        except Exception as exc:

            application_logger.exception(
                "Error fetching student bulletins.",
                extra={
                    "school_id": (
                        str(request.school.id)
                        if getattr(request, "school", None)
                        else None
                    ),
                    "student_id": request.query_params.get(
                        "student_id"
                    ),
                    "parent_id": str(request.user.id),
                    "error": str(exc),
                },
            )

            return CustomResponse.errorResponse(
                "Unable to fetch bulletins."
            )


class BulletinReadAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        try:
            school = request.school
            bulletin_id = request.data.get("bulletin_id")


            # ----------------------------------------------------------
            # VALIDATE BULLETIN ID
            # ----------------------------------------------------------

            try:
                bulletin_id = uuid.UUID(str(bulletin_id))
            except (ValueError, TypeError):
                return CustomResponse.errorResponse(
                    "Invalid bulletin_id."
                )

            # ----------------------------------------------------------
            # GET BULLETIN
            # ----------------------------------------------------------

            bulletin = Bulletin.objects.filter(
                id=bulletin_id,
                school=school,
                is_active=True,
            ).first()

            if not bulletin:
                return CustomResponse.errorResponse(
                    "Bulletin not found."
                )

            # ----------------------------------------------------------
            # CREATE READ RECORD
            # ----------------------------------------------------------

            bulletin_read, created = BulletinRead.objects.get_or_create(
                bulletin=bulletin,
                parent=request.user,
            )

            application_logger.info(
                "Bulletin read successfully. "
                "bulletin_id=%s parent_id=%s created=%s",
                bulletin.id,
                request.user.id,
                created,
            )

            # ----------------------------------------------------------
            # RESPONSE
            # ----------------------------------------------------------

            return CustomResponse.successResponse(
                {
                    "bulletin_id": str(bulletin.id),
                    "is_read": True,
                    "read_at": bulletin_read.read_at,
                },
                "Bulletin marked as read.",
            )

        except IntegrityError:
            # Handles concurrent requests safely
            bulletin_read = BulletinRead.objects.filter(
                bulletin_id=bulletin_id,
                parent=request.user,
            ).first()

            if bulletin_read:
                return CustomResponse.successResponse(
                    {
                        "bulletin_id": str(bulletin_id),
                        "is_read": True,
                        "read_at": bulletin_read.read_at,
                    },
                    "Bulletin already marked as read.",
                )

            application_logger.exception(
                "Integrity error while marking bulletin as read. "
                "bulletin_id=%s parent_id=%s",
                bulletin_id,
                request.user.id,
            )

            return CustomResponse.errorResponse(
                "Unable to mark bulletin as read."
            )

        except Exception as exc:
            application_logger.exception(
                "Error marking bulletin as read: %s",
                exc,
            )

            return CustomResponse.errorResponse(
                "Unable to mark bulletin as read."
            )


