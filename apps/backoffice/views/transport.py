from django.db import transaction
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.school.models.school import Branch
from apps.transport.models import Vehicle, VehicleDocument
from shared.mixins import CustomResponse
from shared.permissions import HasPermission
from shared.utils.logger import application_logger, audit_logger


class CreateVehicleAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "transport.vehicle.create"

    def post(self, request):

        school = request.school

        vehicle_number = request.data.get("vehicle_number")

        application_logger.info(
            "vehicle_create_requested",
            requested_by=str(request.user.id),
            school_id=str(school.id) if school else None,
            vehicle_number=vehicle_number,
        )

        if school is None:

            application_logger.warning(
                "vehicle_create_failed",
                requested_by=str(request.user.id),
                reason="school_not_found",
            )

            return CustomResponse.errorResponse(
                description="School not found."
            )

        required_fields = [
            "vehicle_number",
            "registration_number",
            "vehicle_type",
            "capacity",
            "manufacturer",
            "model",
            "status",
        ]

        for field in required_fields:

            if request.data.get(field) in [None, ""]:

                application_logger.warning(
                    "vehicle_create_failed",
                    requested_by=str(request.user.id),
                    school_id=str(school.id),
                    field=field,
                    reason="required_field_missing",
                )

                return CustomResponse.errorResponse(
                    description=f"{field} is required."
                )

        vehicle_type = request.data.get("vehicle_type")

        if vehicle_type not in Vehicle.VehicleType.values:

            application_logger.warning(
                "vehicle_create_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                vehicle_type=vehicle_type,
                reason="invalid_vehicle_type",
            )

            return CustomResponse.errorResponse(
                description="Invalid vehicle type."
            )

        status = request.data.get("status")

        if status not in Vehicle.Status.values:

            application_logger.warning(
                "vehicle_create_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                status=status,
                reason="invalid_status",
            )

            return CustomResponse.errorResponse(
                description="Invalid status."
            )

        if Vehicle.objects.filter(
            school=school,
            vehicle_number__iexact=vehicle_number.strip(),
        ).exists():

            application_logger.warning(
                "vehicle_create_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                vehicle_number=vehicle_number,
                reason="vehicle_already_exists",
            )

            return CustomResponse.errorResponse(
                description="Vehicle already exists."
            )

        branch = None

        branch_id = request.data.get("branch_id")

        if branch_id:

            branch = Branch.objects.filter(
                id=branch_id,
                school=school,
            ).first()

            if branch is None:

                application_logger.warning(
                    "vehicle_create_failed",
                    requested_by=str(request.user.id),
                    school_id=str(school.id),
                    branch_id=branch_id,
                    reason="branch_not_found",
                )

                return CustomResponse.errorResponse(
                    description="Branch not found."
                )

        try:

            with transaction.atomic():

                vehicle = Vehicle.objects.create(
                    school=school,
                    branch=branch,
                    vehicle_number=vehicle_number.strip(),
                    registration_number=request.data.get("registration_number").strip(),
                    vehicle_type=vehicle_type,
                    capacity=request.data.get("capacity"),
                    manufacturer=request.data.get("manufacturer").strip(),
                    model=request.data.get("model").strip(),
                    chassis_number=request.data.get("chassis_number"),
                    engine_number=request.data.get("engine_number"),
                    speed_limit=request.data.get("speed_limit"),
                    camera_installed=request.data.get("camera_installed", False),
                    panic_button=request.data.get("panic_button", False),
                    rfid_reader=request.data.get("rfid_reader", False),
                    status=status,
                    remarks=request.data.get("remarks"),
                )

        except Exception as e:

            application_logger.exception(
                "vehicle_create_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                vehicle_number=vehicle_number,
                reason="vehicle_creation_failed",
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description=str(e)
            )

        audit_logger.info(
            "vehicle_created",
            requested_by=str(request.user.id),
            school_id=str(school.id),
            vehicle_id=str(vehicle.id),
            vehicle_number=vehicle.vehicle_number,
        )

        return CustomResponse.successResponse(
            description="Vehicle created successfully.",
            data={
                "id": str(vehicle.id),
                "vehicle_number": vehicle.vehicle_number,
                "registration_number": vehicle.registration_number,
                "vehicle_type": vehicle.vehicle_type,
                "vehicle_type_display": vehicle.get_vehicle_type_display(),
                "capacity": vehicle.capacity,
                "manufacturer": vehicle.manufacturer,
                "model": vehicle.model,
                "status": vehicle.status,
                "status_display": vehicle.get_status_display(),
            },
        )


class VehicleListAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "transport.vehicle.view"

    def get(self, request):

        school = request.school
        search = request.GET.get("search", "").strip()
        vehicle_type = request.GET.get("vehicle_type")
        status = request.GET.get("status")
        branch_id = request.GET.get("branch_id")

        application_logger.info(
            "vehicle_list_requested",
            requested_by=str(request.user.id),
            school_id=str(school.id) if school else None,
            search=search,
            vehicle_type=vehicle_type,
            status=status,
            branch_id=branch_id,
        )

        if school is None:
            application_logger.warning(
                "vehicle_list_failed",
                requested_by=str(request.user.id),
                reason="school_not_found",
            )

            return CustomResponse.errorResponse(
                description="School not found."
            )

        try:

            queryset = Vehicle.objects.select_related(
                "branch",
            ).filter(
                school=school,
            )

            if search:
                queryset = queryset.filter(
                    Q(vehicle_number__icontains=search)
                    | Q(registration_number__icontains=search)
                    | Q(manufacturer__icontains=search)
                    | Q(model__icontains=search)
                )

            if vehicle_type:

                if vehicle_type not in Vehicle.VehicleType.values:
                    application_logger.warning(
                        "vehicle_list_failed",
                        requested_by=str(request.user.id),
                        school_id=str(school.id),
                        vehicle_type=vehicle_type,
                        reason="invalid_vehicle_type",
                    )

                    return CustomResponse.errorResponse(
                        description="Invalid vehicle type."
                    )

                queryset = queryset.filter(
                    vehicle_type=vehicle_type
                )

            if status:

                if status not in Vehicle.Status.values:
                    application_logger.warning(
                        "vehicle_list_failed",
                        requested_by=str(request.user.id),
                        school_id=str(school.id),
                        status=status,
                        reason="invalid_status",
                    )

                    return CustomResponse.errorResponse(
                        description="Invalid status."
                    )

                queryset = queryset.filter(
                    status=status
                )

            if branch_id:
                queryset = queryset.filter(
                    branch_id=branch_id
                )

            queryset = queryset.order_by("vehicle_number")

            data = []

            for vehicle in queryset:
                data.append(
                    {
                        "id": str(vehicle.id),
                        "vehicle_number": vehicle.vehicle_number,
                        "registration_number": vehicle.registration_number,
                        "vehicle_type": vehicle.vehicle_type,
                        "vehicle_type_display": vehicle.get_vehicle_type_display(),
                        "capacity": vehicle.capacity,
                        "manufacturer": vehicle.manufacturer,
                        "model": vehicle.model,
                        "speed_limit": vehicle.speed_limit,
                        "camera_installed": vehicle.camera_installed,
                        "panic_button": vehicle.panic_button,
                        "rfid_reader": vehicle.rfid_reader,
                        "status": vehicle.status,
                        "status_display": vehicle.get_status_display(),
                        "branch": (
                            {
                                "id": str(vehicle.branch.id),
                                "name": vehicle.branch.name,
                            }
                            if vehicle.branch
                            else None
                        ),
                        "created_at": vehicle.created_at,
                        "updated_at": vehicle.updated_at,
                    }
                )

        except Exception as e:

            application_logger.exception(
                "vehicle_list_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                reason="vehicle_list_fetch_failed",
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description=str(e)
            )

        audit_logger.info(
            "vehicle_list_fetched",
            requested_by=str(request.user.id),
            school_id=str(school.id),
            returned_count=len(data),
        )

        return CustomResponse.successResponse(
            description="Vehicles fetched successfully.",
            data={
                "total": len(data),
                "vehicles": data,
            },
        )


class UpdateVehicleAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "transport.vehicle.update"

    def put(self, request, vehicle_id):

        school = request.school

        application_logger.info(
            "vehicle_update_requested",
            requested_by=str(request.user.id),
            school_id=str(school.id) if school else None,
            vehicle_id=str(vehicle_id),
        )

        if school is None:
            application_logger.warning(
                "vehicle_update_failed",
                requested_by=str(request.user.id),
                vehicle_id=str(vehicle_id),
                reason="school_not_found",
            )

            return CustomResponse.errorResponse(
                description="School not found."
            )

        vehicle = Vehicle.objects.select_related(
            "branch",
        ).filter(
            id=vehicle_id,
            school=school,
        ).first()

        if vehicle is None:
            application_logger.warning(
                "vehicle_update_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                vehicle_id=str(vehicle_id),
                reason="vehicle_not_found",
            )

            return CustomResponse.errorResponse(
                description="Vehicle not found."
            )

        vehicle_number = request.data.get("vehicle_number")

        if vehicle_number not in [None, ""]:

            vehicle_number = vehicle_number.strip()

            if Vehicle.objects.filter(
                    school=school,
                    vehicle_number__iexact=vehicle_number,
            ).exclude(
                id=vehicle.id
            ).exists():
                application_logger.warning(
                    "vehicle_update_failed",
                    requested_by=str(request.user.id),
                    school_id=str(school.id),
                    vehicle_id=str(vehicle.id),
                    vehicle_number=vehicle_number,
                    reason="vehicle_number_already_exists",
                )

                return CustomResponse.errorResponse(
                    description="Vehicle number already exists."
                )

            vehicle.vehicle_number = vehicle_number

        registration_number = request.data.get("registration_number")

        if registration_number not in [None, ""]:

            registration_number = registration_number.strip()

            if Vehicle.objects.filter(
                    school=school,
                    registration_number__iexact=registration_number,
            ).exclude(
                id=vehicle.id
            ).exists():
                application_logger.warning(
                    "vehicle_update_failed",
                    requested_by=str(request.user.id),
                    school_id=str(school.id),
                    vehicle_id=str(vehicle.id),
                    registration_number=registration_number,
                    reason="registration_number_already_exists",
                )

                return CustomResponse.errorResponse(
                    description="Registration number already exists."
                )

            vehicle.registration_number = registration_number

        vehicle_type = request.data.get("vehicle_type")

        if vehicle_type:

            if vehicle_type not in Vehicle.VehicleType.values:
                application_logger.warning(
                    "vehicle_update_failed",
                    requested_by=str(request.user.id),
                    school_id=str(school.id),
                    vehicle_id=str(vehicle.id),
                    vehicle_type=vehicle_type,
                    reason="invalid_vehicle_type",
                )

                return CustomResponse.errorResponse(
                    description="Invalid vehicle type."
                )

            vehicle.vehicle_type = vehicle_type

        if request.data.get("capacity") not in [None, ""]:
            vehicle.capacity = request.data.get("capacity")

        if request.data.get("manufacturer") not in [None, ""]:
            vehicle.manufacturer = request.data.get("manufacturer").strip()

        if request.data.get("model") not in [None, ""]:
            vehicle.model = request.data.get("model").strip()

        if "chassis_number" in request.data:
            vehicle.chassis_number = request.data.get("chassis_number")

        if "engine_number" in request.data:
            vehicle.engine_number = request.data.get("engine_number")

        if "speed_limit" in request.data:
            vehicle.speed_limit = request.data.get("speed_limit")

        if "camera_installed" in request.data:
            vehicle.camera_installed = request.data.get("camera_installed")

        if "panic_button" in request.data:
            vehicle.panic_button = request.data.get("panic_button")

        if "rfid_reader" in request.data:
            vehicle.rfid_reader = request.data.get("rfid_reader")

        status = request.data.get("status")

        if status:

            if status not in Vehicle.Status.values:
                application_logger.warning(
                    "vehicle_update_failed",
                    requested_by=str(request.user.id),
                    school_id=str(school.id),
                    vehicle_id=str(vehicle.id),
                    status=status,
                    reason="invalid_status",
                )

                return CustomResponse.errorResponse(
                    description="Invalid status."
                )

            vehicle.status = status

        if "remarks" in request.data:
            vehicle.remarks = request.data.get("remarks")

        if "branch_id" in request.data:

            branch_id = request.data.get("branch_id")

            if branch_id:

                branch = Branch.objects.filter(
                    id=branch_id,
                    school=school,
                ).first()

                if branch is None:
                    application_logger.warning(
                        "vehicle_update_failed",
                        requested_by=str(request.user.id),
                        school_id=str(school.id),
                        vehicle_id=str(vehicle.id),
                        branch_id=branch_id,
                        reason="branch_not_found",
                    )

                    return CustomResponse.errorResponse(
                        description="Branch not found."
                    )

                vehicle.branch = branch

            else:

                vehicle.branch = None

        try:

            with transaction.atomic():

                vehicle.save()

        except Exception as e:

            application_logger.exception(
                "vehicle_update_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                vehicle_id=str(vehicle.id),
                reason="vehicle_update_failed",
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description=str(e)
            )

        audit_logger.info(
            "vehicle_updated",
            requested_by=str(request.user.id),
            school_id=str(school.id),
            vehicle_id=str(vehicle.id),
            vehicle_number=vehicle.vehicle_number,
        )

        return CustomResponse.successResponse(
            description="Vehicle updated successfully.",
            data={
                "id": str(vehicle.id),
                "vehicle_number": vehicle.vehicle_number,
                "registration_number": vehicle.registration_number,
                "vehicle_type": vehicle.vehicle_type,
                "vehicle_type_display": vehicle.get_vehicle_type_display(),
                "capacity": vehicle.capacity,
                "manufacturer": vehicle.manufacturer,
                "model": vehicle.model,
                "status": vehicle.status,
                "status_display": vehicle.get_status_display(),
            },
        )


class CreateVehicleDocumentAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "vehicle.document.create"

    def post(self, request):

        school = request.school
        vehicle_id = request.data.get("vehicle_id")
        document_type = request.data.get("document_type")

        application_logger.info(
            "vehicle_document_create_requested",
            requested_by=str(request.user.id),
            school_id=str(school.id) if school else None,
            vehicle_id=vehicle_id,
            document_type=document_type,
        )

        if school is None:

            application_logger.warning(
                "vehicle_document_create_failed",
                requested_by=str(request.user.id),
                reason="school_not_found",
            )

            return CustomResponse.errorResponse(
                description="School not found."
            )

        required_fields = [
            "vehicle_id",
            "document_type",
            "document_number",
        ]

        for field in required_fields:

            if request.data.get(field) in [None, ""]:

                application_logger.warning(
                    "vehicle_document_create_failed",
                    requested_by=str(request.user.id),
                    school_id=str(school.id),
                    vehicle_id=vehicle_id,
                    field=field,
                    reason="required_field_missing",
                )

                return CustomResponse.errorResponse(
                    description=f"{field} is required."
                )

        vehicle = Vehicle.objects.filter(
            id=vehicle_id,
            school=school,
        ).first()

        if vehicle is None:

            application_logger.warning(
                "vehicle_document_create_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                vehicle_id=vehicle_id,
                reason="vehicle_not_found",
            )

            return CustomResponse.errorResponse(
                description="Vehicle not found."
            )

        if document_type not in VehicleDocument.DocumentType.values:

            application_logger.warning(
                "vehicle_document_create_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                vehicle_id=str(vehicle.id),
                document_type=document_type,
                reason="invalid_document_type",
            )

            return CustomResponse.errorResponse(
                description="Invalid document type."
            )

        if VehicleDocument.objects.filter(
            vehicle=vehicle,
            document_type=document_type,
        ).exists():

            application_logger.warning(
                "vehicle_document_create_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                vehicle_id=str(vehicle.id),
                document_type=document_type,
                reason="document_already_exists",
            )

            return CustomResponse.errorResponse(
                description=f"{document_type.replace('_', ' ').title()} already exists."
            )

        issue_date = request.data.get("issue_date")
        expiry_date = request.data.get("expiry_date")

        if issue_date and expiry_date and issue_date > expiry_date:

            application_logger.warning(
                "vehicle_document_create_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                vehicle_id=str(vehicle.id),
                reason="invalid_date_range",
            )

            return CustomResponse.errorResponse(
                description="Expiry date must be greater than or equal to issue date."
            )

        try:

            with transaction.atomic():

                document = VehicleDocument.objects.create(
                    vehicle=vehicle,
                    document_type=document_type,
                    document_number=request.data.get("document_number").strip(),
                    issue_date=issue_date,
                    expiry_date=expiry_date,
                    issued_by=request.data.get("issued_by"),
                    document_file=request.data.get("document_file"),
                    remarks=request.data.get("remarks"),
                    status=request.data.get(
                        "status",
                        VehicleDocument.Status.ACTIVE,
                    ),
                )

        except Exception as e:

            application_logger.exception(
                "vehicle_document_create_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                vehicle_id=str(vehicle.id),
                document_type=document_type,
                reason="vehicle_document_creation_failed",
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description=str(e)
            )

        application_logger.info(
            "vehicle_document_created",
            requested_by=str(request.user.id),
            school_id=str(school.id),
            vehicle_id=str(vehicle.id),
            document_id=str(document.id),
            document_type=document.document_type,
        )

        return CustomResponse.successResponse(
            description="Vehicle document uploaded successfully.",
            data={
                "id": str(document.id),
                "vehicle_id": str(vehicle.id),
                "document_type": document.document_type,
                "document_number": document.document_number,
                "status": document.status,
            },
        )


class VehicleDocumentListAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "vehicle.document.view"

    def get(self, request):

        school = request.school
        vehicle_id = request.GET.get("vehicle_id")

        application_logger.info(
            "vehicle_document_list_requested",
            requested_by=str(request.user.id),
            school_id=str(school.id) if school else None,
            vehicle_id=vehicle_id,
        )

        if school is None:

            application_logger.warning(
                "vehicle_document_list_failed",
                requested_by=str(request.user.id),
                vehicle_id=vehicle_id,
                reason="school_not_found",
            )

            return CustomResponse.errorResponse(
                description="School not found."
            )

        if not vehicle_id:

            application_logger.warning(
                "vehicle_document_list_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                reason="vehicle_id_required",
            )

            return CustomResponse.errorResponse(
                description="vehicle_id is required."
            )

        try:

            vehicle = Vehicle.objects.filter(
                id=vehicle_id,
                school=school,
            ).first()

            if vehicle is None:

                application_logger.warning(
                    "vehicle_document_list_failed",
                    requested_by=str(request.user.id),
                    school_id=str(school.id),
                    vehicle_id=vehicle_id,
                    reason="vehicle_not_found",
                )

                return CustomResponse.errorResponse(
                    description="Vehicle not found."
                )

            documents = VehicleDocument.objects.filter(
                vehicle=vehicle,
            ).order_by(
                "document_type"
            )

            data = []

            for document in documents:

                data.append({
                    "id": str(document.id),
                    "document_type": document.document_type,
                    "document_type_display": document.get_document_type_display(),
                    "document_number": document.document_number,
                    "issue_date": document.issue_date,
                    "expiry_date": document.expiry_date,
                    "issued_by": document.issued_by,
                    "document_file": (
                        document.document_file.url
                        if document.document_file
                        else None
                    ),
                    "remarks": document.remarks,
                    "status": document.status,
                    "status_display": document.get_status_display(),
                    "created_at": document.created_at,
                    "updated_at": document.updated_at,
                })

        except Exception as e:

            application_logger.exception(
                "vehicle_document_list_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                vehicle_id=vehicle_id,
                reason="vehicle_document_list_fetch_failed",
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description=str(e)
            )

        application_logger.info(
            "vehicle_document_list_fetched",
            requested_by=str(request.user.id),
            school_id=str(school.id),
            vehicle_id=str(vehicle.id),
            returned_count=len(data),
        )

        return CustomResponse.successResponse(
            description="Vehicle documents fetched successfully.",
            data={
                "vehicle_id": str(vehicle.id),
                "vehicle_number": vehicle.vehicle_number,
                "documents": data,
            },
        )


class UpdateVehicleDocumentAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "vehicle.document.update"

    def put(self, request, document_id):

        school = request.school

        application_logger.info(
            "vehicle_document_update_requested",
            requested_by=str(request.user.id),
            school_id=str(school.id) if school else None,
            document_id=str(document_id),
        )

        if school is None:

            application_logger.warning(
                "vehicle_document_update_failed",
                requested_by=str(request.user.id),
                document_id=str(document_id),
                reason="school_not_found",
            )

            return CustomResponse.errorResponse(
                description="School not found."
            )

        document = VehicleDocument.objects.select_related(
            "vehicle"
        ).filter(
            id=document_id,
            vehicle__school=school,
        ).first()

        if document is None:

            application_logger.warning(
                "vehicle_document_update_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                document_id=str(document_id),
                reason="document_not_found",
            )

            return CustomResponse.errorResponse(
                description="Vehicle document not found."
            )

        document_type = request.data.get("document_type")

        if document_type:

            if document_type not in VehicleDocument.DocumentType.values:

                application_logger.warning(
                    "vehicle_document_update_failed",
                    requested_by=str(request.user.id),
                    school_id=str(school.id),
                    document_id=str(document.id),
                    vehicle_id=str(document.vehicle.id),
                    document_type=document_type,
                    reason="invalid_document_type",
                )

                return CustomResponse.errorResponse(
                    description="Invalid document type."
                )

            if VehicleDocument.objects.filter(
                vehicle=document.vehicle,
                document_type=document_type,
            ).exclude(
                id=document.id
            ).exists():

                application_logger.warning(
                    "vehicle_document_update_failed",
                    requested_by=str(request.user.id),
                    school_id=str(school.id),
                    document_id=str(document.id),
                    vehicle_id=str(document.vehicle.id),
                    document_type=document_type,
                    reason="document_type_already_exists",
                )

                return CustomResponse.errorResponse(
                    description=f"{document_type.replace('_', ' ').title()} already exists."
                )

            document.document_type = document_type

        issue_date = request.data.get(
            "issue_date",
            document.issue_date,
        )

        expiry_date = request.data.get(
            "expiry_date",
            document.expiry_date,
        )

        if issue_date and expiry_date and issue_date > expiry_date:

            application_logger.warning(
                "vehicle_document_update_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                document_id=str(document.id),
                vehicle_id=str(document.vehicle.id),
                reason="invalid_date_range",
            )

            return CustomResponse.errorResponse(
                description="Expiry date must be greater than or equal to issue date."
            )

        if request.data.get("document_number") not in [None, ""]:
            document.document_number = request.data.get(
                "document_number"
            ).strip()

        if "issue_date" in request.data:
            document.issue_date = request.data.get("issue_date") or None

        if "expiry_date" in request.data:
            document.expiry_date = request.data.get("expiry_date") or None

        if "issued_by" in request.data:
            document.issued_by = request.data.get("issued_by")

        if "document_file" in request.data:
            document.document_file = request.data.get("document_file")

        if "remarks" in request.data:
            document.remarks = request.data.get("remarks")

        if "status" in request.data:
            document.status = request.data.get("status")

        try:

            with transaction.atomic():

                document.save()

        except Exception as e:

            application_logger.exception(
                "vehicle_document_update_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                document_id=str(document.id),
                vehicle_id=str(document.vehicle.id),
                reason="vehicle_document_update_failed",
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description=str(e)
            )

        application_logger.info(
            "vehicle_document_updated",
            requested_by=str(request.user.id),
            school_id=str(school.id),
            document_id=str(document.id),
            vehicle_id=str(document.vehicle.id),
            document_type=document.document_type,
        )

        return CustomResponse.successResponse(
            description="Vehicle document updated successfully.",
            data={
                "id": str(document.id),
                "vehicle_id": str(document.vehicle.id),
                "document_type": document.document_type,
                "document_number": document.document_number,
                "issue_date": document.issue_date,
                "expiry_date": document.expiry_date,
                "issued_by": document.issued_by,
                "document_file": (
                    document.document_file.url
                    if document.document_file
                    else None
                ),
                "remarks": document.remarks,
                "status": document.status,
            },
        )