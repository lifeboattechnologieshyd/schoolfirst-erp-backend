from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.school.models.school import Branch, Staff, Student, AcademicYear
from apps.transport.models import Vehicle, VehicleDocument, Route, RouteStop, VehicleAssignment, StudentTransport, Stop, \
    Trip, TripAttendance, LiveLocation, TripEvent
from shared.mixins import CustomResponse
from shared.permissions import HasPermission
from shared.utils.logger import application_logger, audit_logger
from shared.utils.transport import update_live_location


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
                        # "vehicle_type_display": vehicle.get_vehicle_type_display(),
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

class CreateRouteAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "route.create"

    def post(self, request):

        school = request.school
        branch_id = request.data.get("branch_id")
        route_code = request.data.get("route_code")

        application_logger.info(
            "route_create_requested",
            requested_by=str(request.user.id),
            school_id=str(school.id) if school else None,
            branch_id=branch_id,
            route_code=route_code,
        )

        if school is None:

            application_logger.warning(
                "route_create_failed",
                requested_by=str(request.user.id),
                reason="school_not_found",
            )

            return CustomResponse.errorResponse(
                description="School not found."
            )

        required_fields = [
            "route_name",
            "route_code",
            "source",
            "destination",
            "shift",
        ]

        for field in required_fields:

            if request.data.get(field) in [None, ""]:

                application_logger.warning(
                    "route_create_failed",
                    requested_by=str(request.user.id),
                    school_id=str(school.id),
                    field=field,
                    reason="required_field_missing",
                )

                return CustomResponse.errorResponse(
                    description=f"{field} is required."
                )

        branch = None

        if branch_id:

            branch = Branch.objects.filter(
                id=branch_id,
                school=school,
            ).first()

            if branch is None:

                application_logger.warning(
                    "route_create_failed",
                    requested_by=str(request.user.id),
                    school_id=str(school.id),
                    branch_id=branch_id,
                    reason="branch_not_found",
                )

                return CustomResponse.errorResponse(
                    description="Branch not found."
                )

        shift = request.data.get("shift")

        if shift not in Route.Shift.values:

            application_logger.warning(
                "route_create_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                shift=shift,
                reason="invalid_shift",
            )

            return CustomResponse.errorResponse(
                description="Invalid shift."
            )

        if Route.objects.filter(
            school=school,
            route_code=route_code,
        ).exists():

            application_logger.warning(
                "route_create_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                route_code=route_code,
                reason="route_code_already_exists",
            )

            return CustomResponse.errorResponse(
                description="Route code already exists."
            )

        try:

            with transaction.atomic():

                route = Route.objects.create(
                    school=school,
                    branch=branch,
                    route_name=request.data.get("route_name").strip(),
                    route_code=route_code.strip(),
                    source=request.data.get("source").strip(),
                    destination=request.data.get("destination").strip(),
                    total_distance=request.data.get("total_distance"),
                    estimated_duration=request.data.get("estimated_duration"),
                    shift=shift,
                    status=request.data.get(
                        "status",
                        Route.Status.ACTIVE,
                    ),
                )

        except Exception as e:

            application_logger.exception(
                "route_create_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                route_code=route_code,
                reason="route_creation_failed",
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description=str(e)
            )

        application_logger.info(
            "route_created",
            requested_by=str(request.user.id),
            school_id=str(school.id),
            route_id=str(route.id),
            route_code=route.route_code,
        )

        return CustomResponse.successResponse(
            description="Route created successfully.",
            data={
                "id": str(route.id),
                "route_name": route.route_name,
                "route_code": route.route_code,
                "branch": (
                    {
                        "id": str(branch.id),
                        "name": branch.name,
                    }
                    if branch
                    else None
                ),
                "source": route.source,
                "destination": route.destination,
                "shift": route.shift,
                "status": route.status,
            },
        )


class RouteListAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "route.view"

    def get(self, request):

        school = request.school

        branch_id = request.GET.get("branch_id")
        shift = request.GET.get("shift")
        status = request.GET.get("status")
        search = request.GET.get("search", "").strip()

        application_logger.info(
            "route_list_requested",
            requested_by=str(request.user.id),
            school_id=str(school.id) if school else None,
            branch_id=branch_id,
            shift=shift,
            status=status,
            search=search,
        )

        if school is None:

            application_logger.warning(
                "route_list_failed",
                requested_by=str(request.user.id),
                reason="school_not_found",
            )

            return CustomResponse.errorResponse(
                description="School not found."
            )

        try:

            routes = Route.objects.select_related(
                "branch",
            ).filter(
                school=school,
            )

            if branch_id:

                routes = routes.filter(
                    branch_id=branch_id,
                )

            if shift:

                routes = routes.filter(
                    shift=shift,
                )

            if status:

                routes = routes.filter(
                    status=status,
                )

            if search:

                routes = routes.filter(
                    Q(route_name__icontains=search)
                    | Q(route_code__icontains=search)
                    | Q(source__icontains=search)
                    | Q(destination__icontains=search)
                )

            routes = routes.order_by(
                "route_name",
            )

            data = []

            for route in routes:

                data.append({
                    "id": str(route.id),
                    "route_name": route.route_name,
                    "route_code": route.route_code,
                    "branch": (
                        {
                            "id": str(route.branch.id),
                            "name": route.branch.name,
                        }
                        if route.branch
                        else None
                    ),
                    "source": route.source,
                    "destination": route.destination,
                    "total_distance": route.total_distance,
                    "estimated_duration": route.estimated_duration,
                    "shift": route.shift,
                    "shift_display": route.get_shift_display(),
                    "status": route.status,
                    "status_display": route.get_status_display(),
                    "created_at": route.created_at,
                    "updated_at": route.updated_at,
                })

        except Exception as e:

            application_logger.exception(
                "route_list_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description=str(e),
            )

        application_logger.info(
            "route_list_fetched",
            requested_by=str(request.user.id),
            school_id=str(school.id),
            returned_count=len(data),
        )

        return CustomResponse.successResponse(
            description="Routes fetched successfully.",
            total=len(data),
            data=data,
        )



class UpdateRouteAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "route.update"

    def put(self, request, route_id):

        school = request.school

        application_logger.info(
            "route_update_requested",
            requested_by=str(request.user.id),
            school_id=str(school.id) if school else None,
            route_id=str(route_id),
        )

        if school is None:

            application_logger.warning(
                "route_update_failed",
                requested_by=str(request.user.id),
                route_id=str(route_id),
                reason="school_not_found",
            )

            return CustomResponse.errorResponse(
                description="School not found."
            )

        route = Route.objects.filter(
            id=route_id,
            school=school,
        ).first()

        if route is None:

            application_logger.warning(
                "route_update_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                route_id=str(route_id),
                reason="route_not_found",
            )

            return CustomResponse.errorResponse(
                description="Route not found."
            )

        branch = route.branch

        if "branch_id" in request.data:

            branch_id = request.data.get("branch_id")

            if branch_id:

                branch = Branch.objects.filter(
                    id=branch_id,
                    school=school,
                ).first()

                if branch is None:

                    application_logger.warning(
                        "route_update_failed",
                        requested_by=str(request.user.id),
                        school_id=str(school.id),
                        route_id=str(route.id),
                        branch_id=branch_id,
                        reason="branch_not_found",
                    )

                    return CustomResponse.errorResponse(
                        description="Branch not found."
                    )

            else:

                branch = None

        route_code = request.data.get("route_code")

        if route_code:

            if Route.objects.filter(
                school=school,
                route_code=route_code,
            ).exclude(
                id=route.id,
            ).exists():

                application_logger.warning(
                    "route_update_failed",
                    requested_by=str(request.user.id),
                    school_id=str(school.id),
                    route_id=str(route.id),
                    route_code=route_code,
                    reason="route_code_already_exists",
                )

                return CustomResponse.errorResponse(
                    description="Route code already exists."
                )

            route.route_code = route_code.strip()

        shift = request.data.get("shift")

        if shift:

            if shift not in Route.Shift.values:

                application_logger.warning(
                    "route_update_failed",
                    requested_by=str(request.user.id),
                    school_id=str(school.id),
                    route_id=str(route.id),
                    shift=shift,
                    reason="invalid_shift",
                )

                return CustomResponse.errorResponse(
                    description="Invalid shift."
                )

            route.shift = shift

        status = request.data.get("status")

        if status:

            if status not in Route.Status.values:

                application_logger.warning(
                    "route_update_failed",
                    requested_by=str(request.user.id),
                    school_id=str(school.id),
                    route_id=str(route.id),
                    status=status,
                    reason="invalid_status",
                )

                return CustomResponse.errorResponse(
                    description="Invalid status."
                )

            route.status = status

        if request.data.get("route_name") not in [None, ""]:
            route.route_name = request.data.get("route_name").strip()

        if request.data.get("source") not in [None, ""]:
            route.source = request.data.get("source").strip()

        if request.data.get("destination") not in [None, ""]:
            route.destination = request.data.get("destination").strip()

        if "total_distance" in request.data:
            route.total_distance = request.data.get("total_distance")

        if "estimated_duration" in request.data:
            route.estimated_duration = request.data.get("estimated_duration")

        route.branch = branch

        try:

            with transaction.atomic():

                route.save()

        except Exception as e:

            application_logger.exception(
                "route_update_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                route_id=str(route.id),
                reason="route_update_failed",
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description=str(e)
            )

        application_logger.info(
            "route_updated",
            requested_by=str(request.user.id),
            school_id=str(school.id),
            route_id=str(route.id),
            route_code=route.route_code,
        )

        return CustomResponse.successResponse(
            description="Route updated successfully.",
            data={
                "id": str(route.id),
                "route_name": route.route_name,
                "route_code": route.route_code,
                "branch": (
                    {
                        "id": str(route.branch.id),
                        "name": route.branch.name,
                    }
                    if route.branch
                    else None
                ),
                "source": route.source,
                "destination": route.destination,
                "total_distance": route.total_distance,
                "estimated_duration": route.estimated_duration,
                "shift": route.shift,
                "status": route.status,
            },
        )


class CreateRouteStopAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "route.stop.create"

    def post(self, request):

        school = request.school

        route_id = request.data.get("route_id")
        stop_id = request.data.get("stop_id")
        stop_order = request.data.get("stop_order")

        application_logger.info(
            "route_stop_create_requested",
            requested_by=str(request.user.id),
            school_id=str(school.id) if school else None,
            route_id=route_id,
            stop_id=stop_id,
        )

        if school is None:

            application_logger.warning(
                "route_stop_create_failed",
                requested_by=str(request.user.id),
                reason="school_not_found",
            )

            return CustomResponse.errorResponse(
                description="School not found."
            )

        required_fields = [
            "route_id",
            "stop_id",
            "stop_order",
        ]

        for field in required_fields:

            if request.data.get(field) in [None, ""]:

                application_logger.warning(
                    "route_stop_create_failed",
                    requested_by=str(request.user.id),
                    school_id=str(school.id),
                    field=field,
                    reason="required_field_missing",
                )

                return CustomResponse.errorResponse(
                    description=f"{field} is required."
                )

        route = Route.objects.filter(
            id=route_id,
            school=school,
        ).first()

        if route is None:

            application_logger.warning(
                "route_stop_create_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                route_id=route_id,
                reason="route_not_found",
            )

            return CustomResponse.errorResponse(
                description="Route not found."
            )

        stop = Stop.objects.filter(
            id=stop_id,
            school=school,
        ).first()

        if stop is None:

            application_logger.warning(
                "route_stop_create_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                stop_id=stop_id,
                reason="stop_not_found",
            )

            return CustomResponse.errorResponse(
                description="Stop not found."
            )

        if RouteStop.objects.filter(
            route=route,
            stop=stop,
        ).exists():

            application_logger.warning(
                "route_stop_create_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                route_id=str(route.id),
                stop_id=str(stop.id),
                reason="route_stop_already_exists",
            )

            return CustomResponse.errorResponse(
                description="Stop is already mapped to this route."
            )

        if RouteStop.objects.filter(
            route=route,
            stop_order=stop_order,
        ).exists():

            application_logger.warning(
                "route_stop_create_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                route_id=str(route.id),
                stop_order=stop_order,
                reason="stop_order_already_exists",
            )

            return CustomResponse.errorResponse(
                description="Stop order already exists for this route."
            )

        try:

            with transaction.atomic():

                route_stop = RouteStop.objects.create(
                    route=route,
                    stop=stop,
                    stop_order=stop_order,
                    pickup_time=request.data.get("pickup_time"),
                    drop_time=request.data.get("drop_time"),
                    distance_from_previous_stop=request.data.get(
                        "distance_from_previous_stop",
                        0,
                    ),
                    estimated_travel_time=request.data.get(
                        "estimated_travel_time",
                    ),
                )

        except Exception as e:

            application_logger.exception(
                "route_stop_create_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                route_id=str(route.id),
                stop_id=str(stop.id),
                reason="route_stop_creation_failed",
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description=str(e),
            )

        application_logger.info(
            "route_stop_created",
            requested_by=str(request.user.id),
            school_id=str(school.id),
            route_stop_id=str(route_stop.id),
            route_id=str(route.id),
            stop_id=str(stop.id),
            stop_order=route_stop.stop_order,
        )

        return CustomResponse.successResponse(
            description="Route stop created successfully.",
            data={
                "id": str(route_stop.id),
                "route_id": str(route.id),
                "route_name": route.route_name,
                "stop_id": str(stop.id),
                "stop_name": stop.stop_name,
                "stop_order": route_stop.stop_order,
                "pickup_time": route_stop.pickup_time,
                "drop_time": route_stop.drop_time,
            },
        )


class RouteStopListAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "route.stop.view"

    def get(self, request):

        school = request.school

        route_id = request.GET.get("route_id")
        search = request.GET.get("search", "").strip()

        application_logger.info(
            "route_stop_list_requested",
            requested_by=str(request.user.id),
            school_id=str(school.id) if school else None,
            route_id=route_id,
            search=search,
        )

        if school is None:

            application_logger.warning(
                "route_stop_list_failed",
                requested_by=str(request.user.id),
                reason="school_not_found",
            )

            return CustomResponse.errorResponse(
                description="School not found."
            )

        if not route_id:

            application_logger.warning(
                "route_stop_list_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                reason="route_id_required",
            )

            return CustomResponse.errorResponse(
                description="route_id is required."
            )

        try:

            route = Route.objects.filter(
                id=route_id,
                school=school,
            ).first()

            if route is None:

                application_logger.warning(
                    "route_stop_list_failed",
                    requested_by=str(request.user.id),
                    school_id=str(school.id),
                    route_id=route_id,
                    reason="route_not_found",
                )

                return CustomResponse.errorResponse(
                    description="Route not found."
                )

            route_stops = RouteStop.objects.select_related(
                "route",
                "stop",
            ).filter(
                route=route,
            )

            if search:

                route_stops = route_stops.filter(
                    Q(stop__stop_name__icontains=search)
                    | Q(stop__stop_code__icontains=search)
                    | Q(stop__address__icontains=search)
                )

            route_stops = route_stops.order_by(
                "stop_order",
            )

            data = []

            for route_stop in route_stops:

                data.append({
                    "id": str(route_stop.id),
                    "stop_order": route_stop.stop_order,
                    "pickup_time": route_stop.pickup_time,
                    "drop_time": route_stop.drop_time,
                    "distance_from_previous_stop": route_stop.distance_from_previous_stop,
                    "estimated_travel_time": route_stop.estimated_travel_time,
                    "stop": {
                        "id": str(route_stop.stop.id),
                        "stop_name": route_stop.stop.stop_name,
                        "stop_code": route_stop.stop.stop_code,
                        "latitude": route_stop.stop.latitude,
                        "longitude": route_stop.stop.longitude,
                        "address": route_stop.stop.address,
                    },
                })

        except Exception as e:

            application_logger.exception(
                "route_stop_list_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                route_id=route_id,
                reason="route_stop_fetch_failed",
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description=str(e),
            )

        application_logger.info(
            "route_stop_list_fetched",
            requested_by=str(request.user.id),
            school_id=str(school.id),
            route_id=str(route.id),
            returned_count=len(data),
        )

        return CustomResponse.successResponse(
            description="Route stops fetched successfully.",
            total=len(data),
            data={
                "route_id": str(route.id),
                "route_name": route.route_name,
                "route_code": route.route_code,
                "stops": data,
            },
        )


class UpdateRouteStopAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "route.stop.update"

    def put(self, request, route_stop_id):

        school = request.school

        application_logger.info(
            "route_stop_update_requested",
            requested_by=str(request.user.id),
            school_id=str(school.id) if school else None,
            route_stop_id=str(route_stop_id),
        )

        if school is None:

            application_logger.warning(
                "route_stop_update_failed",
                requested_by=str(request.user.id),
                route_stop_id=str(route_stop_id),
                reason="school_not_found",
            )

            return CustomResponse.errorResponse(
                description="School not found."
            )

        route_stop = RouteStop.objects.select_related(
            "route",
            "stop",
        ).filter(
            id=route_stop_id,
            route__school=school,
        ).first()

        if route_stop is None:

            application_logger.warning(
                "route_stop_update_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                route_stop_id=str(route_stop_id),
                reason="route_stop_not_found",
            )

            return CustomResponse.errorResponse(
                description="Route stop not found."
            )

        if "stop_id" in request.data:

            stop = Stop.objects.filter(
                id=request.data.get("stop_id"),
                school=school,
            ).first()

            if stop is None:

                application_logger.warning(
                    "route_stop_update_failed",
                    requested_by=str(request.user.id),
                    school_id=str(school.id),
                    route_stop_id=str(route_stop.id),
                    stop_id=request.data.get("stop_id"),
                    reason="stop_not_found",
                )

                return CustomResponse.errorResponse(
                    description="Stop not found."
                )

            if RouteStop.objects.filter(
                route=route_stop.route,
                stop=stop,
            ).exclude(
                id=route_stop.id,
            ).exists():

                application_logger.warning(
                    "route_stop_update_failed",
                    requested_by=str(request.user.id),
                    school_id=str(school.id),
                    route_stop_id=str(route_stop.id),
                    stop_id=str(stop.id),
                    reason="route_stop_already_exists",
                )

                return CustomResponse.errorResponse(
                    description="Stop is already mapped to this route."
                )

            route_stop.stop = stop

        if "stop_order" in request.data:

            stop_order = request.data.get("stop_order")

            if RouteStop.objects.filter(
                route=route_stop.route,
                stop_order=stop_order,
            ).exclude(
                id=route_stop.id,
            ).exists():

                application_logger.warning(
                    "route_stop_update_failed",
                    requested_by=str(request.user.id),
                    school_id=str(school.id),
                    route_stop_id=str(route_stop.id),
                    stop_order=stop_order,
                    reason="stop_order_already_exists",
                )

                return CustomResponse.errorResponse(
                    description="Stop order already exists for this route."
                )

            route_stop.stop_order = stop_order

        if "pickup_time" in request.data:
            route_stop.pickup_time = request.data.get("pickup_time") or None

        if "drop_time" in request.data:
            route_stop.drop_time = request.data.get("drop_time") or None

        if "distance_from_previous_stop" in request.data:
            route_stop.distance_from_previous_stop = request.data.get(
                "distance_from_previous_stop"
            )

        if "estimated_travel_time" in request.data:
            route_stop.estimated_travel_time = request.data.get(
                "estimated_travel_time"
            )

        try:

            with transaction.atomic():

                route_stop.save()

        except Exception as e:

            application_logger.exception(
                "route_stop_update_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                route_stop_id=str(route_stop.id),
                reason="route_stop_update_failed",
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description=str(e),
            )

        application_logger.info(
            "route_stop_updated",
            requested_by=str(request.user.id),
            school_id=str(school.id),
            route_stop_id=str(route_stop.id),
            route_id=str(route_stop.route.id),
            stop_id=str(route_stop.stop.id),
            stop_order=route_stop.stop_order,
        )

        return CustomResponse.successResponse(
            description="Route stop updated successfully.",
            data={
                "id": str(route_stop.id),
                "route_id": str(route_stop.route.id),
                "route_name": route_stop.route.route_name,
                "stop_id": str(route_stop.stop.id),
                "stop_name": route_stop.stop.stop_name,
                "stop_order": route_stop.stop_order,
                "pickup_time": route_stop.pickup_time,
                "drop_time": route_stop.drop_time,
                "distance_from_previous_stop": route_stop.distance_from_previous_stop,
                "estimated_travel_time": route_stop.estimated_travel_time,
            },
        )

class CreateVehicleAssignmentAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "vehicle.assignment.create"

    def post(self, request):

        school = request.school

        vehicle_id = request.data.get("vehicle_id")
        route_id = request.data.get("route_id")
        driver_id = request.data.get("driver_id")
        attendant_id = request.data.get("attendant_id")
        branch_id = request.data.get("branch_id")
        effective_from = request.data.get("effective_from")

        application_logger.info(
            "vehicle_assignment_create_requested",
            requested_by=str(request.user.id),
            school_id=str(school.id) if school else None,
            vehicle_id=vehicle_id,
            route_id=route_id,
        )

        if school is None:

            application_logger.warning(
                "vehicle_assignment_create_failed",
                requested_by=str(request.user.id),
                reason="school_not_found",
            )

            return CustomResponse.errorResponse(
                description="School not found."
            )

        required_fields = [
            "vehicle_id",
            "route_id",
            "driver_id",
            "effective_from",
        ]

        for field in required_fields:

            if request.data.get(field) in [None, ""]:

                application_logger.warning(
                    "vehicle_assignment_create_failed",
                    requested_by=str(request.user.id),
                    school_id=str(school.id),
                    field=field,
                    reason="required_field_missing",
                )

                return CustomResponse.errorResponse(
                    description=f"{field} is required."
                )

        branch = None

        if branch_id:

            branch = Branch.objects.filter(
                id=branch_id,
                school=school,
            ).first()

            if branch is None:

                application_logger.warning(
                    "vehicle_assignment_create_failed",
                    requested_by=str(request.user.id),
                    school_id=str(school.id),
                    branch_id=branch_id,
                    reason="branch_not_found",
                )

                return CustomResponse.errorResponse(
                    description="Branch not found."
                )

        vehicle = Vehicle.objects.filter(
            id=vehicle_id,
            school=school,
        ).first()

        if vehicle is None:

            application_logger.warning(
                "vehicle_assignment_create_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                vehicle_id=vehicle_id,
                reason="vehicle_not_found",
            )

            return CustomResponse.errorResponse(
                description="Vehicle not found."
            )

        route = Route.objects.filter(
            id=route_id,
            school=school,
        ).first()

        if route is None:

            application_logger.warning(
                "vehicle_assignment_create_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                route_id=route_id,
                reason="route_not_found",
            )

            return CustomResponse.errorResponse(
                description="Route not found."
            )

        driver = Staff.objects.filter(
            id=driver_id,
            school=school,
            staff_type=Staff.StaffType.DRIVER,
        ).first()

        if driver is None:

            application_logger.warning(
                "vehicle_assignment_create_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                driver_id=driver_id,
                reason="driver_not_found",
            )

            return CustomResponse.errorResponse(
                description="Driver not found."
            )

        attendant = None

        if attendant_id:

            attendant = Staff.objects.filter(
                id=attendant_id,
                school=school,
                staff_type=Staff.StaffType.BUS_ATTENDANT,
            ).first()

            if attendant is None:

                application_logger.warning(
                    "vehicle_assignment_create_failed",
                    requested_by=str(request.user.id),
                    school_id=str(school.id),
                    attendant_id=attendant_id,
                    reason="attendant_not_found",
                )

                return CustomResponse.errorResponse(
                    description="Bus attendant not found."
                )

        if VehicleAssignment.objects.filter(
            vehicle=vehicle,
            effective_from=effective_from,
        ).exists():

            application_logger.warning(
                "vehicle_assignment_create_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                vehicle_id=str(vehicle.id),
                effective_from=effective_from,
                reason="vehicle_assignment_already_exists",
            )

            return CustomResponse.errorResponse(
                description="Vehicle assignment already exists for the selected effective date."
            )

        effective_to = request.data.get("effective_to")

        if effective_to and effective_to < effective_from:

            application_logger.warning(
                "vehicle_assignment_create_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                reason="invalid_date_range",
            )

            return CustomResponse.errorResponse(
                description="Effective To should be greater than or equal to Effective From."
            )

        try:

            with transaction.atomic():

                assignment = VehicleAssignment.objects.create(
                    school=school,
                    branch=branch,
                    vehicle=vehicle,
                    route=route,
                    driver=driver,
                    attendant=attendant,
                    effective_from=effective_from,
                    effective_to=effective_to,
                    status=request.data.get(
                        "status",
                        VehicleAssignment.Status.ACTIVE,
                    ),
                    remarks=request.data.get("remarks"),
                )

        except Exception as e:

            application_logger.exception(
                "vehicle_assignment_create_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                vehicle_id=str(vehicle.id),
                route_id=str(route.id),
                reason="vehicle_assignment_creation_failed",
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description=str(e),
            )

        application_logger.info(
            "vehicle_assignment_created",
            requested_by=str(request.user.id),
            school_id=str(school.id),
            assignment_id=str(assignment.id),
            vehicle_id=str(vehicle.id),
            route_id=str(route.id),
        )

        return CustomResponse.successResponse(
            description="Vehicle assignment created successfully.",
            data={
                "id": str(assignment.id),
                "vehicle": vehicle.vehicle_number,
                "route": route.route_name,
                "driver": driver.name,
                "attendant": attendant.name if attendant else None,
                "effective_from": assignment.effective_from,
                "effective_to": assignment.effective_to,
                "status": assignment.status,
            },
        )


class VehicleAssignmentListAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "vehicle.assignment.view"

    def get(self, request):

        school = request.school

        branch_id = request.GET.get("branch_id")
        vehicle_id = request.GET.get("vehicle_id")
        route_id = request.GET.get("route_id")
        driver_id = request.GET.get("driver_id")
        status = request.GET.get("status")
        search = request.GET.get("search", "").strip()

        application_logger.info(
            "vehicle_assignment_list_requested",
            requested_by=str(request.user.id),
            school_id=str(school.id) if school else None,
            branch_id=branch_id,
            vehicle_id=vehicle_id,
            route_id=route_id,
            driver_id=driver_id,
            status=status,
            search=search,
        )

        if school is None:

            application_logger.warning(
                "vehicle_assignment_list_failed",
                requested_by=str(request.user.id),
                reason="school_not_found",
            )

            return CustomResponse.errorResponse(
                description="School not found."
            )

        try:

            assignments = VehicleAssignment.objects.select_related(
                "branch",
                "vehicle",
                "route",
                "driver",
                "attendant",
            ).filter(
                school=school,
            )

            if branch_id:

                assignments = assignments.filter(
                    branch_id=branch_id,
                )

            if vehicle_id:

                assignments = assignments.filter(
                    vehicle_id=vehicle_id,
                )

            if route_id:

                assignments = assignments.filter(
                    route_id=route_id,
                )

            if driver_id:

                assignments = assignments.filter(
                    driver_id=driver_id,
                )

            if status:

                assignments = assignments.filter(
                    status=status,
                )

            if search:

                assignments = assignments.filter(
                    Q(vehicle__vehicle_number__icontains=search)
                    | Q(route__route_name__icontains=search)
                    | Q(route__route_code__icontains=search)
                    | Q(driver__name__icontains=search)
                    | Q(attendant__name__icontains=search)
                )

            assignments = assignments.order_by(
                "-effective_from",
            )

            data = []

            for assignment in assignments:

                data.append({
                    "id": str(assignment.id),

                    "branch": (
                        {
                            "id": str(assignment.branch.id),
                            "name": assignment.branch.name,
                        }
                        if assignment.branch
                        else None
                    ),

                    "vehicle": {
                        "id": str(assignment.vehicle.id),
                        "vehicle_number": assignment.vehicle.vehicle_number,
                        "registration_number": assignment.vehicle.registration_number,
                    },

                    "route": {
                        "id": str(assignment.route.id),
                        "route_name": assignment.route.route_name,
                        "route_code": assignment.route.route_code,
                    },

                    "driver": {
                        "id": str(assignment.driver.id),
                        "employee_id": assignment.driver.employee_id,
                        "name": assignment.driver.name,
                        "mobile": assignment.driver.mobile,
                    },

                    "attendant": (
                        {
                            "id": str(assignment.attendant.id),
                            "employee_id": assignment.attendant.employee_id,
                            "name": assignment.attendant.name,
                            "mobile": assignment.attendant.mobile,
                        }
                        if assignment.attendant
                        else None
                    ),

                    "effective_from": assignment.effective_from,
                    "effective_to": assignment.effective_to,
                    "status": assignment.status,
                    "status_display": assignment.get_status_display(),
                    "remarks": assignment.remarks,
                    "created_at": assignment.created_at,
                    "updated_at": assignment.updated_at,
                })

        except Exception as e:

            application_logger.exception(
                "vehicle_assignment_list_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                reason="vehicle_assignment_fetch_failed",
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description=str(e),
            )

        application_logger.info(
            "vehicle_assignment_list_fetched",
            requested_by=str(request.user.id),
            school_id=str(school.id),
            returned_count=len(data),
        )

        return CustomResponse.successResponse(
            description="Vehicle assignments fetched successfully.",
            total=len(data),
            data=data,
        )


class UpdateVehicleAssignmentAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "vehicle.assignment.update"

    def put(self, request, assignment_id):

        school = request.school

        application_logger.info(
            "vehicle_assignment_update_requested",
            requested_by=str(request.user.id),
            school_id=str(school.id) if school else None,
            assignment_id=str(assignment_id),
        )

        if school is None:

            application_logger.warning(
                "vehicle_assignment_update_failed",
                requested_by=str(request.user.id),
                assignment_id=str(assignment_id),
                reason="school_not_found",
            )

            return CustomResponse.errorResponse(
                description="School not found."
            )

        assignment = VehicleAssignment.objects.select_related(
            "vehicle",
            "route",
            "driver",
            "attendant",
            "branch",
        ).filter(
            id=assignment_id,
            school=school,
        ).first()

        if assignment is None:

            application_logger.warning(
                "vehicle_assignment_update_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                assignment_id=str(assignment_id),
                reason="assignment_not_found",
            )

            return CustomResponse.errorResponse(
                description="Vehicle assignment not found."
            )

        branch = assignment.branch

        if "branch_id" in request.data:

            branch_id = request.data.get("branch_id")

            if branch_id:

                branch = Branch.objects.filter(
                    id=branch_id,
                    school=school,
                ).first()

                if branch is None:

                    application_logger.warning(
                        "vehicle_assignment_update_failed",
                        requested_by=str(request.user.id),
                        school_id=str(school.id),
                        assignment_id=str(assignment.id),
                        branch_id=branch_id,
                        reason="branch_not_found",
                    )

                    return CustomResponse.errorResponse(
                        description="Branch not found."
                    )

            else:

                branch = None

        vehicle = assignment.vehicle

        if "vehicle_id" in request.data:

            vehicle = Vehicle.objects.filter(
                id=request.data.get("vehicle_id"),
                school=school,
            ).first()

            if vehicle is None:

                application_logger.warning(
                    "vehicle_assignment_update_failed",
                    requested_by=str(request.user.id),
                    school_id=str(school.id),
                    assignment_id=str(assignment.id),
                    reason="vehicle_not_found",
                )

                return CustomResponse.errorResponse(
                    description="Vehicle not found."
                )

        route = assignment.route

        if "route_id" in request.data:

            route = Route.objects.filter(
                id=request.data.get("route_id"),
                school=school,
            ).first()

            if route is None:

                application_logger.warning(
                    "vehicle_assignment_update_failed",
                    requested_by=str(request.user.id),
                    school_id=str(school.id),
                    assignment_id=str(assignment.id),
                    reason="route_not_found",
                )

                return CustomResponse.errorResponse(
                    description="Route not found."
                )

        driver = assignment.driver

        if "driver_id" in request.data:

            driver = Staff.objects.filter(
                id=request.data.get("driver_id"),
                school=school,
                staff_type=Staff.StaffType.DRIVER,
            ).first()

            if driver is None:

                application_logger.warning(
                    "vehicle_assignment_update_failed",
                    requested_by=str(request.user.id),
                    school_id=str(school.id),
                    assignment_id=str(assignment.id),
                    reason="driver_not_found",
                )

                return CustomResponse.errorResponse(
                    description="Driver not found."
                )

        attendant = assignment.attendant

        if "attendant_id" in request.data:

            attendant_id = request.data.get("attendant_id")

            if attendant_id:

                attendant = Staff.objects.filter(
                    id=attendant_id,
                    school=school,
                    staff_type=Staff.StaffType.BUS_ATTENDANT,
                ).first()

                if attendant is None:

                    application_logger.warning(
                        "vehicle_assignment_update_failed",
                        requested_by=str(request.user.id),
                        school_id=str(school.id),
                        assignment_id=str(assignment.id),
                        reason="attendant_not_found",
                    )

                    return CustomResponse.errorResponse(
                        description="Bus attendant not found."
                    )

            else:

                attendant = None

        effective_from = request.data.get(
            "effective_from",
            assignment.effective_from,
        )

        if VehicleAssignment.objects.filter(
            vehicle=vehicle,
            effective_from=effective_from,
        ).exclude(
            id=assignment.id,
        ).exists():

            application_logger.warning(
                "vehicle_assignment_update_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                assignment_id=str(assignment.id),
                reason="assignment_already_exists",
            )

            return CustomResponse.errorResponse(
                description="Vehicle assignment already exists for the selected effective date."
            )

        effective_to = request.data.get(
            "effective_to",
            assignment.effective_to,
        )

        if effective_to and effective_to < effective_from:

            application_logger.warning(
                "vehicle_assignment_update_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                assignment_id=str(assignment.id),
                reason="invalid_date_range",
            )

            return CustomResponse.errorResponse(
                description="Effective To should be greater than or equal to Effective From."
            )

        assignment.branch = branch
        assignment.vehicle = vehicle
        assignment.route = route
        assignment.driver = driver
        assignment.attendant = attendant

        if "effective_from" in request.data:
            assignment.effective_from = effective_from

        if "effective_to" in request.data:
            assignment.effective_to = request.data.get("effective_to") or None

        if "status" in request.data:
            assignment.status = request.data.get("status")

        if "remarks" in request.data:
            assignment.remarks = request.data.get("remarks")

        try:

            with transaction.atomic():

                assignment.save()

        except Exception as e:

            application_logger.exception(
                "vehicle_assignment_update_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                assignment_id=str(assignment.id),
                reason="vehicle_assignment_update_failed",
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description=str(e),
            )

        application_logger.info(
            "vehicle_assignment_updated",
            requested_by=str(request.user.id),
            school_id=str(school.id),
            assignment_id=str(assignment.id),
        )

        return CustomResponse.successResponse(
            description="Vehicle assignment updated successfully.",
            data={
                "id": str(assignment.id),
                "vehicle": assignment.vehicle.vehicle_number,
                "route": assignment.route.route_name,
                "driver": assignment.driver.name,
                "attendant": (
                    assignment.attendant.name
                    if assignment.attendant
                    else None
                ),
                "effective_from": assignment.effective_from,
                "effective_to": assignment.effective_to,
                "status": assignment.status,
                "remarks": assignment.remarks,
            },
        )

class CreateStopAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "stop.create"

    def post(self, request):

        school = request.school
        branch = None

        application_logger.info(
            "stop_create_started",
            requested_by=str(request.user.id),
            school_id=str(school.id) if school else None,
        )

        branch_id = request.data.get("branch_id")

        if branch_id:

            branch = Branch.objects.filter(
                id=branch_id,
                school=school,
            ).first()

            if branch is None:

                application_logger.warning(
                    "stop_create_failed",
                    requested_by=str(request.user.id),
                    school_id=str(school.id),
                    branch_id=branch_id,
                    reason="branch_not_found",
                )

                return CustomResponse.errorResponse(
                    description="Branch not found."
                )

        try:

            stop = Stop.objects.create(
                school=school,
                branch=branch,
                stop_name=request.data.get("stop_name"),
                stop_code=request.data.get("stop_code"),
                address=request.data.get("address"),
                landmark=request.data.get("landmark"),
                latitude=request.data.get("latitude"),
                longitude=request.data.get("longitude"),
                pickup_time=request.data.get("pickup_time"),
                drop_time=request.data.get("drop_time"),
                # radius=request.data.get(
                #     "radius",
                #     100,
                # ),
                status=request.data.get(
                    "status",
                    Stop.Status.ACTIVE,
                ),
            )

        except Exception as e:

            application_logger.exception(
                "stop_create_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description=str(e),
            )

        application_logger.info(
            "stop_created",
            requested_by=str(request.user.id),
            school_id=str(school.id),
            stop_id=str(stop.id),
        )

        return CustomResponse.successResponse(
            description="Stop created successfully.",
            data={
                "id": str(stop.id),
            },
        )

class StopListAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "stop.view"

    def get(self, request):

        school = request.school

        branch_id = request.query_params.get("branch_id")
        search = request.query_params.get("search")

        application_logger.info(
            "stop_list_started",
            requested_by=str(request.user.id),
            school_id=str(school.id) if school else None,
            branch_id=branch_id,
            search=search,
        )

        queryset = Stop.objects.select_related(
            "branch",
        ).filter(
            school=school,
        )

        if branch_id:

            queryset = queryset.filter(
                branch_id=branch_id,
            )

        if search:

            queryset = queryset.filter(
                Q(stop_name__icontains=search)
                | Q(stop_code__icontains=search)
                | Q(address__icontains=search)
                | Q(landmark__icontains=search)
            )

        queryset = queryset.order_by(
            "stop_name",
        )

        data = []

        for stop in queryset:

            data.append({
                "id": str(stop.id),
                "branch": {
                    "id": str(stop.branch.id),
                    "name": stop.branch.name,
                } if stop.branch else None,
                "stop_name": stop.stop_name,
                "stop_code": stop.stop_code,
                "address": stop.address,
                "landmark": stop.landmark,
                "latitude": stop.latitude,
                "longitude": stop.longitude,
                "pickup_time": stop.pickup_time,
                "drop_time": stop.drop_time,
                "radius": stop.radius,
                "status": stop.status,
            })

        application_logger.info(
            "stop_list_fetched",
            requested_by=str(request.user.id),
            school_id=str(school.id) if school else None,
            total_count=len(data),
        )

        return CustomResponse.successResponse(
            description="Stops fetched successfully.",
            total=len(data),
            data=data,
        )

class UpdateStopAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "stop.update"

    def put(self, request, stop_id):

        school = request.school

        application_logger.info(
            "stop_update_started",
            requested_by=str(request.user.id),
            school_id=str(school.id) if school else None,
            stop_id=str(stop_id),
        )

        stop = Stop.objects.filter(
            id=stop_id,
            school=school,
        ).first()

        if stop is None:

            application_logger.warning(
                "stop_update_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                stop_id=str(stop_id),
                reason="stop_not_found",
            )

            return CustomResponse.errorResponse(
                description="Stop not found."
            )

        branch = stop.branch

        branch_id = request.data.get("branch_id")

        if branch_id:

            branch = Branch.objects.filter(
                id=branch_id,
                school=school,
            ).first()

            if branch is None:

                application_logger.warning(
                    "stop_update_failed",
                    requested_by=str(request.user.id),
                    school_id=str(school.id),
                    branch_id=branch_id,
                    stop_id=str(stop.id),
                    reason="branch_not_found",
                )

                return CustomResponse.errorResponse(
                    description="Branch not found."
                )

        elif "branch_id" in request.data:

            # Allow removing branch
            branch = None

        try:

            stop.branch = branch
            stop.stop_name = request.data.get(
                "stop_name",
                stop.stop_name,
            )
            stop.stop_code = request.data.get(
                "stop_code",
                stop.stop_code,
            )
            stop.address = request.data.get(
                "address",
                stop.address,
            )
            stop.landmark = request.data.get(
                "landmark",
                stop.landmark,
            )
            stop.latitude = request.data.get(
                "latitude",
                stop.latitude,
            )
            stop.longitude = request.data.get(
                "longitude",
                stop.longitude,
            )
            stop.pickup_time = request.data.get(
                "pickup_time",
                stop.pickup_time,
            )
            stop.drop_time = request.data.get(
                "drop_time",
                stop.drop_time,
            )
            stop.radius = request.data.get(
                "radius",
                stop.radius,
            )
            stop.status = request.data.get(
                "status",
                stop.status,
            )

            stop.save()

        except Exception as e:

            application_logger.exception(
                "stop_update_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                stop_id=str(stop.id),
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description=str(e),
            )

        application_logger.info(
            "stop_updated",
            requested_by=str(request.user.id),
            school_id=str(school.id),
            stop_id=str(stop.id),
        )

        return CustomResponse.successResponse(
            description="Stop updated successfully.",
        )

class CreateStudentTransportAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "student.transport.create"

    def post(self, request):

        school = request.school

        academic_year_id = request.data.get("academic_year_id")
        branch_id = request.data.get("branch_id")
        student_id = request.data.get("student_id")
        vehicle_assignment_id = request.data.get("vehicle_assignment_id")
        pickup_stop_id = request.data.get("pickup_stop_id")
        drop_stop_id = request.data.get("drop_stop_id")
        trip_type = request.data.get("trip_type")

        application_logger.info(
            "student_transport_create_requested",
            requested_by=str(request.user.id),
            school_id=str(school.id) if school else None,
            student_id=student_id,
            vehicle_assignment_id=vehicle_assignment_id,
        )

        if school is None:

            application_logger.warning(
                "student_transport_create_failed",
                requested_by=str(request.user.id),
                reason="school_not_found",
            )

            return CustomResponse.errorResponse(
                description="School not found."
            )

        required_fields = [
            "academic_year_id",
            "student_id",
            "vehicle_assignment_id",
        ]

        for field in required_fields:

            if request.data.get(field) in [None, ""]:

                application_logger.warning(
                    "student_transport_create_failed",
                    requested_by=str(request.user.id),
                    school_id=str(school.id),
                    field=field,
                    reason="required_field_missing",
                )

                return CustomResponse.errorResponse(
                    description=f"{field} is required."
                )

        academic_year = AcademicYear.objects.filter(
            id=academic_year_id,
            school=school,
        ).first()

        if academic_year is None:

            application_logger.warning(
                "student_transport_create_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                academic_year_id=academic_year_id,
                reason="academic_year_not_found",
            )

            return CustomResponse.errorResponse(
                description="Academic year not found."
            )

        branch = None

        if branch_id:

            branch = Branch.objects.filter(
                id=branch_id,
                school=school,
            ).first()

            if branch is None:

                application_logger.warning(
                    "student_transport_create_failed",
                    requested_by=str(request.user.id),
                    school_id=str(school.id),
                    branch_id=branch_id,
                    reason="branch_not_found",
                )

                return CustomResponse.errorResponse(
                    description="Branch not found."
                )

        student = Student.objects.filter(
            id=student_id,
            school=school,
        ).first()

        if student is None:

            application_logger.warning(
                "student_transport_create_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                student_id=student_id,
                reason="student_not_found",
            )

            return CustomResponse.errorResponse(
                description="Student not found."
            )

        vehicle_assignment = VehicleAssignment.objects.select_related(
            "route",
        ).filter(
            id=vehicle_assignment_id,
            school=school,
        ).first()

        if vehicle_assignment is None:

            application_logger.warning(
                "student_transport_create_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                vehicle_assignment_id=vehicle_assignment_id,
                reason="vehicle_assignment_not_found",
            )

            return CustomResponse.errorResponse(
                description="Vehicle assignment not found."
            )

        pickup_stop = None

        if pickup_stop_id:

            pickup_stop = Stop.objects.filter(
                id=pickup_stop_id,
                school=school,
            ).first()

            if pickup_stop is None:

                application_logger.warning(
                    "student_transport_create_failed",
                    requested_by=str(request.user.id),
                    school_id=str(school.id),
                    pickup_stop_id=pickup_stop_id,
                    reason="pickup_stop_not_found",
                )

                return CustomResponse.errorResponse(
                    description="Pickup stop not found."
                )

            if not RouteStop.objects.filter(
                route=vehicle_assignment.route,
                stop=pickup_stop,
            ).exists():

                application_logger.warning(
                    "student_transport_create_failed",
                    requested_by=str(request.user.id),
                    school_id=str(school.id),
                    pickup_stop_id=pickup_stop_id,
                    reason="pickup_stop_not_in_route",
                )

                return CustomResponse.errorResponse(
                    description="Pickup stop is not mapped to the selected route."
                )

        drop_stop = None

        if drop_stop_id:

            drop_stop = Stop.objects.filter(
                id=drop_stop_id,
                school=school,
            ).first()

            if drop_stop is None:

                application_logger.warning(
                    "student_transport_create_failed",
                    requested_by=str(request.user.id),
                    school_id=str(school.id),
                    drop_stop_id=drop_stop_id,
                    reason="drop_stop_not_found",
                )

                return CustomResponse.errorResponse(
                    description="Drop stop not found."
                )

            if not RouteStop.objects.filter(
                route=vehicle_assignment.route,
                stop=drop_stop,
            ).exists():

                application_logger.warning(
                    "student_transport_create_failed",
                    requested_by=str(request.user.id),
                    school_id=str(school.id),
                    drop_stop_id=drop_stop_id,
                    reason="drop_stop_not_in_route",
                )

                return CustomResponse.errorResponse(
                    description="Drop stop is not mapped to the selected route."
                )

        if trip_type:

            if trip_type not in StudentTransport.TripType.values:

                application_logger.warning(
                    "student_transport_create_failed",
                    requested_by=str(request.user.id),
                    school_id=str(school.id),
                    trip_type=trip_type,
                    reason="invalid_trip_type",
                )

                return CustomResponse.errorResponse(
                    description="Invalid trip type."
                )

        if StudentTransport.objects.filter(
            academic_year=academic_year,
            student=student,
        ).exists():

            application_logger.warning(
                "student_transport_create_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                student_id=str(student.id),
                academic_year_id=str(academic_year.id),
                reason="student_transport_already_exists",
            )

            return CustomResponse.errorResponse(
                description="Transport is already assigned to this student."
            )
        try:

            with transaction.atomic():

                student_transport = StudentTransport.objects.create(
                    school=school,
                    branch=branch,
                    academic_year=academic_year,
                    student=student,
                    vehicle_assignment=vehicle_assignment,
                    pickup_stop=pickup_stop,
                    drop_stop=drop_stop,
                    trip_type=request.data.get(
                        "trip_type",
                        StudentTransport.TripType.BOTH,
                    ),
                    status=request.data.get(
                        "status",
                        StudentTransport.Status.ACTIVE,
                    ),
                    remarks=request.data.get("remarks"),
                )

        except Exception as e:

            application_logger.exception(
                "student_transport_create_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                student_id=str(student.id),
                vehicle_assignment_id=str(vehicle_assignment.id),
                reason="student_transport_creation_failed",
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description=str(e),
            )

        application_logger.info(
            "student_transport_created",
            requested_by=str(request.user.id),
            school_id=str(school.id),
            student_transport_id=str(student_transport.id),
            student_id=str(student.id),
            vehicle_assignment_id=str(vehicle_assignment.id),
        )

        return CustomResponse.successResponse(
            description="Student transport assigned successfully.",
            data={
                "id": str(student_transport.id),
                "student": {
                    "id": str(student.id),
                    "name": student.name,
                },
                "vehicle": {
                    "id": str(vehicle_assignment.vehicle.id),
                    "vehicle_number": vehicle_assignment.vehicle.vehicle_number,
                },
                "route": {
                    "id": str(vehicle_assignment.route.id),
                    "route_name": vehicle_assignment.route.route_name,
                },
                "driver": {
                    "id": str(vehicle_assignment.driver.id),
                    "name": vehicle_assignment.driver.name,
                },
                "pickup_stop": (
                    {
                        "id": str(pickup_stop.id),
                        "stop_name": pickup_stop.stop_name,
                    }
                    if pickup_stop
                    else None
                ),
                "drop_stop": (
                    {
                        "id": str(drop_stop.id),
                        "stop_name": drop_stop.stop_name,
                    }
                    if drop_stop
                    else None
                ),
                "trip_type": student_transport.trip_type,
                "status": student_transport.status,
                "remarks": student_transport.remarks,
            },
        )

class StudentTransportListAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "student.transport.view"

    def get(self, request):

        school = request.school

        academic_year_id = request.GET.get("academic_year_id")
        branch_id = request.GET.get("branch_id")
        vehicle_assignment_id = request.GET.get("vehicle_assignment_id")
        student_id = request.GET.get("student_id")
        status = request.GET.get("status")
        search = request.GET.get("search", "").strip()

        application_logger.info(
            "student_transport_list_requested",
            requested_by=str(request.user.id),
            school_id=str(school.id) if school else None,
            academic_year_id=academic_year_id,
            branch_id=branch_id,
            vehicle_assignment_id=vehicle_assignment_id,
            student_id=student_id,
            status=status,
            search=search,
        )

        if school is None:

            application_logger.warning(
                "student_transport_list_failed",
                requested_by=str(request.user.id),
                reason="school_not_found",
            )

            return CustomResponse.errorResponse(
                description="School not found."
            )

        try:

            transports = StudentTransport.objects.select_related(
                "academic_year",
                "branch",
                "student",
                "vehicle_assignment",
                "vehicle_assignment__vehicle",
                "vehicle_assignment__route",
                "vehicle_assignment__driver",
                "pickup_stop",
                "drop_stop",
            ).filter(
                school=school,
            )

            if academic_year_id:

                transports = transports.filter(
                    academic_year_id=academic_year_id,
                )

            if branch_id:

                transports = transports.filter(
                    branch_id=branch_id,
                )

            if vehicle_assignment_id:

                transports = transports.filter(
                    vehicle_assignment_id=vehicle_assignment_id,
                )

            if student_id:

                transports = transports.filter(
                    student_id=student_id,
                )

            if status:

                transports = transports.filter(
                    status=status,
                )

            if search:

                transports = transports.filter(
                    Q(student__name__icontains=search)
                    | Q(student__admission_number__icontains=search)
                    | Q(vehicle_assignment__vehicle__vehicle_number__icontains=search)
                    | Q(vehicle_assignment__route__route_name__icontains=search)
                )

            transports = transports.order_by(
                "student__name",
            )

            data = []

            for transport in transports:

                data.append({
                    "id": str(transport.id),

                    "academic_year": {
                        "id": str(transport.academic_year.id),
                        "name": transport.academic_year.name,
                    },

                    "branch": (
                        {
                            "id": str(transport.branch.id),
                            "name": transport.branch.name,
                        }
                        if transport.branch
                        else None
                    ),

                    "student": {
                        "id": str(transport.student.id),
                        "name": transport.student.name,
                        "admission_number": transport.student.admission_number,
                    },

                    "vehicle": {
                        "id": str(transport.vehicle_assignment.vehicle.id),
                        "vehicle_number": transport.vehicle_assignment.vehicle.vehicle_number,
                    },

                    "route": {
                        "id": str(transport.vehicle_assignment.route.id),
                        "route_name": transport.vehicle_assignment.route.route_name,
                        "route_code": transport.vehicle_assignment.route.route_code,
                    },

                    "driver": {
                        "id": str(transport.vehicle_assignment.driver.id),
                        "name": transport.vehicle_assignment.driver.name,
                        "mobile": transport.vehicle_assignment.driver.mobile,
                    },

                    "pickup_stop": (
                        {
                            "id": str(transport.pickup_stop.id),
                            "stop_name": transport.pickup_stop.stop_name,
                        }
                        if transport.pickup_stop
                        else None
                    ),

                    "drop_stop": (
                        {
                            "id": str(transport.drop_stop.id),
                            "stop_name": transport.drop_stop.stop_name,
                        }
                        if transport.drop_stop
                        else None
                    ),

                    "trip_type": transport.trip_type,
                    "trip_type_display": transport.get_trip_type_display(),

                    "status": transport.status,
                    "status_display": transport.get_status_display(),

                    "remarks": transport.remarks,

                    "created_at": transport.created_at,
                    "updated_at": transport.updated_at,
                })

        except Exception as e:

            application_logger.exception(
                "student_transport_list_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                reason="student_transport_fetch_failed",
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description=str(e),
            )

        application_logger.info(
            "student_transport_list_fetched",
            requested_by=str(request.user.id),
            school_id=str(school.id),
            returned_count=len(data),
        )

        return CustomResponse.successResponse(
            description="Student transport assignments fetched successfully.",
            total=len(data),
            data=data,
        )


class UpdateStudentTransportAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "student.transport.update"

    def put(self, request, student_transport_id):

        school = request.school

        application_logger.info(
            "student_transport_update_requested",
            requested_by=str(request.user.id),
            school_id=str(school.id) if school else None,
            student_transport_id=str(student_transport_id),
        )

        if school is None:

            application_logger.warning(
                "student_transport_update_failed",
                requested_by=str(request.user.id),
                reason="school_not_found",
            )

            return CustomResponse.errorResponse(
                description="School not found."
            )

        student_transport = StudentTransport.objects.select_related(
            "academic_year",
            "student",
            "vehicle_assignment",
            "pickup_stop",
            "drop_stop",
            "branch",
        ).filter(
            id=student_transport_id,
            school=school,
        ).first()

        if student_transport is None:

            application_logger.warning(
                "student_transport_update_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                student_transport_id=str(student_transport_id),
                reason="student_transport_not_found",
            )

            return CustomResponse.errorResponse(
                description="Student transport not found."
            )

        branch = student_transport.branch

        if "branch_id" in request.data:

            branch_id = request.data.get("branch_id")

            if branch_id:

                branch = Branch.objects.filter(
                    id=branch_id,
                    school=school,
                ).first()

                if branch is None:

                    application_logger.warning(
                        "student_transport_update_failed",
                        requested_by=str(request.user.id),
                        school_id=str(school.id),
                        branch_id=branch_id,
                        reason="branch_not_found",
                    )

                    return CustomResponse.errorResponse(
                        description="Branch not found."
                    )

            else:

                branch = None

        vehicle_assignment = student_transport.vehicle_assignment

        if "vehicle_assignment_id" in request.data:

            vehicle_assignment = VehicleAssignment.objects.select_related(
                "route",
            ).filter(
                id=request.data.get("vehicle_assignment_id"),
                school=school,
            ).first()

            if vehicle_assignment is None:

                application_logger.warning(
                    "student_transport_update_failed",
                    requested_by=str(request.user.id),
                    school_id=str(school.id),
                    reason="vehicle_assignment_not_found",
                )

                return CustomResponse.errorResponse(
                    description="Vehicle assignment not found."
                )

        pickup_stop = student_transport.pickup_stop

        if "pickup_stop_id" in request.data:

            pickup_stop_id = request.data.get("pickup_stop_id")

            if pickup_stop_id:

                pickup_stop = Stop.objects.filter(
                    id=pickup_stop_id,
                    school=school,
                ).first()

                if pickup_stop is None:

                    application_logger.warning(
                        "student_transport_update_failed",
                        requested_by=str(request.user.id),
                        school_id=str(school.id),
                        reason="pickup_stop_not_found",
                    )

                    return CustomResponse.errorResponse(
                        description="Pickup stop not found."
                    )

                if not RouteStop.objects.filter(
                    route=vehicle_assignment.route,
                    stop=pickup_stop,
                ).exists():

                    return CustomResponse.errorResponse(
                        description="Pickup stop is not mapped to the selected route."
                    )

            else:

                pickup_stop = None

        drop_stop = student_transport.drop_stop

        if "drop_stop_id" in request.data:

            drop_stop_id = request.data.get("drop_stop_id")

            if drop_stop_id:

                drop_stop = Stop.objects.filter(
                    id=drop_stop_id,
                    school=school,
                ).first()

                if drop_stop is None:

                    application_logger.warning(
                        "student_transport_update_failed",
                        requested_by=str(request.user.id),
                        school_id=str(school.id),
                        reason="drop_stop_not_found",
                    )

                    return CustomResponse.errorResponse(
                        description="Drop stop not found."
                    )

                if not RouteStop.objects.filter(
                    route=vehicle_assignment.route,
                    stop=drop_stop,
                ).exists():

                    return CustomResponse.errorResponse(
                        description="Drop stop is not mapped to the selected route."
                    )

            else:

                drop_stop = None

        if "trip_type" in request.data:

            trip_type = request.data.get("trip_type")

            if trip_type not in StudentTransport.TripType.values:

                application_logger.warning(
                    "student_transport_update_failed",
                    requested_by=str(request.user.id),
                    school_id=str(school.id),
                    trip_type=trip_type,
                    reason="invalid_trip_type",
                )

                return CustomResponse.errorResponse(
                    description="Invalid trip type."
                )

            student_transport.trip_type = trip_type

        if "status" in request.data:

            status = request.data.get("status")

            if status not in StudentTransport.Status.values:

                application_logger.warning(
                    "student_transport_update_failed",
                    requested_by=str(request.user.id),
                    school_id=str(school.id),
                    status=status,
                    reason="invalid_status",
                )

                return CustomResponse.errorResponse(
                    description="Invalid status."
                )

            student_transport.status = status

        student_transport.branch = branch
        student_transport.vehicle_assignment = vehicle_assignment
        student_transport.pickup_stop = pickup_stop
        student_transport.drop_stop = drop_stop

        if "remarks" in request.data:
            student_transport.remarks = request.data.get("remarks")

        try:

            with transaction.atomic():

                student_transport.save()

        except Exception as e:

            application_logger.exception(
                "student_transport_update_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                student_transport_id=str(student_transport.id),
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description=str(e),
            )

        application_logger.info(
            "student_transport_updated",
            requested_by=str(request.user.id),
            school_id=str(school.id),
            student_transport_id=str(student_transport.id),
        )

        return CustomResponse.successResponse(
            description="Student transport updated successfully.",
            data={
                "id": str(student_transport.id),
                "student": student_transport.student.name,
                "vehicle": student_transport.vehicle_assignment.vehicle.vehicle_number,
                "route": student_transport.vehicle_assignment.route.route_name,
                "trip_type": student_transport.trip_type,
                "status": student_transport.status,
            },
        )


class CreateTripAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "trip.create"

    def post(self, request):

        school = request.school

        branch_id = request.data.get("branch_id")
        vehicle_assignment_id = request.data.get("vehicle_assignment_id")
        trip_date = request.data.get("trip_date")
        shift = request.data.get("shift")
        scheduled_start_time = request.data.get("scheduled_start_time")

        application_logger.info(
            "trip_create_requested",
            requested_by=str(request.user.id),
            school_id=str(school.id) if school else None,
            vehicle_assignment_id=vehicle_assignment_id,
        )

        if school is None:

            application_logger.warning(
                "trip_create_failed",
                requested_by=str(request.user.id),
                reason="school_not_found",
            )

            return CustomResponse.errorResponse(
                description="School not found."
            )

        required_fields = [
            "vehicle_assignment_id",
            "trip_date",
            "shift",
            "scheduled_start_time",
        ]

        for field in required_fields:

            if request.data.get(field) in [None, ""]:

                application_logger.warning(
                    "trip_create_failed",
                    requested_by=str(request.user.id),
                    school_id=str(school.id),
                    field=field,
                    reason="required_field_missing",
                )

                return CustomResponse.errorResponse(
                    description=f"{field} is required."
                )

        branch = None

        if branch_id:

            branch = Branch.objects.filter(
                id=branch_id,
                school=school,
            ).first()

            if branch is None:

                application_logger.warning(
                    "trip_create_failed",
                    requested_by=str(request.user.id),
                    school_id=str(school.id),
                    branch_id=branch_id,
                    reason="branch_not_found",
                )

                return CustomResponse.errorResponse(
                    description="Branch not found."
                )

        vehicle_assignment = VehicleAssignment.objects.select_related(
            "vehicle",
            "route",
            "driver",
        ).filter(
            id=vehicle_assignment_id,
            school=school,
        ).first()

        if vehicle_assignment is None:

            application_logger.warning(
                "trip_create_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                vehicle_assignment_id=vehicle_assignment_id,
                reason="vehicle_assignment_not_found",
            )

            return CustomResponse.errorResponse(
                description="Vehicle assignment not found."
            )

        if shift not in Trip.Shift.values:

            application_logger.warning(
                "trip_create_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                shift=shift,
                reason="invalid_shift",
            )

            return CustomResponse.errorResponse(
                description="Invalid shift."
            )

        if Trip.objects.filter(
            vehicle_assignment=vehicle_assignment,
            trip_date=trip_date,
            shift=shift,
        ).exists():

            application_logger.warning(
                "trip_create_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                vehicle_assignment_id=str(vehicle_assignment.id),
                trip_date=trip_date,
                shift=shift,
                reason="trip_already_exists",
            )

            return CustomResponse.errorResponse(
                description="Trip already exists."
            )

        try:

            with transaction.atomic():

                trip = Trip.objects.create(
                    school=school,
                    branch=branch,
                    vehicle_assignment=vehicle_assignment,
                    trip_date=trip_date,
                    shift=shift,
                    scheduled_start_time=scheduled_start_time,
                    scheduled_end_time=request.data.get(
                        "scheduled_end_time"
                    ),
                    actual_start_time=request.data.get(
                        "actual_start_time"
                    ),
                    actual_end_time=request.data.get(
                        "actual_end_time"
                    ),
                    start_odometer=request.data.get(
                        "start_odometer"
                    ),
                    end_odometer=request.data.get(
                        "end_odometer"
                    ),
                    total_distance=request.data.get(
                        "total_distance"
                    ),
                    status=request.data.get(
                        "status",
                        Trip.Status.SCHEDULED,
                    ),
                    remarks=request.data.get(
                        "remarks"
                    ),
                )

        except Exception as e:

            application_logger.exception(
                "trip_create_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                vehicle_assignment_id=str(vehicle_assignment.id),
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description=str(e),
            )

        application_logger.info(
            "trip_created",
            requested_by=str(request.user.id),
            school_id=str(school.id),
            trip_id=str(trip.id),
        )

        return CustomResponse.successResponse(
            description="Trip created successfully.",
            data={
                "id": str(trip.id),
                "vehicle": trip.vehicle_assignment.vehicle.vehicle_number,
                "route": trip.vehicle_assignment.route.route_name,
                "driver": trip.vehicle_assignment.driver.name,
                "trip_date": trip.trip_date,
                "shift": trip.shift,
                "scheduled_start_time": trip.scheduled_start_time,
                "scheduled_end_time": trip.scheduled_end_time,
                "status": trip.status,
            },
        )


class TripListAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "trip.view"

    def get(self, request):

        school = request.school

        branch_id = request.GET.get("branch_id")
        vehicle_assignment_id = request.GET.get("vehicle_assignment_id")
        trip_date = request.GET.get("trip_date")
        shift = request.GET.get("shift")
        status = request.GET.get("status")
        search = request.GET.get("search", "").strip()

        application_logger.info(
            "trip_list_requested",
            requested_by=str(request.user.id),
            school_id=str(school.id) if school else None,
            branch_id=branch_id,
            vehicle_assignment_id=vehicle_assignment_id,
            trip_date=trip_date,
            shift=shift,
            status=status,
            search=search,
        )

        if school is None:

            application_logger.warning(
                "trip_list_failed",
                requested_by=str(request.user.id),
                reason="school_not_found",
            )

            return CustomResponse.errorResponse(
                description="School not found."
            )

        try:

            trips = Trip.objects.select_related(
                "branch",
                "vehicle_assignment",
                "vehicle_assignment__vehicle",
                "vehicle_assignment__route",
                "vehicle_assignment__driver",
                "vehicle_assignment__attendant",
            ).filter(
                school=school,
            )

            if branch_id:

                trips = trips.filter(
                    branch_id=branch_id,
                )

            if vehicle_assignment_id:

                trips = trips.filter(
                    vehicle_assignment_id=vehicle_assignment_id,
                )

            if trip_date:

                trips = trips.filter(
                    trip_date=trip_date,
                )

            if shift:

                trips = trips.filter(
                    shift=shift,
                )

            if status:

                trips = trips.filter(
                    status=status,
                )

            if search:

                trips = trips.filter(
                    Q(
                        vehicle_assignment__vehicle__vehicle_number__icontains=search
                    )
                    | Q(
                        vehicle_assignment__route__route_name__icontains=search
                    )
                    | Q(
                        vehicle_assignment__driver__name__icontains=search
                    )
                )

            trips = trips.order_by(
                "-trip_date",
                "scheduled_start_time",
            )

            data = []

            for trip in trips:

                data.append({

                    "id": str(trip.id),

                    "branch": (
                        {
                            "id": str(trip.branch.id),
                            "name": trip.branch.name,
                        }
                        if trip.branch
                        else None
                    ),

                    "vehicle": {
                        "id": str(trip.vehicle_assignment.vehicle.id),
                        "vehicle_number": trip.vehicle_assignment.vehicle.vehicle_number,
                        "registration_number": trip.vehicle_assignment.vehicle.registration_number,
                    },

                    "route": {
                        "id": str(trip.vehicle_assignment.route.id),
                        "route_name": trip.vehicle_assignment.route.route_name,
                        "route_code": trip.vehicle_assignment.route.route_code,
                    },

                    "driver": {
                        "id": str(trip.vehicle_assignment.driver.id),
                        "name": trip.vehicle_assignment.driver.name,
                        "mobile": trip.vehicle_assignment.driver.mobile,
                    },

                    "attendant": (
                        {
                            "id": str(trip.vehicle_assignment.attendant.id),
                            "name": trip.vehicle_assignment.attendant.name,
                            "mobile": trip.vehicle_assignment.attendant.mobile,
                        }
                        if trip.vehicle_assignment.attendant
                        else None
                    ),

                    "trip_date": trip.trip_date,

                    "shift": trip.shift,
                    "shift_display": trip.get_shift_display(),

                    "scheduled_start_time": trip.scheduled_start_time,
                    "scheduled_end_time": trip.scheduled_end_time,

                    "actual_start_time": trip.actual_start_time,
                    "actual_end_time": trip.actual_end_time,

                    "start_odometer": trip.start_odometer,
                    "end_odometer": trip.end_odometer,
                    "total_distance": trip.total_distance,

                    "status": trip.status,
                    "status_display": trip.get_status_display(),

                    "remarks": trip.remarks,

                    "created_at": trip.created_at,
                    "updated_at": trip.updated_at,
                })

        except Exception as e:

            application_logger.exception(
                "trip_list_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description=str(e),
            )

        application_logger.info(
            "trip_list_fetched",
            requested_by=str(request.user.id),
            school_id=str(school.id),
            returned_count=len(data),
        )

        return CustomResponse.successResponse(
            description="Trips fetched successfully.",
            total=len(data),
            data=data,
        )


class UpdateTripAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "trip.update"

    def put(self, request, trip_id):

        school = request.school

        application_logger.info(
            "trip_update_requested",
            requested_by=str(request.user.id),
            school_id=str(school.id) if school else None,
            trip_id=str(trip_id),
        )

        if school is None:

            application_logger.warning(
                "trip_update_failed",
                requested_by=str(request.user.id),
                reason="school_not_found",
            )

            return CustomResponse.errorResponse(
                description="School not found."
            )

        trip = Trip.objects.select_related(
            "vehicle_assignment",
            "vehicle_assignment__vehicle",
            "vehicle_assignment__route",
            "branch",
        ).filter(
            id=trip_id,
            school=school,
        ).first()

        if trip is None:

            application_logger.warning(
                "trip_update_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                trip_id=str(trip_id),
                reason="trip_not_found",
            )

            return CustomResponse.errorResponse(
                description="Trip not found."
            )

        branch = trip.branch

        if "branch_id" in request.data:

            branch_id = request.data.get("branch_id")

            if branch_id:

                branch = Branch.objects.filter(
                    id=branch_id,
                    school=school,
                ).first()

                if branch is None:

                    application_logger.warning(
                        "trip_update_failed",
                        requested_by=str(request.user.id),
                        school_id=str(school.id),
                        branch_id=branch_id,
                        reason="branch_not_found",
                    )

                    return CustomResponse.errorResponse(
                        description="Branch not found."
                    )

            else:

                branch = None

        vehicle_assignment = trip.vehicle_assignment

        if "vehicle_assignment_id" in request.data:

            vehicle_assignment = VehicleAssignment.objects.filter(
                id=request.data.get("vehicle_assignment_id"),
                school=school,
            ).first()

            if vehicle_assignment is None:

                application_logger.warning(
                    "trip_update_failed",
                    requested_by=str(request.user.id),
                    school_id=str(school.id),
                    reason="vehicle_assignment_not_found",
                )

                return CustomResponse.errorResponse(
                    description="Vehicle assignment not found."
                )

        trip_date = request.data.get(
            "trip_date",
            trip.trip_date,
        )

        shift = request.data.get(
            "shift",
            trip.shift,
        )

        if shift not in Trip.Shift.values:

            application_logger.warning(
                "trip_update_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                shift=shift,
                reason="invalid_shift",
            )

            return CustomResponse.errorResponse(
                description="Invalid shift."
            )

        if Trip.objects.filter(
            vehicle_assignment=vehicle_assignment,
            trip_date=trip_date,
            shift=shift,
        ).exclude(
            id=trip.id,
        ).exists():

            application_logger.warning(
                "trip_update_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                reason="trip_already_exists",
            )

            return CustomResponse.errorResponse(
                description="Trip already exists for the selected vehicle, date and shift."
            )

        trip.branch = branch
        trip.vehicle_assignment = vehicle_assignment
        trip.trip_date = trip_date
        trip.shift = shift

        if "scheduled_start_time" in request.data:
            trip.scheduled_start_time = request.data.get(
                "scheduled_start_time"
            )

        if "scheduled_end_time" in request.data:
            trip.scheduled_end_time = request.data.get(
                "scheduled_end_time"
            )

        if "actual_start_time" in request.data:
            trip.actual_start_time = request.data.get(
                "actual_start_time"
            )

        if "actual_end_time" in request.data:
            trip.actual_end_time = request.data.get(
                "actual_end_time"
            )

        if "start_odometer" in request.data:
            trip.start_odometer = request.data.get(
                "start_odometer"
            )

        if "end_odometer" in request.data:
            trip.end_odometer = request.data.get(
                "end_odometer"
            )

        if "total_distance" in request.data:
            trip.total_distance = request.data.get(
                "total_distance"
            )

        if "status" in request.data:

            status = request.data.get("status")

            if status not in Trip.Status.values:

                application_logger.warning(
                    "trip_update_failed",
                    requested_by=str(request.user.id),
                    school_id=str(school.id),
                    status=status,
                    reason="invalid_status",
                )

                return CustomResponse.errorResponse(
                    description="Invalid status."
                )

            trip.status = status

        if "remarks" in request.data:
            trip.remarks = request.data.get("remarks")

        try:

            with transaction.atomic():

                trip.save()

        except Exception as e:

            application_logger.exception(
                "trip_update_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                trip_id=str(trip.id),
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description=str(e),
            )

        application_logger.info(
            "trip_updated",
            requested_by=str(request.user.id),
            school_id=str(school.id),
            trip_id=str(trip.id),
        )

        return CustomResponse.successResponse(
            description="Trip updated successfully.",
            data={
                "id": str(trip.id),
                "vehicle": trip.vehicle_assignment.vehicle.vehicle_number,
                "route": trip.vehicle_assignment.route.route_name,
                "trip_date": trip.trip_date,
                "shift": trip.shift,
                "status": trip.status,
            },
        )



class CreateTripAttendanceAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "trip.attendance.create"

    def post(self, request):

        school = request.school

        branch_id = request.data.get("branch_id")
        trip_id = request.data.get("trip_id")
        student_id = request.data.get("student_id")

        application_logger.info(
            "trip_attendance_create_requested",
            requested_by=str(request.user.id),
            school_id=str(school.id) if school else None,
            trip_id=trip_id,
            student_id=student_id,
        )

        if school is None:

            application_logger.warning(
                "trip_attendance_create_failed",
                requested_by=str(request.user.id),
                reason="school_not_found",
            )

            return CustomResponse.errorResponse(
                description="School not found."
            )

        required_fields = [
            "trip_id",
            "student_id",
        ]

        for field in required_fields:

            if request.data.get(field) in [None, ""]:

                application_logger.warning(
                    "trip_attendance_create_failed",
                    requested_by=str(request.user.id),
                    school_id=str(school.id),
                    field=field,
                    reason="required_field_missing",
                )

                return CustomResponse.errorResponse(
                    description=f"{field} is required."
                )

        branch = None

        if branch_id:

            branch = Branch.objects.filter(
                id=branch_id,
                school=school,
            ).first()

            if branch is None:

                application_logger.warning(
                    "trip_attendance_create_failed",
                    requested_by=str(request.user.id),
                    school_id=str(school.id),
                    branch_id=branch_id,
                    reason="branch_not_found",
                )

                return CustomResponse.errorResponse(
                    description="Branch not found."
                )

        trip = Trip.objects.filter(
            id=trip_id,
            school=school,
        ).first()

        if trip is None:

            application_logger.warning(
                "trip_attendance_create_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                trip_id=trip_id,
                reason="trip_not_found",
            )

            return CustomResponse.errorResponse(
                description="Trip not found."
            )

        student = Student.objects.filter(
            id=student_id,
            school=school,
        ).first()

        if student is None:

            application_logger.warning(
                "trip_attendance_create_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                student_id=student_id,
                reason="student_not_found",
            )

            return CustomResponse.errorResponse(
                description="Student not found."
            )

        if not StudentTransport.objects.filter(
            school=school,
            student=student,
            vehicle_assignment=trip.vehicle_assignment,
            status=StudentTransport.Status.ACTIVE,
        ).exists():

            application_logger.warning(
                "trip_attendance_create_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                student_id=str(student.id),
                reason="student_not_assigned_to_vehicle",
            )

            return CustomResponse.errorResponse(
                description="Student is not assigned to this vehicle."
            )

        if TripAttendance.objects.filter(
            trip=trip,
            student=student,
        ).exists():

            application_logger.warning(
                "trip_attendance_create_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                trip_id=str(trip.id),
                student_id=str(student.id),
                reason="attendance_already_exists",
            )

            return CustomResponse.errorResponse(
                description="Attendance already marked."
            )

        pickup_status = request.data.get(
            "pickup_status",
            TripAttendance.PickupStatus.PENDING,
        )

        if pickup_status not in TripAttendance.PickupStatus.values:

            return CustomResponse.errorResponse(
                description="Invalid pickup status."
            )

        drop_status = request.data.get(
            "drop_status",
            TripAttendance.DropStatus.PENDING,
        )

        if drop_status not in TripAttendance.DropStatus.values:

            return CustomResponse.errorResponse(
                description="Invalid drop status."
            )

        try:

            with transaction.atomic():

                attendance = TripAttendance.objects.create(
                    school=school,
                    branch=branch,
                    trip=trip,
                    student=student,
                    pickup_status=pickup_status,
                    pickup_time=request.data.get("pickup_time"),
                    drop_status=drop_status,
                    drop_time=request.data.get("drop_time"),
                    remarks=request.data.get("remarks"),
                )

        except Exception as e:

            application_logger.exception(
                "trip_attendance_create_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                trip_id=str(trip.id),
                student_id=str(student.id),
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description=str(e),
            )

        application_logger.info(
            "trip_attendance_created",
            requested_by=str(request.user.id),
            school_id=str(school.id),
            attendance_id=str(attendance.id),
        )

        return CustomResponse.successResponse(
            description="Trip attendance created successfully.",
            data={
                "id": str(attendance.id),
                "student": student.name,
                "trip_date": trip.trip_date,
                "vehicle": trip.vehicle_assignment.vehicle.vehicle_number,
                "pickup_status": attendance.pickup_status,
                "drop_status": attendance.drop_status,
            },
        )


class TripAttendanceListAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "trip.attendance.view"

    def get(self, request):

        school = request.school

        trip_id = request.GET.get("trip_id")
        student_id = request.GET.get("student_id")
        pickup_status = request.GET.get("pickup_status")
        drop_status = request.GET.get("drop_status")
        search = request.GET.get("search", "").strip()

        application_logger.info(
            "trip_attendance_list_requested",
            requested_by=str(request.user.id),
            school_id=str(school.id) if school else None,
            trip_id=trip_id,
            student_id=student_id,
        )

        if school is None:

            application_logger.warning(
                "trip_attendance_list_failed",
                requested_by=str(request.user.id),
                reason="school_not_found",
            )

            return CustomResponse.errorResponse(
                description="School not found."
            )

        try:

            attendances = TripAttendance.objects.select_related(
                "branch",
                "trip",
                "trip__vehicle_assignment",
                "trip__vehicle_assignment__vehicle",
                "trip__vehicle_assignment__route",
                "student",
            ).filter(
                school=school,
            )

            if trip_id:

                attendances = attendances.filter(
                    trip_id=trip_id,
                )

            if student_id:

                attendances = attendances.filter(
                    student_id=student_id,
                )

            if pickup_status:

                attendances = attendances.filter(
                    pickup_status=pickup_status,
                )

            if drop_status:

                attendances = attendances.filter(
                    drop_status=drop_status,
                )

            if search:

                attendances = attendances.filter(
                    Q(student__name__icontains=search)
                    | Q(student__admission_number__icontains=search)
                    | Q(
                        trip__vehicle_assignment__vehicle__vehicle_number__icontains=search
                    )
                    | Q(
                        trip__vehicle_assignment__route__route_name__icontains=search
                    )
                )

            attendances = attendances.order_by(
                "-trip__trip_date",
                "student__name",
            )

            data = []

            for attendance in attendances:

                data.append({

                    "id": str(attendance.id),

                    "student": {
                        "id": str(attendance.student.id),
                        "name": attendance.student.name,
                        "admission_number": attendance.student.admission_number,
                    },

                    "trip": {
                        "id": str(attendance.trip.id),
                        "trip_date": attendance.trip.trip_date,
                        "shift": attendance.trip.shift,
                    },

                    "vehicle": {
                        "id": str(attendance.trip.vehicle_assignment.vehicle.id),
                        "vehicle_number": attendance.trip.vehicle_assignment.vehicle.vehicle_number,
                    },

                    "route": {
                        "id": str(attendance.trip.vehicle_assignment.route.id),
                        "route_name": attendance.trip.vehicle_assignment.route.route_name,
                    },

                    "pickup_status": attendance.pickup_status,
                    "pickup_status_display": attendance.get_pickup_status_display(),
                    "pickup_time": attendance.pickup_time,

                    "drop_status": attendance.drop_status,
                    "drop_status_display": attendance.get_drop_status_display(),
                    "drop_time": attendance.drop_time,

                    "remarks": attendance.remarks,

                    "created_at": attendance.created_at,
                    "updated_at": attendance.updated_at,
                })

        except Exception as e:

            application_logger.exception(
                "trip_attendance_list_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description=str(e),
            )

        application_logger.info(
            "trip_attendance_list_fetched",
            requested_by=str(request.user.id),
            school_id=str(school.id),
            returned_count=len(data),
        )

        return CustomResponse.successResponse(
            description="Trip attendance fetched successfully.",
            total=len(data),
            data=data,
        )


class UpdateTripAttendanceAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "trip.attendance.update"

    def put(self, request, attendance_id):

        school = request.school

        application_logger.info(
            "trip_attendance_update_requested",
            requested_by=str(request.user.id),
            school_id=str(school.id) if school else None,
            attendance_id=str(attendance_id),
        )

        if school is None:

            application_logger.warning(
                "trip_attendance_update_failed",
                requested_by=str(request.user.id),
                reason="school_not_found",
            )

            return CustomResponse.errorResponse(
                description="School not found."
            )

        attendance = TripAttendance.objects.select_related(
            "trip",
            "trip__vehicle_assignment",
            "student",
            "branch",
        ).filter(
            id=attendance_id,
            school=school,
        ).first()

        if attendance is None:

            application_logger.warning(
                "trip_attendance_update_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                attendance_id=str(attendance_id),
                reason="attendance_not_found",
            )

            return CustomResponse.errorResponse(
                description="Trip attendance not found."
            )

        branch = attendance.branch

        if "branch_id" in request.data:

            branch_id = request.data.get("branch_id")

            if branch_id:

                branch = Branch.objects.filter(
                    id=branch_id,
                    school=school,
                ).first()

                if branch is None:

                    application_logger.warning(
                        "trip_attendance_update_failed",
                        requested_by=str(request.user.id),
                        school_id=str(school.id),
                        branch_id=branch_id,
                        reason="branch_not_found",
                    )

                    return CustomResponse.errorResponse(
                        description="Branch not found."
                    )

            else:

                branch = None

        if "pickup_status" in request.data:

            pickup_status = request.data.get("pickup_status")

            if pickup_status not in TripAttendance.PickupStatus.values:

                application_logger.warning(
                    "trip_attendance_update_failed",
                    requested_by=str(request.user.id),
                    school_id=str(school.id),
                    pickup_status=pickup_status,
                    reason="invalid_pickup_status",
                )

                return CustomResponse.errorResponse(
                    description="Invalid pickup status."
                )

            attendance.pickup_status = pickup_status

        if "drop_status" in request.data:

            drop_status = request.data.get("drop_status")

            if drop_status not in TripAttendance.DropStatus.values:

                application_logger.warning(
                    "trip_attendance_update_failed",
                    requested_by=str(request.user.id),
                    school_id=str(school.id),
                    drop_status=drop_status,
                    reason="invalid_drop_status",
                )

                return CustomResponse.errorResponse(
                    description="Invalid drop status."
                )

            attendance.drop_status = drop_status

        if "pickup_time" in request.data:
            attendance.pickup_time = request.data.get("pickup_time")

        if "drop_time" in request.data:
            attendance.drop_time = request.data.get("drop_time")

        if "remarks" in request.data:
            attendance.remarks = request.data.get("remarks")

        attendance.branch = branch

        try:

            with transaction.atomic():

                attendance.save()

        except Exception as e:

            application_logger.exception(
                "trip_attendance_update_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                attendance_id=str(attendance.id),
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description=str(e),
            )

        application_logger.info(
            "trip_attendance_updated",
            requested_by=str(request.user.id),
            school_id=str(school.id),
            attendance_id=str(attendance.id),
        )

        return CustomResponse.successResponse(
            description="Trip attendance updated successfully.",
            data={
                "id": str(attendance.id),
                "student": attendance.student.name,
                "trip_date": attendance.trip.trip_date,
                "pickup_status": attendance.pickup_status,
                "pickup_time": attendance.pickup_time,
                "drop_status": attendance.drop_status,
                "drop_time": attendance.drop_time,
                "remarks": attendance.remarks,
            },
        )

class UpdateLiveLocationAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):

        school = request.school

        application_logger.info(
            "live_location_update_requested",
            requested_by=str(request.user.id),
            school_id=str(school.id) if school else None,
        )

        if school is None:

            application_logger.warning(
                "live_location_update_failed",
                requested_by=str(request.user.id),
                reason="school_not_found",
            )

            return CustomResponse.errorResponse(
                description="School not found."
            )

        required_fields = [
            "trip_id",
            "latitude",
            "longitude",
        ]

        for field in required_fields:

            if request.data.get(field) in [None, ""]:

                application_logger.warning(
                    "live_location_update_failed",
                    requested_by=str(request.user.id),
                    school_id=str(school.id),
                    field=field,
                    reason="required_field_missing",
                )

                return CustomResponse.errorResponse(
                    description=f"{field} is required."
                )

        trip = Trip.objects.select_related(
            "vehicle_assignment",
            "vehicle_assignment__driver",
            "vehicle_assignment__vehicle",
        ).filter(
            id=request.data.get("trip_id"),
            school=school,
        ).first()

        if trip is None:

            application_logger.warning(
                "live_location_update_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                trip_id=request.data.get("trip_id"),
                reason="trip_not_found",
            )

            return CustomResponse.errorResponse(
                description="Trip not found."
            )

        if trip.status != Trip.Status.STARTED:

            application_logger.warning(
                "live_location_update_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                trip_id=str(trip.id),
                reason="trip_not_started",
            )

            return CustomResponse.errorResponse(
                description="Trip is not active."
            )

        assignment = trip.vehicle_assignment

        if (
            assignment.driver
            and assignment.driver.user != request.user
        ):

            application_logger.warning(
                "live_location_update_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                trip_id=str(trip.id),
                reason="driver_mismatch",
            )

            return CustomResponse.errorResponse(
                description="You are not assigned to this trip."
            )

        try:

            live_location = update_live_location(
                school=school,
                trip=trip,
                latitude=request.data.get("latitude"),
                longitude=request.data.get("longitude"),
                speed=request.data.get("speed", 0),
                heading=request.data.get("heading"),
                altitude=request.data.get("altitude"),
                accuracy=request.data.get("accuracy"),
                source=request.data.get(
                    "source",
                    LiveLocation.LocationSource.MOBILE,
                ),
                device_timestamp=request.data.get(
                    "device_timestamp",
                ),
            )

        except Exception as e:

            application_logger.exception(
                "live_location_update_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                trip_id=str(trip.id),
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description="Unable to update live location."
            )

        application_logger.info(
            "live_location_updated",
            requested_by=str(request.user.id),
            school_id=str(school.id),
            trip_id=str(trip.id),
        )

        return CustomResponse.successResponse(
            description="Live location updated successfully.",
            data={
                "trip_id": str(trip.id),
                "latitude": live_location.latitude,
                "longitude": live_location.longitude,
                "speed": live_location.speed,
                "recorded_at": live_location.recorded_at,
            },
        )


class LiveLocationAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        school = request.school

        trip_id = request.GET.get("trip_id")

        application_logger.info(
            "live_location_fetch_requested",
            requested_by=str(request.user.id),
            school_id=str(school.id) if school else None,
            trip_id=trip_id,
        )

        if school is None:

            return CustomResponse.errorResponse(
                description="School not found."
            )

        if not trip_id:

            return CustomResponse.errorResponse(
                description="trip_id is required."
            )

        trip = Trip.objects.filter(
            id=trip_id,
            school=school,
        ).first()

        if trip is None:

            application_logger.warning(
                "live_location_fetch_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                trip_id=trip_id,
                reason="trip_not_found",
            )

            return CustomResponse.errorResponse(
                description="Trip not found."
            )

        live_location = LiveLocation.objects.filter(
            trip=trip,
        ).first()

        if live_location is None:

            application_logger.warning(
                "live_location_fetch_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                trip_id=str(trip.id),
                reason="live_location_not_found",
            )

            return CustomResponse.errorResponse(
                description="Live location not available."
            )

        application_logger.info(
            "live_location_fetched",
            requested_by=str(request.user.id),
            school_id=str(school.id),
            trip_id=str(trip.id),
        )

        return CustomResponse.successResponse(
            description="Live location fetched successfully.",
            data={
                "trip": {
                    "id": str(trip.id),
                    "trip_date": trip.trip_date,
                    "shift": trip.shift,
                    "status": trip.status,
                },
                "vehicle": {
                    "id": str(trip.vehicle_assignment.vehicle.id),
                    "vehicle_number": trip.vehicle_assignment.vehicle.vehicle_number,
                },
                "route": {
                    "id": str(trip.vehicle_assignment.route.id),
                    "route_name": trip.vehicle_assignment.route.route_name,
                },
                "driver": {
                    "id": str(trip.vehicle_assignment.driver.id),
                    "name": trip.vehicle_assignment.driver.name,
                    "mobile": trip.vehicle_assignment.driver.mobile,
                },
                "location": {
                    "latitude": live_location.latitude,
                    "longitude": live_location.longitude,
                    "speed": live_location.speed,
                    "heading": live_location.heading,
                    "altitude": live_location.altitude,
                    "accuracy": live_location.accuracy,
                    "source": live_location.source,
                    "device_timestamp": live_location.device_timestamp,
                    "recorded_at": live_location.recorded_at,
                },
            },
        )



class LocationHistoryAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        school = request.school

        trip_id = request.GET.get("trip_id")
        start_time = request.GET.get("start_time")
        end_time = request.GET.get("end_time")

        application_logger.info(
            "location_history_fetch_requested",
            requested_by=str(request.user.id),
            school_id=str(school.id) if school else None,
            trip_id=trip_id,
        )

        if school is None:

            return CustomResponse.errorResponse(
                description="School not found."
            )

        if not trip_id:

            return CustomResponse.errorResponse(
                description="trip_id is required."
            )

        trip = Trip.objects.filter(
            id=trip_id,
            school=school,
        ).first()

        if trip is None:

            application_logger.warning(
                "location_history_fetch_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                trip_id=trip_id,
                reason="trip_not_found",
            )

            return CustomResponse.errorResponse(
                description="Trip not found."
            )

        queryset = LocationHistory.objects.filter(
            trip=trip,
        )

        if start_time:

            queryset = queryset.filter(
                recorded_at__gte=start_time,
            )

        if end_time:

            queryset = queryset.filter(
                recorded_at__lte=end_time,
            )

        queryset = queryset.order_by(
            "recorded_at",
        )

        data = []

        for location in queryset:

            data.append({
                "id": str(location.id),
                "latitude": location.latitude,
                "longitude": location.longitude,
                "speed": location.speed,
                "heading": location.heading,
                "altitude": location.altitude,
                "accuracy": location.accuracy,
                "source": location.source,
                "device_timestamp": location.device_timestamp,
                "recorded_at": location.recorded_at,
            })

        application_logger.info(
            "location_history_fetched",
            requested_by=str(request.user.id),
            school_id=str(school.id),
            trip_id=str(trip.id),
            total_count=len(data),
        )

        return CustomResponse.successResponse(
            description="Location history fetched successfully.",
            total=len(data),
            data={
                "trip": {
                    "id": str(trip.id),
                    "trip_date": trip.trip_date,
                    "shift": trip.shift,
                    "status": trip.status,
                },
                "locations": data,
            },
        )

class StartTripAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "trip.start"

    def post(self, request, trip_id):

        school = request.school

        application_logger.info(
            "trip_start_requested",
            requested_by=str(request.user.id),
            school_id=str(school.id) if school else None,
            trip_id=str(trip_id),
        )

        if school is None:

            return CustomResponse.errorResponse(
                description="School not found."
            )

        trip = Trip.objects.select_related(
            "vehicle_assignment",
        ).filter(
            id=trip_id,
            school=school,
        ).first()

        if trip is None:

            application_logger.warning(
                "trip_start_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                trip_id=str(trip_id),
                reason="trip_not_found",
            )

            return CustomResponse.errorResponse(
                description="Trip not found."
            )

        if trip.status != Trip.Status.SCHEDULED:

            application_logger.warning(
                "trip_start_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                trip_id=str(trip.id),
                reason="trip_already_started",
            )

            return CustomResponse.errorResponse(
                description="Trip has already been started."
            )

        try:

            with transaction.atomic():

                trip.status = Trip.Status.STARTED
                trip.actual_start_time = timezone.now()

                if request.data.get("start_odometer"):

                    trip.start_odometer = request.data.get(
                        "start_odometer"
                    )

                trip.save(
                    update_fields=[
                        "status",
                        "actual_start_time",
                        "start_odometer",
                        "updated_at",
                    ]
                )

                TripEvent.objects.create(
                    school=school,
                    branch=trip.branch,
                    trip=trip,
                    event_type=TripEvent.EventType.TRIP_STARTED,
                    event_time=timezone.now(),
                    remarks="Trip started.",
                )

        except Exception as e:

            application_logger.exception(
                "trip_start_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                trip_id=str(trip.id),
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description=str(e),
            )

        application_logger.info(
            "trip_started",
            requested_by=str(request.user.id),
            school_id=str(school.id),
            trip_id=str(trip.id),
        )

        return CustomResponse.successResponse(
            description="Trip started successfully.",
            data={
                "trip_id": str(trip.id),
                "status": trip.status,
                "actual_start_time": trip.actual_start_time,
                "start_odometer": trip.start_odometer,
            },
        )


class EndTripAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "trip.end"

    def post(self, request, trip_id):

        school = request.school

        application_logger.info(
            "trip_end_requested",
            requested_by=str(request.user.id),
            school_id=str(school.id) if school else None,
            trip_id=str(trip_id),
        )

        if school is None:

            return CustomResponse.errorResponse(
                description="School not found."
            )

        trip = Trip.objects.select_related(
            "vehicle_assignment",
        ).filter(
            id=trip_id,
            school=school,
        ).first()

        if trip is None:

            application_logger.warning(
                "trip_end_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                trip_id=str(trip_id),
                reason="trip_not_found",
            )

            return CustomResponse.errorResponse(
                description="Trip not found."
            )

        if trip.status != Trip.Status.STARTED:

            application_logger.warning(
                "trip_end_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                trip_id=str(trip.id),
                reason="trip_not_started",
            )

            return CustomResponse.errorResponse(
                description="Trip is not in progress."
            )

        end_odometer = request.data.get("end_odometer")

        try:

            with transaction.atomic():

                trip.actual_end_time = timezone.now()
                trip.status = Trip.Status.COMPLETED

                if end_odometer is not None:

                    end_odometer = int(end_odometer)

                    if (
                        trip.start_odometer is not None
                        and end_odometer < trip.start_odometer
                    ):

                        return CustomResponse.errorResponse(
                            description="End odometer cannot be less than start odometer."
                        )

                    trip.end_odometer = end_odometer

                    if trip.start_odometer is not None:

                        trip.total_distance = (
                            end_odometer
                            - trip.start_odometer
                        )

                if "remarks" in request.data:
                    trip.remarks = request.data.get("remarks")

                trip.save(
                    update_fields=[
                        "actual_end_time",
                        "end_odometer",
                        "total_distance",
                        "status",
                        "remarks",
                        "updated_at",
                    ]
                )

                TripEvent.objects.create(
                    school=school,
                    branch=trip.branch,
                    trip=trip,
                    event_type=TripEvent.EventType.TRIP_COMPLETED,
                    event_time=timezone.now(),
                    remarks="Trip completed.",
                )

        except Exception as e:

            application_logger.exception(
                "trip_end_failed",
                requested_by=str(request.user.id),
                school_id=str(school.id),
                trip_id=str(trip.id),
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description=str(e),
            )

        application_logger.info(
            "trip_completed",
            requested_by=str(request.user.id),
            school_id=str(school.id),
            trip_id=str(trip.id),
        )

        return CustomResponse.successResponse(
            description="Trip completed successfully.",
            data={
                "trip_id": str(trip.id),
                "status": trip.status,
                "actual_end_time": trip.actual_end_time,
                "start_odometer": trip.start_odometer,
                "end_odometer": trip.end_odometer,
                "total_distance": trip.total_distance,
            },
        )