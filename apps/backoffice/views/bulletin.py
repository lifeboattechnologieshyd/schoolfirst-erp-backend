import json
import uuid

from django.db import IntegrityError, transaction
from django.db.models import Prefetch
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.bulletin.models import BulletinCategory, Bulletin, BulletinAttachment, BulletinAudience, BulletinRead
from apps.school.models.school import Section, Grade
from shared.mixins import CustomResponse
from shared.permissions import HasPermission
from shared.utils.logger import application_logger


class BulletinCategoryCreateAPIView(APIView):
    permission_classes = [IsAuthenticated,HasPermission]

    required_permission = "bulletin_category.create"


    def post(self, request):
        try:
            school = request.school

            name = request.data.get("name")
            description = request.data.get("description")

            # =========================================================
            # VALIDATION
            # =========================================================

            if not name:
                return CustomResponse.errorResponse(
                    description="Category name is required."
                )

            name = str(name).strip()

            if not name:
                return CustomResponse.errorResponse(
                    description="Category name cannot be empty."
                )

            # =========================================================
            # DUPLICATE CHECK
            # =========================================================

            if BulletinCategory.objects.filter(
                school=school,
                name__iexact=name,
            ).exists():
                return CustomResponse.errorResponse(
                    description=(
                        "Bulletin category with this name "
                        "already exists."
                    )
                )

            # =========================================================
            # CREATE
            # =========================================================

            category = BulletinCategory.objects.create(
                school=school,
                name=name,
                description=(
                    str(description).strip()
                    if description
                    else None
                ),
                is_active=True,
                created_by=request.user,
            )

            application_logger.info(
                "Bulletin category created successfully. "
                "category_id=%s school_id=%s created_by=%s",
                category.id,
                school.id,
                request.user.id,
            )

            # =========================================================
            # RESPONSE
            # =========================================================

            data = {
                "id": str(category.id),
                "name": category.name,
                "description": category.description,
                "is_active": category.is_active,
            }

            return CustomResponse.successResponse(
                data=data,
                description=(
                    "Bulletin category created successfully."
                ),
            )

        except IntegrityError:

            application_logger.exception(
                "Duplicate bulletin category creation. "
                "school_id=%s",
                request.school.id,
            )

            return CustomResponse.errorResponse(
                description=(
                    "Bulletin category with this name "
                    "already exists."
                )
            )

        except Exception as e:

            application_logger.exception(
                "Error creating bulletin category. "
                "error=%s",
                str(e),
            )

            return CustomResponse.errorResponse(
                description=(
                    "Failed to create bulletin category."
                )
            )

class BulletinCategoryListAPIView(APIView):
    permission_classes = [IsAuthenticated,HasPermission]

    required_permission = "bulletin_category.view"


    def get(self, request):
        try:
            school = request.school

            search = request.query_params.get(
                "search"
            )

            categories = BulletinCategory.objects.filter(
                school=school,
                is_active=True,
            ).order_by("name")

            if search:
                search = search.strip()

                if search:
                    categories = categories.filter(
                        name__icontains=search
                    )

            data = []

            for category in categories:

                data.append(
                    {
                        "id": str(category.id),
                        "name": category.name,
                        "description": category.description,
                        "is_active": category.is_active,
                    }
                )

            application_logger.info(
                "Bulletin categories fetched successfully. "
                "school_id=%s count=%s",
                school.id,
                len(data),
            )

            return CustomResponse.successResponse(
                data=data,
                description=(
                    "Bulletin categories fetched successfully."
                ),
            )

        except Exception as e:

            application_logger.exception(
                "Error fetching bulletin categories. "
                "error=%s",
                str(e),
            )

            return CustomResponse.errorResponse(
                description=(
                    "Failed to fetch bulletin categories."
                )
            )

class BulletinCategoryUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated,HasPermission]
    required_permission = "bulletin_category.update"

    def put(self, request, category_id):
        try:
            school = request.school

            # =========================================================
            # VALIDATE UUID
            # =========================================================

            try:
                category_uuid = uuid.UUID(
                    str(category_id)
                )

            except (ValueError, TypeError):
                return CustomResponse.errorResponse(
                    description="Invalid category_id."
                )

            # =========================================================
            # GET CATEGORY
            # =========================================================

            category = BulletinCategory.objects.filter(
                id=category_uuid,
                school=school,
                is_active=True,
            ).first()

            if not category:
                return CustomResponse.errorResponse(
                    description=(
                        "Bulletin category not found."
                    )
                )

            # =========================================================
            # GET DATA
            # =========================================================

            name = request.data.get("name")
            description = request.data.get(
                "description"
            )

            update_fields = []

            # =========================================================
            # UPDATE NAME
            # =========================================================

            if name is not None:

                name = str(name).strip()

                if not name:
                    return CustomResponse.errorResponse(
                        description=(
                            "Category name cannot be empty."
                        )
                    )

                # -----------------------------------------------------
                # Duplicate check
                # -----------------------------------------------------

                if BulletinCategory.objects.filter(
                    school=school,
                    name__iexact=name,
                ).exclude(
                    id=category.id
                ).exists():

                    return CustomResponse.errorResponse(
                        description=(
                            "Bulletin category with this "
                            "name already exists."
                        )
                    )

                category.name = name
                update_fields.append("name")

            # =========================================================
            # UPDATE DESCRIPTION
            # =========================================================

            if description is not None:

                description = str(
                    description
                ).strip()

                category.description = (
                    description or None
                )

                update_fields.append(
                    "description"
                )

            # =========================================================
            # NOTHING TO UPDATE
            # =========================================================

            if not update_fields:
                return CustomResponse.errorResponse(
                    description=(
                        "No fields provided for update."
                    )
                )

            # =========================================================
            # SAVE
            # =========================================================

            category.updated_by = request.user

            update_fields.extend(
                [
                    "updated_by",
                    "updated_at",
                ]
            )

            category.save(
                update_fields=update_fields
            )

            application_logger.info(
                "Bulletin category updated successfully. "
                "category_id=%s school_id=%s updated_by=%s",
                category.id,
                school.id,
                request.user.id,
            )

            # =========================================================
            # RESPONSE
            # =========================================================

            data = {
                "id": str(category.id),
                "name": category.name,
                "description": category.description,
                "is_active": category.is_active,
            }

            return CustomResponse.successResponse(
                data=data,
                description=(
                    "Bulletin category updated successfully."
                ),
            )

        except IntegrityError:

            application_logger.exception(
                "Duplicate bulletin category update. "
                "category_id=%s",
                category_id,
            )

            return CustomResponse.errorResponse(
                description=(
                    "Bulletin category with this name "
                    "already exists."
                )
            )

        except Exception as e:

            application_logger.exception(
                "Error updating bulletin category. "
                "category_id=%s error=%s",
                category_id,
                str(e),
            )

            return CustomResponse.errorResponse(
                description=(
                    "Failed to update bulletin category."
                )
            )

class BulletinCategoryDeleteAPIView(APIView):
    permission_classes = [IsAuthenticated,HasPermission]

    required_permission = "bulletin_category.delete"


    def delete(self, request, category_id):
        try:
            school = request.school

            # =========================================================
            # VALIDATE UUID
            # =========================================================

            try:
                category_uuid = uuid.UUID(
                    str(category_id)
                )

            except (ValueError, TypeError):
                return CustomResponse.errorResponse(
                    description="Invalid category_id."
                )

            # =========================================================
            # GET CATEGORY
            # =========================================================

            category = BulletinCategory.objects.filter(
                id=category_uuid,
                school=school,
                is_active=True,
            ).first()

            if not category:
                return CustomResponse.errorResponse(
                    description=(
                        "Bulletin category not found."
                    )
                )

            # =========================================================
            # SOFT DELETE
            # =========================================================

            category.is_active = False
            category.updated_by = request.user

            category.save(
                update_fields=[
                    "is_active",
                    "updated_by",
                    "updated_at",
                ]
            )

            application_logger.info(
                "Bulletin category deleted successfully. "
                "category_id=%s school_id=%s deleted_by=%s",
                category.id,
                school.id,
                request.user.id,
            )

            return CustomResponse.successResponse(
                data={
                    "id": str(category.id),
                },
                description=(
                    "Bulletin category deleted successfully."
                ),
            )

        except Exception as e:

            application_logger.exception(
                "Error deleting bulletin category. "
                "category_id=%s error=%s",
                category_id,
                str(e),
            )

            return CustomResponse.errorResponse(
                description=(
                    "Failed to delete bulletin category."
                )
            )

class BulletinCreateAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "bulletin.create"

    @transaction.atomic
    def post(self, request):
        try:
            school = request.school

            category_id = request.data.get("category_id")
            title = request.data.get("title")
            summary = request.data.get("summary")
            message_body = request.data.get("message_body")

            # Banner
            banner_label = request.data.get("banner_label")
            banner_headline = request.data.get("banner_headline")
            banner_color = request.data.get("banner_color")
            is_pinned = request.data.get("is_pinned", False)

            # Audience
            audiences = request.data.get("audiences", [])

            # ----------------------------------------------------------
            # BASIC VALIDATION
            # ----------------------------------------------------------

            if not category_id:
                return CustomResponse.errorResponse(
                    "Category is required."
                )

            if not title:
                return CustomResponse.errorResponse(
                    "Title is required."
                )

            try:
                category_id = uuid.UUID(str(category_id))
            except (ValueError, TypeError):
                return CustomResponse.errorResponse(
                    "Invalid category_id."
                )

            category = BulletinCategory.objects.filter(
                id=category_id,
                school=school,
                is_active=True,
            ).first()

            if not category:
                return CustomResponse.errorResponse(
                    "Bulletin category not found."
                )

            # ----------------------------------------------------------
            # BANNER COLOR
            # ----------------------------------------------------------

            if banner_color:
                valid_colors = [
                    choice[0]
                    for choice in Bulletin.BannerColor.choices
                ]

                if banner_color not in valid_colors:
                    return CustomResponse.errorResponse(
                        f"Invalid banner_color. "
                        f"Allowed values: {', '.join(valid_colors)}"
                    )

            # ----------------------------------------------------------
            # PARSE AUDIENCES
            # ----------------------------------------------------------

            if isinstance(audiences, str):
                try:
                    audiences = json.loads(audiences)
                except json.JSONDecodeError:
                    return CustomResponse.errorResponse(
                        "Invalid audiences format."
                    )

            if not isinstance(audiences, list):
                return CustomResponse.errorResponse(
                    "Audiences must be a list."
                )

            if not audiences:
                return CustomResponse.errorResponse(
                    "At least one audience is required."
                )

            # ----------------------------------------------------------
            # CREATE BULLETIN
            # ----------------------------------------------------------

            bulletin = Bulletin.objects.create(
                school=school,
                category=category,
                title=title,
                summary=summary,
                message_body=message_body,

                banner_label=banner_label,
                banner_headline=banner_headline,
                banner_color=(
                    banner_color
                    or Bulletin.BannerColor.INDIGO
                ),

                is_pinned=is_pinned,
                is_active=True,

                created_by=request.user,
            )

            # ----------------------------------------------------------
            # CREATE AUDIENCES
            # ----------------------------------------------------------

            audience_data = []

            for audience_item in audiences:

                if not isinstance(audience_item, dict):
                    return CustomResponse.errorResponse(
                        "Each audience must be an object."
                    )

                audience_type = audience_item.get(
                    "audience_type"
                )

                grade_id = audience_item.get("grade_id")
                section_id = audience_item.get("section_id")

                valid_audience_types = [
                    choice[0]
                    for choice in BulletinAudience.AudienceType.choices
                ]

                if audience_type not in valid_audience_types:
                    return CustomResponse.errorResponse(
                        f"Invalid audience_type. "
                        f"Allowed values: "
                        f"{', '.join(valid_audience_types)}"
                    )

                # ------------------------------------------------------
                # ALL PARENTS
                # ------------------------------------------------------

                if audience_type == (
                    BulletinAudience.AudienceType.ALL_PARENTS
                ):
                    if grade_id or section_id:
                        return CustomResponse.errorResponse(
                            "Grade or section is not allowed "
                            "for ALL_PARENTS."
                        )

                    audience = BulletinAudience.objects.create(
                        bulletin=bulletin,
                        audience_type=audience_type,
                        is_active=True,
                        created_by=request.user,
                    )

                # ------------------------------------------------------
                # GRADE
                # ------------------------------------------------------

                elif audience_type == (
                    BulletinAudience.AudienceType.GRADE
                ):
                    if not grade_id:
                        return CustomResponse.errorResponse(
                            "grade_id is required for GRADE audience."
                        )

                    if section_id:
                        return CustomResponse.errorResponse(
                            "section_id is not allowed for GRADE audience."
                        )

                    try:
                        grade_id = uuid.UUID(str(grade_id))
                    except (ValueError, TypeError):
                        return CustomResponse.errorResponse(
                            "Invalid grade_id."
                        )

                    # Replace Grade with your actual model import.
                    grade = Grade.objects.filter(
                        id=grade_id,
                        school=school,
                    ).first()

                    if not grade:
                        return CustomResponse.errorResponse(
                            "Grade not found."
                        )

                    audience = BulletinAudience.objects.create(
                        bulletin=bulletin,
                        audience_type=audience_type,
                        grade=grade,
                        is_active=True,
                        created_by=request.user,
                    )

                # ------------------------------------------------------
                # SECTION
                # ------------------------------------------------------

                else:
                    if not grade_id:
                        return CustomResponse.errorResponse(
                            "grade_id is required for SECTION audience."
                        )

                    if not section_id:
                        return CustomResponse.errorResponse(
                            "section_id is required for SECTION audience."
                        )

                    try:
                        grade_id = uuid.UUID(str(grade_id))
                        section_id = uuid.UUID(str(section_id))
                    except (ValueError, TypeError):
                        return CustomResponse.errorResponse(
                            "Invalid grade_id or section_id."
                        )

                    grade = Grade.objects.filter(
                        id=grade_id,
                        school=school,
                    ).first()

                    if not grade:
                        return CustomResponse.errorResponse(
                            "Grade not found."
                        )

                    section = Section.objects.filter(
                        id=section_id,
                        grade=grade,
                    ).first()

                    if not section:
                        return CustomResponse.errorResponse(
                            "Section not found for the selected grade."
                        )

                    audience = BulletinAudience.objects.create(
                        bulletin=bulletin,
                        audience_type=audience_type,
                        grade=grade,
                        section=section,
                        is_active=True,
                        created_by=request.user,
                    )

                audience_data.append({
                    "id": str(audience.id),
                    "audience_type": audience.audience_type,
                    "grade_id": (
                        str(audience.grade_id)
                        if audience.grade_id
                        else None
                    ),
                    "section_id": (
                        str(audience.section_id)
                        if audience.section_id
                        else None
                    ),
                })

            # ----------------------------------------------------------
            # ATTACHMENTS
            # ----------------------------------------------------------

            attachments = request.data.get("attachments", [])

            if isinstance(attachments, str):
                try:
                    attachments = json.loads(attachments)
                except json.JSONDecodeError:
                    return CustomResponse.errorResponse(
                        "Invalid attachments format."
                    )

            if not isinstance(attachments, list):
                return CustomResponse.errorResponse(
                    "Attachments must be a list."
                )

            attachment_data = []

            for attachment_item in attachments:

                if not isinstance(attachment_item, dict):
                    return CustomResponse.errorResponse(
                        "Each attachment must be an object."
                    )

                name = attachment_item.get("name")
                pdf = attachment_item.get("pdf")

                if not name:
                    return CustomResponse.errorResponse(
                        "Attachment name is required."
                    )

                if not pdf:
                    return CustomResponse.errorResponse(
                        f"PDF is required for attachment '{name}'."
                    )

                attachment = BulletinAttachment.objects.create(
                    bulletin=bulletin,
                    name=name,
                    pdf=pdf,
                    is_active=True,
                    created_by=request.user,
                )

                attachment_data.append({
                    "id": str(attachment.id),
                    "name": attachment.name,
                    "pdf": attachment.pdf,
                })

            # ----------------------------------------------------------
            # LOG
            # ----------------------------------------------------------

            application_logger.info(
                "Bulletin created successfully. "
                "bulletin_id=%s school_id=%s",
                bulletin.id,
                school.id,
            )

            # ----------------------------------------------------------
            # RESPONSE
            # ----------------------------------------------------------

            return CustomResponse.successResponse(
                {
                    "id": str(bulletin.id),

                    "category": {
                        "id": str(category.id),
                        "name": category.name,
                    },

                    "title": bulletin.title,
                    "summary": bulletin.summary,
                    "message_body": bulletin.message_body,

                    "banner": {
                        "label": bulletin.banner_label,
                        "headline": bulletin.banner_headline,
                        "color": bulletin.banner_color,
                    },

                    "audiences": audience_data,

                    "is_pinned": bulletin.is_pinned,
                    "is_active": bulletin.is_active,

                    "attachments": attachment_data,
                },
                "Bulletin created successfully.",
            )

        except Exception as exc:
            application_logger.exception(
                "Error creating bulletin: %s",
                exc,
            )

            return CustomResponse.errorResponse(
                "Unable to create bulletin."
            )


class BulletinListAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "bulletin.view"

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
                )
                .select_related("category")
                .prefetch_related(
                    Prefetch(
                        "audiences",
                        queryset=BulletinAudience.objects.filter(
                            is_active=True
                        ).select_related(
                            "grade",
                            "section",
                        ),
                    ),
                    Prefetch(
                        "attachments",
                        queryset=BulletinAttachment.objects.filter(
                            is_active=True
                        ).order_by("-created_at"),
                    ),
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
                    | Q(message_body__icontains=search)
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
            # RESPONSE DATA
            # ----------------------------------------------------------

            data = []

            for bulletin in bulletins:

                # ======================================================
                # AUDIENCE
                # ======================================================

                audience_data = []

                # UserMaster IDs targeted by this bulletin
                targeted_parent_ids = set()

                for audience in bulletin.audiences.all():

                    # --------------------------------------------------
                    # ALL PARENTS
                    # --------------------------------------------------

                    if (
                        audience.audience_type
                        == BulletinAudience.AudienceType.ALL_PARENTS
                    ):
                        audience_name = "All Parents"

                        students = Student.objects.filter(
                            school=school,
                            status=Student.Status.ACTIVE,
                        ).filter(
                            Q(father_mobile__isnull=False)
                            | Q(mother_mobile__isnull=False)
                            | Q(guardian_mobile__isnull=False)
                        )

                    # --------------------------------------------------
                    # GRADE
                    # --------------------------------------------------

                    elif (
                        audience.audience_type
                        == BulletinAudience.AudienceType.GRADE
                    ):
                        audience_name = (
                            f"Grade {audience.grade.name}"
                        )

                        students = Student.objects.filter(
                            school=school,
                            grade_id=audience.grade_id,
                            status=Student.Status.ACTIVE,
                        ).filter(
                            Q(father_mobile__isnull=False)
                            | Q(mother_mobile__isnull=False)
                            | Q(guardian_mobile__isnull=False)
                        )

                    # --------------------------------------------------
                    # SECTION
                    # --------------------------------------------------

                    else:
                        audience_name = (
                            f"Grade {audience.grade.name} · "
                            f"Sec {audience.section.name}"
                        )

                        students = Student.objects.filter(
                            school=school,
                            grade_id=audience.grade_id,
                            section_id=audience.section_id,
                            status=Student.Status.ACTIVE,
                        ).filter(
                            Q(father_mobile__isnull=False)
                            | Q(mother_mobile__isnull=False)
                            | Q(guardian_mobile__isnull=False)
                        )

                    # --------------------------------------------------
                    # GET PARENT MOBILE NUMBERS
                    # --------------------------------------------------

                    parent_mobiles = set()

                    for student in students.only(
                        "father_mobile",
                        "mother_mobile",
                        "guardian_mobile",
                    ):
                        if student.father_mobile:
                            parent_mobiles.add(
                                student.father_mobile
                            )

                        if student.mother_mobile:
                            parent_mobiles.add(
                                student.mother_mobile
                            )

                        if student.guardian_mobile:
                            parent_mobiles.add(
                                student.guardian_mobile
                            )

                    # --------------------------------------------------
                    # RESOLVE USERMASTER IDS
                    # --------------------------------------------------

                    if parent_mobiles:
                        parent_ids = (
                            UserMaster.objects
                            .filter(
                                mobile__in=parent_mobiles,
                            )
                            .values_list(
                                "id",
                                flat=True,
                            )
                        )

                        targeted_parent_ids.update(
                            parent_ids
                        )

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

                        "name": audience_name,
                    })

                # ======================================================
                # READ COUNT
                # ======================================================

                targeted_parent_ids = set(
                    targeted_parent_ids
                )

                targeted_parent_count = len(
                    targeted_parent_ids
                )

                read_parent_ids = set(
                    BulletinRead.objects.filter(
                        bulletin=bulletin,
                        parent_id__in=targeted_parent_ids,
                    ).values_list(
                        "parent_id",
                        flat=True,
                    )
                )

                read_count = len(read_parent_ids)

                # ======================================================
                # READ PERCENTAGE
                # ======================================================

                read_percentage = 0

                if targeted_parent_count:
                    read_percentage = round(
                        (
                            read_count
                            / targeted_parent_count
                        ) * 100,
                        2,
                    )

                # ======================================================
                # RESPONSE
                # ======================================================

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

                    "audiences": audience_data,

                    "targeted_parent_count": (
                        targeted_parent_count
                    ),

                    "read_count": read_count,

                    "read_percentage": read_percentage,

                    "is_pinned": bulletin.is_pinned,

                    "is_active": bulletin.is_active,

                    "attachments": [
                        {
                            "id": str(attachment.id),
                            "name": attachment.name,
                            "pdf": attachment.pdf,
                        }
                        for attachment in bulletin.attachments.all()
                    ],

                    "created_at": bulletin.created_at,

                    "updated_at": bulletin.updated_at,

                    "status": bulletin.status,
                })

            # ----------------------------------------------------------
            # LOG
            # ----------------------------------------------------------

            application_logger.info(
                "Bulletins fetched successfully. "
                "school_id=%s count=%s",
                school.id,
                len(data),
            )

            return CustomResponse.successResponse(
                data,
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


class BulletinUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "bulletin.update"

    @transaction.atomic
    def put(self, request, bulletin_id):

        try:
            school = request.school

            # ==========================================================
            # BULLETIN ID
            # ==========================================================

            try:
                bulletin_id = uuid.UUID(str(bulletin_id))
            except (ValueError, TypeError):
                return CustomResponse.errorResponse(
                    "Invalid bulletin_id."
                )

            # ==========================================================
            # GET BULLETIN
            # ==========================================================

            bulletin = Bulletin.objects.filter(
                id=bulletin_id,
                school=school,
                is_active=True,
            ).first()

            if not bulletin:
                return CustomResponse.errorResponse(
                    "Bulletin not found."
                )

            # ==========================================================
            # CATEGORY
            # ==========================================================

            if "category_id" in request.data:

                category_id = request.data.get("category_id")

                try:
                    category_id = uuid.UUID(str(category_id))
                except (ValueError, TypeError):
                    return CustomResponse.errorResponse(
                        "Invalid category_id."
                    )

                category = BulletinCategory.objects.filter(
                    id=category_id,
                    school=school,
                    is_active=True,
                ).first()

                if not category:
                    return CustomResponse.errorResponse(
                        "Bulletin category not found."
                    )

                bulletin.category = category

            # ==========================================================
            # CONTENT
            # ==========================================================

            if "title" in request.data:

                title = request.data.get("title")

                if not title:
                    return CustomResponse.errorResponse(
                        "Title cannot be empty."
                    )

                bulletin.title = title

            if "summary" in request.data:
                bulletin.summary = request.data.get("summary")

            if "message_body" in request.data:
                bulletin.message_body = request.data.get(
                    "message_body"
                )

            # ==========================================================
            # BANNER
            # ==========================================================

            if "banner_label" in request.data:
                bulletin.banner_label = request.data.get(
                    "banner_label"
                )

            if "banner_headline" in request.data:
                bulletin.banner_headline = request.data.get(
                    "banner_headline"
                )

            # ----------------------------------------------------------
            # banner_sub_text REMOVED
            #
            # In the new design, SUB-TEXT represents Audience.
            # Audience is stored in BulletinAudience.
            # ----------------------------------------------------------

            if "banner_color" in request.data:

                banner_color = request.data.get(
                    "banner_color"
                )

                valid_colors = [
                    choice[0]
                    for choice in Bulletin.BannerColor.choices
                ]

                if banner_color not in valid_colors:
                    return CustomResponse.errorResponse(
                        "Invalid banner_color. "
                        f"Allowed values: {', '.join(valid_colors)}"
                    )

                bulletin.banner_color = banner_color

            # ==========================================================
            # PINNED
            # ==========================================================

            if "is_pinned" in request.data:

                is_pinned = request.data.get("is_pinned")

                if isinstance(is_pinned, str):
                    is_pinned = is_pinned.lower() == "true"

                bulletin.is_pinned = is_pinned

            # ==========================================================
            # STATUS
            # ==========================================================

            if "status" in request.data:

                status = request.data.get("status")

                valid_statuses = [
                    choice[0]
                    for choice in Bulletin.Status.choices
                ]

                if status not in valid_statuses:
                    return CustomResponse.errorResponse(
                        "Invalid status. "
                        f"Allowed values: {', '.join(valid_statuses)}"
                    )

                bulletin.status = status

            # ==========================================================
            # UPDATED BY
            # ==========================================================

            bulletin.updated_by = request.user

            bulletin.save()

            # ==========================================================
            # AUDIENCE
            # ==========================================================

            if "audiences" in request.data:

                audiences = request.data.get("audiences")

                # Multipart/form-data may send JSON as string
                if isinstance(audiences, str):
                    try:
                        audiences = json.loads(audiences)
                    except json.JSONDecodeError:
                        return CustomResponse.errorResponse(
                            "Invalid audiences format."
                        )

                if not isinstance(audiences, list):
                    return CustomResponse.errorResponse(
                        "Audiences must be a list."
                    )

                # ------------------------------------------------------
                # Validate everything BEFORE deleting existing audiences
                # ------------------------------------------------------

                validated_audiences = []

                for audience_item in audiences:

                    if not isinstance(audience_item, dict):
                        return CustomResponse.errorResponse(
                            "Each audience must be an object."
                        )

                    audience_type = audience_item.get(
                        "audience_type"
                    )

                    valid_audience_types = [
                        choice[0]
                        for choice in BulletinAudience.AudienceType.choices
                    ]

                    if audience_type not in valid_audience_types:
                        return CustomResponse.errorResponse(
                            "Invalid audience_type. "
                            f"Allowed values: "
                            f"{', '.join(valid_audience_types)}"
                        )

                    grade_id = audience_item.get("grade_id")
                    section_id = audience_item.get("section_id")

                    # --------------------------------------------------
                    # ALL PARENTS
                    # --------------------------------------------------

                    if (
                        audience_type
                        == BulletinAudience.AudienceType.ALL_PARENTS
                    ):

                        if grade_id or section_id:
                            return CustomResponse.errorResponse(
                                "grade_id and section_id must be empty "
                                "for ALL_PARENTS."
                            )

                        validated_audiences.append({
                            "audience_type": audience_type,
                            "grade_id": None,
                            "section_id": None,
                        })

                    # --------------------------------------------------
                    # GRADE
                    # --------------------------------------------------

                    elif (
                        audience_type
                        == BulletinAudience.AudienceType.GRADE
                    ):

                        if not grade_id:
                            return CustomResponse.errorResponse(
                                "grade_id is required for GRADE audience."
                            )

                        try:
                            grade_id = uuid.UUID(
                                str(grade_id)
                            )
                        except (ValueError, TypeError):
                            return CustomResponse.errorResponse(
                                "Invalid grade_id."
                            )

                        grade_exists = Grade.objects.filter(
                            id=grade_id,
                            school=school,
                            is_active=True,
                        ).exists()

                        if not grade_exists:
                            return CustomResponse.errorResponse(
                                "Grade not found."
                            )

                        if section_id:
                            return CustomResponse.errorResponse(
                                "section_id must be empty "
                                "for GRADE audience."
                            )

                        validated_audiences.append({
                            "audience_type": audience_type,
                            "grade_id": grade_id,
                            "section_id": None,
                        })

                    # --------------------------------------------------
                    # SECTION
                    # --------------------------------------------------

                    elif (
                        audience_type
                        == BulletinAudience.AudienceType.SECTION
                    ):

                        if not grade_id:
                            return CustomResponse.errorResponse(
                                "grade_id is required for SECTION audience."
                            )

                        if not section_id:
                            return CustomResponse.errorResponse(
                                "section_id is required for SECTION audience."
                            )

                        try:
                            grade_id = uuid.UUID(
                                str(grade_id)
                            )

                            section_id = uuid.UUID(
                                str(section_id)
                            )

                        except (ValueError, TypeError):
                            return CustomResponse.errorResponse(
                                "Invalid grade_id or section_id."
                            )

                        grade_exists = Grade.objects.filter(
                            id=grade_id,
                            school=school,
                            is_active=True,
                        ).exists()

                        if not grade_exists:
                            return CustomResponse.errorResponse(
                                "Grade not found."
                            )

                        section_exists = Section.objects.filter(
                            id=section_id,
                            grade_id=grade_id,
                            is_active=True,
                        ).exists()

                        if not section_exists:
                            return CustomResponse.errorResponse(
                                "Section not found for the selected grade."
                            )

                        validated_audiences.append({
                            "audience_type": audience_type,
                            "grade_id": grade_id,
                            "section_id": section_id,
                        })

                # ------------------------------------------------------
                # REMOVE OLD AUDIENCES
                # ------------------------------------------------------

                BulletinAudience.objects.filter(
                    bulletin=bulletin,
                    is_active=True,
                ).update(
                    is_active=False,
                    updated_by=request.user,
                )

                # ------------------------------------------------------
                # CREATE NEW AUDIENCES
                # ------------------------------------------------------

                for audience in validated_audiences:

                    BulletinAudience.objects.create(
                        bulletin=bulletin,
                        audience_type=audience["audience_type"],
                        grade_id=audience["grade_id"],
                        section_id=audience["section_id"],
                        is_active=True,
                        created_by=request.user,
                    )

            # ==========================================================
            # REMOVE ATTACHMENTS
            # ==========================================================

            remove_attachment_ids = request.data.get(
                "remove_attachment_ids"
            )

            if remove_attachment_ids:

                if isinstance(remove_attachment_ids, str):

                    try:
                        remove_attachment_ids = json.loads(
                            remove_attachment_ids
                        )

                    except json.JSONDecodeError:

                        remove_attachment_ids = [
                            item.strip()
                            for item in remove_attachment_ids.split(",")
                            if item.strip()
                        ]

                if not isinstance(
                    remove_attachment_ids,
                    list,
                ):
                    return CustomResponse.errorResponse(
                        "remove_attachment_ids must be a list."
                    )

                BulletinAttachment.objects.filter(
                    id__in=remove_attachment_ids,
                    bulletin=bulletin,
                    is_active=True,
                ).update(
                    is_active=False,
                    updated_by=request.user,
                )

            # ==========================================================
            # ADD NEW ATTACHMENTS
            # ==========================================================

            attachments = request.FILES.getlist(
                "attachments"
            )

            for file in attachments:

                BulletinAttachment.objects.create(
                    bulletin=bulletin,
                    name=file.name,

                    # Replace with actual uploaded URL
                    pdf=file.name,

                    is_active=True,
                    created_by=request.user,
                )

            # ==========================================================
            # LOG
            # ==========================================================

            application_logger.info(
                "Bulletin updated successfully. "
                "bulletin_id=%s school_id=%s",
                bulletin.id,
                school.id,
            )

            # ==========================================================
            # RESPONSE
            # ==========================================================

            return CustomResponse.successResponse(
                {
                    "id": str(bulletin.id),
                },
                "Bulletin updated successfully.",
            )

        except Exception as exc:

            application_logger.exception(
                "Error updating bulletin: %s",
                exc,
            )

            return CustomResponse.errorResponse(
                "Unable to update bulletin."
            )


class BulletinDeleteAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "bulletin.delete"

    @transaction.atomic
    def delete(self, request, bulletin_id):
        try:
            school = request.school

            try:
                bulletin_id = uuid.UUID(str(bulletin_id))
            except (ValueError, TypeError):
                return CustomResponse.errorResponse(
                    "Invalid bulletin_id."
                )

            bulletin = Bulletin.objects.filter(
                id=bulletin_id,
                school=school,
                is_active=True,
            ).first()

            if not bulletin:
                return CustomResponse.errorResponse(
                    "Bulletin not found."
                )

            bulletin.is_active = False
            bulletin.updated_by = request.user
            bulletin.save(
                update_fields=[
                    "is_active",
                    "updated_by",
                    "updated_at",
                ]
            )

            # Soft delete attachments
            BulletinAttachment.objects.filter(
                bulletin=bulletin,
                is_active=True,
            ).update(
                is_active=False,
                updated_by=request.user,
            )

            application_logger.info(
                "Bulletin deleted successfully. "
                "bulletin_id=%s school_id=%s",
                bulletin.id,
                school.id,
            )

            return CustomResponse.successResponse(
                {},
                "Bulletin deleted successfully.",
            )

        except Exception as exc:
            application_logger.exception(
                "Error deleting bulletin: %s",
                exc,
            )

            return CustomResponse.errorResponse(
                "Unable to delete bulletin."
            )



