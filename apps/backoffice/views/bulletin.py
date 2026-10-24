import json
import uuid

from django.db import IntegrityError, transaction
from django.db.models import Prefetch
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.bulletin.models import BulletinCategory, Bulletin, BulletinAttachment
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

            # ----------------------------------------------------------
            # BANNER
            # ----------------------------------------------------------

            banner_label = request.data.get("banner_label")
            banner_headline = request.data.get("banner_headline")
            banner_sub_text = request.data.get("banner_sub_text")
            banner_color = request.data.get("banner_color")
            is_pinned = request.data.get("is_pinned", False)

            # ----------------------------------------------------------
            # VALIDATION
            # ----------------------------------------------------------

            if not category_id:
                return CustomResponse.errorResponse(
                    "Category is required."
                )

            if not title:
                return CustomResponse.errorResponse(
                    "Title is required."
                )

            # Category UUID validation
            try:
                category_id = uuid.UUID(str(category_id))
            except (ValueError, TypeError):
                return CustomResponse.errorResponse(
                    "Invalid category_id."
                )

            # Category belongs to current school
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
            # BANNER COLOR VALIDATION
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
                banner_sub_text=banner_sub_text,
                banner_color=(
                    banner_color
                    or Bulletin.BannerColor.INDIGO
                ),

                is_pinned=is_pinned,
                is_active=True,

                created_by=request.user,
                status=Bulletin.Status.DRAFT,
            )

            # ----------------------------------------------------------
            # CREATE ATTACHMENTS
            # ----------------------------------------------------------

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
                        "sub_text": bulletin.banner_sub_text,
                        "banner_color": bulletin.banner_color,
                    },

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
                        "attachments",
                        queryset=BulletinAttachment.objects.filter(
                            is_active=True
                        ).order_by("-created_at"),
                    )
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
                    title__icontains=search
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

            bulletins = bulletins.order_by(
                "-is_pinned",
                "-created_at",
            )

            data = []

            for bulletin in bulletins:
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
                    "status": bulletin.status,
                })

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

            # ----------------------------------------------------------
            # CATEGORY
            # ----------------------------------------------------------

            category_id = request.data.get("category_id")

            if category_id:
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

            # ----------------------------------------------------------
            # CONTENT
            # ----------------------------------------------------------

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

            # ----------------------------------------------------------
            # BANNER
            # ----------------------------------------------------------

            if "banner_label" in request.data:
                bulletin.banner_label = request.data.get(
                    "banner_label"
                )

            if "banner_headline" in request.data:
                bulletin.banner_headline = request.data.get(
                    "banner_headline"
                )

            if "banner_sub_text" in request.data:
                bulletin.banner_sub_text = request.data.get(
                    "banner_sub_text"
                )

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
                        f"Invalid banner_color. "
                        f"Allowed values: {', '.join(valid_colors)}"
                    )

                bulletin.banner_color = banner_color

            # ----------------------------------------------------------
            # PINNED
            # ----------------------------------------------------------

            if "is_pinned" in request.data:
                bulletin.is_pinned = request.data.get(
                    "is_pinned"
                )

            bulletin.updated_by = request.user
            if "status" in request.data:
                bulletin.status = request.data.get("status")



            bulletin.save()

            # ----------------------------------------------------------
            # REMOVE ATTACHMENTS
            # ----------------------------------------------------------

            remove_attachment_ids = request.data.get(
                "remove_attachment_ids"
            )

            if remove_attachment_ids:
                if isinstance(remove_attachment_ids, str):
                    remove_attachment_ids = [
                        item.strip()
                        for item in remove_attachment_ids.split(",")
                        if item.strip()
                    ]

                BulletinAttachment.objects.filter(
                    id__in=remove_attachment_ids,
                    bulletin=bulletin,
                    is_active=True,
                ).update(
                    is_active=False,
                    updated_by=request.user,
                )

            # ----------------------------------------------------------
            # ADD NEW ATTACHMENTS
            # ----------------------------------------------------------

            attachments = request.FILES.getlist(
                "attachments"
            )

            for file in attachments:
                BulletinAttachment.objects.create(
                    bulletin=bulletin,
                    name=file.name,

                    # Replace with actual S3 / MinIO URL.
                    pdf=file.name,

                    is_active=True,
                    created_by=request.user,
                )

            application_logger.info(
                "Bulletin updated successfully. "
                "bulletin_id=%s school_id=%s",
                bulletin.id,
                school.id,
            )

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



