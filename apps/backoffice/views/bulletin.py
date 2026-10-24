import uuid

from django.db import IntegrityError
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.bulletin.models import BulletinCategory, Bulletin
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
    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "bulletin.create"

    def post(self, request):
        try:
            school = request.school

            # =========================================================
            # REQUEST DATA
            # =========================================================

            category_id = request.data.get(
                "category_id"
            )

            name = request.data.get("name")
            summary = request.data.get("summary")
            description = request.data.get(
                "description"
            )

            # =========================================================
            # VALIDATE CATEGORY ID
            # =========================================================

            if not category_id:
                return CustomResponse.errorResponse(
                    description="category_id is required."
                )

            try:
                category_uuid = uuid.UUID(
                    str(category_id)
                )

            except (ValueError, TypeError):
                return CustomResponse.errorResponse(
                    description="Invalid category_id."
                )

            # =========================================================
            # VALIDATE NAME
            # =========================================================

            if not name:
                return CustomResponse.errorResponse(
                    description="name is required."
                )

            name = str(name).strip()

            if not name:
                return CustomResponse.errorResponse(
                    description="name cannot be empty."
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
            # CREATE BULLETIN
            # =========================================================

            bulletin = Bulletin.objects.create(
                school=school,
                category=category,
                name=name,
                summary=(
                    str(summary).strip()
                    if summary
                    else None
                ),
                description=(
                    str(description).strip()
                    if description
                    else None
                ),
                is_active=True,
                created_by=request.user,
            )

            application_logger.info(
                "Bulletin created successfully. "
                "bulletin_id=%s category_id=%s "
                "school_id=%s created_by=%s",
                bulletin.id,
                category.id,
                school.id,
                request.user.id,
            )

            # =========================================================
            # RESPONSE
            # =========================================================

            data = {
                "id": str(bulletin.id),

                "category": {
                    "id": str(
                        bulletin.category_id
                    ),
                    "name": (
                        bulletin.category.name
                    ),
                },

                "name": bulletin.name,

                "summary": bulletin.summary,

                "description": bulletin.description,

                "is_active": bulletin.is_active,
            }

            return CustomResponse.successResponse(
                data=data,
                description=(
                    "Bulletin created successfully."
                ),
            )

        except IntegrityError:

            application_logger.exception(
                "Integrity error while creating bulletin."
            )

            return CustomResponse.errorResponse(
                description=(
                    "Unable to create bulletin."
                )
            )

        except Exception as e:

            application_logger.exception(
                "Error creating bulletin. error=%s",
                str(e),
            )

            return CustomResponse.errorResponse(
                description=(
                    "Failed to create bulletin."
                )
            )

class BulletinListAPIView(APIView):
    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "bulletin.view"

    def get(self, request):
        try:
            school = request.school

            category_id = request.query_params.get(
                "category_id"
            )

            search = request.query_params.get(
                "search"
            )

            # =========================================================
            # BULLETINS
            # =========================================================

            bulletins = (
                Bulletin.objects
                .filter(
                    school=school,
                    is_active=True,
                )
                .select_related("category")
                .order_by("-created_at")
            )

            # =========================================================
            # CATEGORY FILTER
            # =========================================================

            if category_id:

                try:
                    category_uuid = uuid.UUID(
                        str(category_id)
                    )

                except (ValueError, TypeError):
                    return CustomResponse.errorResponse(
                        description=(
                            "Invalid category_id."
                        )
                    )

                bulletins = bulletins.filter(
                    category_id=category_uuid
                )

            # =========================================================
            # SEARCH
            # =========================================================

            if search:

                search = search.strip()

                if search:

                    bulletins = bulletins.filter(
                        name__icontains=search
                    )

            # =========================================================
            # RESPONSE
            # =========================================================

            data = []

            for bulletin in bulletins:

                data.append(
                    {
                        "id": str(
                            bulletin.id
                        ),

                        "category": {
                            "id": str(
                                bulletin.category_id
                            ),

                            "name": (
                                bulletin.category.name
                            ),
                        },

                        "name": (
                            bulletin.name
                        ),

                        "summary": (
                            bulletin.summary
                        ),

                        "description": (
                            bulletin.description
                        ),

                        "is_active": (
                            bulletin.is_active
                        ),

                        "created_at": (
                            bulletin.created_at
                            if bulletin.created_at
                            else None
                        ),
                    }
                )

            application_logger.info(
                "Bulletins fetched successfully. "
                "school_id=%s count=%s",
                school.id,
                len(data),
            )

            return CustomResponse.successResponse(
                data=data,
                description=(
                    "Bulletins fetched successfully."
                ),
            )

        except Exception as e:

            application_logger.exception(
                "Error fetching bulletins. error=%s",
                str(e),
            )

            return CustomResponse.errorResponse(
                description=(
                    "Failed to fetch bulletins."
                )
            )

class BulletinUpdateAPIView(APIView):
    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "bulletin.update"

    def put(self, request, bulletin_id):
        try:
            school = request.school

            # =========================================================
            # VALIDATE UUID
            # =========================================================

            try:
                bulletin_uuid = uuid.UUID(
                    str(bulletin_id)
                )

            except (ValueError, TypeError):
                return CustomResponse.errorResponse(
                    description="Invalid bulletin_id."
                )

            # =========================================================
            # GET BULLETIN
            # =========================================================

            bulletin = Bulletin.objects.filter(
                id=bulletin_uuid,
                school=school,
                is_active=True,
            ).first()

            if not bulletin:
                return CustomResponse.errorResponse(
                    description="Bulletin not found."
                )

            update_fields = []

            # =========================================================
            # CATEGORY
            # =========================================================

            category_id = request.data.get(
                "category_id"
            )

            if category_id is not None:

                try:
                    category_uuid = uuid.UUID(
                        str(category_id)
                    )

                except (ValueError, TypeError):
                    return CustomResponse.errorResponse(
                        description=(
                            "Invalid category_id."
                        )
                    )

                category = (
                    BulletinCategory.objects.filter(
                        id=category_uuid,
                        school=school,
                        is_active=True,
                    ).first()
                )

                if not category:
                    return CustomResponse.errorResponse(
                        description=(
                            "Bulletin category not found."
                        )
                    )

                bulletin.category = category

                update_fields.append(
                    "category"
                )

            # =========================================================
            # NAME
            # =========================================================

            name = request.data.get("name")

            if name is not None:

                name = str(name).strip()

                if not name:
                    return CustomResponse.errorResponse(
                        description=(
                            "name cannot be empty."
                        )
                    )

                bulletin.name = name

                update_fields.append("name")

            # =========================================================
            # SUMMARY
            # =========================================================

            if "summary" in request.data:

                summary = request.data.get(
                    "summary"
                )

                bulletin.summary = (
                    str(summary).strip()
                    if summary
                    else None
                )

                update_fields.append(
                    "summary"
                )

            # =========================================================
            # DESCRIPTION
            # =========================================================

            if "description" in request.data:

                description = request.data.get(
                    "description"
                )

                bulletin.description = (
                    str(description).strip()
                    if description
                    else None
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

            bulletin.updated_by = request.user

            update_fields.extend(
                [
                    "updated_by",
                    "updated_at",
                ]
            )

            bulletin.save(
                update_fields=update_fields
            )

            application_logger.info(
                "Bulletin updated successfully. "
                "bulletin_id=%s school_id=%s updated_by=%s",
                bulletin.id,
                school.id,
                request.user.id,
            )

            # =========================================================
            # RESPONSE
            # =========================================================

            bulletin.refresh_from_db()

            bulletin = (
                Bulletin.objects
                .filter(id=bulletin.id)
                .select_related("category")
                .first()
            )

            data = {
                "id": str(
                    bulletin.id
                ),

                "category": {
                    "id": str(
                        bulletin.category_id
                    ),

                    "name": (
                        bulletin.category.name
                    ),
                },

                "name": bulletin.name,

                "summary": (
                    bulletin.summary
                ),

                "description": (
                    bulletin.description
                ),

                "is_active": (
                    bulletin.is_active
                ),
            }

            return CustomResponse.successResponse(
                data=data,
                description=(
                    "Bulletin updated successfully."
                ),
            )

        except Exception as e:

            application_logger.exception(
                "Error updating bulletin. "
                "bulletin_id=%s error=%s",
                bulletin_id,
                str(e),
            )

            return CustomResponse.errorResponse(
                description=(
                    "Failed to update bulletin."
                )
            )

class BulletinDeleteAPIView(APIView):
    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "bulletin.delete"

    def delete(self, request, bulletin_id):
        try:
            school = request.school

            # =========================================================
            # VALIDATE UUID
            # =========================================================

            try:
                bulletin_uuid = uuid.UUID(
                    str(bulletin_id)
                )

            except (ValueError, TypeError):
                return CustomResponse.errorResponse(
                    description="Invalid bulletin_id."
                )

            # =========================================================
            # GET BULLETIN
            # =========================================================

            bulletin = Bulletin.objects.filter(
                id=bulletin_uuid,
                school=school,
                is_active=True,
            ).first()

            if not bulletin:
                return CustomResponse.errorResponse(
                    description="Bulletin not found."
                )

            # =========================================================
            # SOFT DELETE
            # =========================================================

            bulletin.is_active = False
            bulletin.updated_by = request.user

            bulletin.save(
                update_fields=[
                    "is_active",
                    "updated_by",
                    "updated_at",
                ]
            )

            application_logger.info(
                "Bulletin deleted successfully. "
                "bulletin_id=%s school_id=%s deleted_by=%s",
                bulletin.id,
                school.id,
                request.user.id,
            )

            return CustomResponse.successResponse(
                data={
                    "id": str(
                        bulletin.id
                    ),
                },
                description=(
                    "Bulletin deleted successfully."
                ),
            )

        except Exception as e:

            application_logger.exception(
                "Error deleting bulletin. "
                "bulletin_id=%s error=%s",
                bulletin_id,
                str(e),
            )

            return CustomResponse.errorResponse(
                description=(
                    "Failed to delete bulletin."
                )
            )

