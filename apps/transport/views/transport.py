from django.db.models import Prefetch
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.school.models.school import Student
from apps.transport.models import StudentTransport, LiveLocation, RouteStop, VehicleDocument
from shared.mixins import CustomResponse
from shared.utils.logger import application_logger


class StudentBusAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        student_id = request.query_params.get("student_id")

        try:
            school = request.school

            application_logger.info(
                "student_transport_details_started",
                user_id=str(user.id),
                student_id=str(student_id) if student_id else None,
                school_id=str(school.id) if school else None,
            )

            if not school:
                return CustomResponse.errorResponse(
                    description="School is required."
                )

            if not student_id:
                return CustomResponse.errorResponse(
                    description="student_id is required."
                )

            # Get student
            student = (
                Student.objects
                .select_related(
                    "school",
                    "branch",
                    "academic_year",
                )
                .filter(
                    id=student_id,
                    school=school,
                    status=Student.Status.ACTIVE,
                )
                .first()
            )

            if student is None:
                application_logger.warning(
                    "student_transport_details_failed",
                    user_id=str(user.id),
                    student_id=str(student_id),
                    school_id=str(school.id),
                    reason="student_not_found",
                )

                return CustomResponse.errorResponse(
                    description="Student not found."
                )

            # Get complete transport assignment
            student_transport = (
                StudentTransport.objects
                .select_related(
                    "vehicle_assignment",
                    "vehicle_assignment__vehicle",
                    "vehicle_assignment__driver",
                    "vehicle_assignment__attendant",
                    "vehicle_assignment__route",
                    "pickup_stop",
                    "drop_stop",
                )
                .prefetch_related(
                    Prefetch(
                        "vehicle_assignment__vehicle__documents",
                        queryset=VehicleDocument.objects.filter(
                            document_type=VehicleDocument.DocumentType.PHOTO,
                        ),
                        to_attr="photo_documents",
                    )
                )
                .filter(
                    student=student,
                    school=school,
                    status=StudentTransport.Status.ACTIVE,
                )
                .first()
            )

            if student_transport is None:
                application_logger.warning(
                    "student_transport_details_failed",
                    user_id=str(user.id),
                    student_id=str(student.id),
                    school_id=str(school.id),
                    reason="transport_assignment_not_found",
                )

                return CustomResponse.errorResponse(
                    description="Transport assignment not found for this student."
                )


            vehicle_assignment = student_transport.vehicle_assignment

            if vehicle_assignment is None:
                return CustomResponse.errorResponse(
                    description="Vehicle assignment not found."
                )

            vehicle = vehicle_assignment.vehicle
            driver = vehicle_assignment.driver
            attendant = vehicle_assignment.attendant
            route = vehicle_assignment.route

            if vehicle is None:
                return CustomResponse.errorResponse(
                    description="Vehicle not found."
                )
            vehicle = vehicle_assignment.vehicle

            bus_photo = (
                str(vehicle.photo_documents[0].document_file.url)
                if vehicle.photo_documents
                   and vehicle.photo_documents[0].document_file
                else None
            )

            if route is None:
                application_logger.warning(
                    "student_transport_details_failed",
                    user_id=str(user.id),
                    student_id=str(student.id),
                    school_id=str(school.id),
                    reason="route_not_found",
                )

                return CustomResponse.errorResponse(
                    description="Route not found."
                )

            # Get all stops belonging to the route
            route_stops = (
                RouteStop.objects
                .select_related("stop")
                .filter(
                    route=route,
                )
                .order_by("stop_order")
            )

            route_stops_data = [
                {
                    "id": str(route_stop.stop.id),
                    "stop_name": route_stop.stop.stop_name,
                    "stop_code": route_stop.stop.stop_code,
                    "stop_type": route_stop.stop.stop_type,
                    "stop_order": route_stop.stop_order,
                    "landmark": route_stop.stop.landmark,
                    "address": route_stop.stop.address,
                    "latitude": route_stop.stop.latitude,
                    "longitude": route_stop.stop.longitude,
                    "pickup_time": route_stop.pickup_time,
                    "drop_time": route_stop.drop_time,
                    "distance_from_previous_stop": (
                        route_stop.distance_from_previous_stop
                    ),
                    "estimated_travel_time": (
                        route_stop.estimated_travel_time
                    ),
                }
                for route_stop in route_stops
            ]

            pickup_stop = student_transport.pickup_stop
            drop_stop = student_transport.drop_stop

            application_logger.info(
                "student_transport_details_retrieved",
                user_id=str(user.id),
                student_id=str(student.id),
                school_id=str(school.id),
                vehicle_id=str(vehicle.id),
                vehicle_assignment_id=str(vehicle_assignment.id),
                route_id=str(route.id),
                route_stop_count=len(route_stops_data),
            )

            return CustomResponse.successResponse(
                description="Student transport details retrieved successfully.",
                data={
                    "student": {
                        "id": str(student.id),
                        "name": student.name,
                    },

                    "bus": {
                        "id": str(vehicle.id),
                        "vehicle_number": vehicle.vehicle_number,
                        "vehicle_type": vehicle.vehicle_type,
                        "capacity": vehicle.capacity,
                        "status": vehicle.status,
                        "photo":bus_photo
                    },

                    "driver": {
                        "id": str(driver.id) if driver else None,
                        "name": driver.name if driver else None,
                        "mobile": driver.mobile if driver else None,
                        "experience": driver.experience if driver else None,
                        "profile_image": (
                            driver.profile_image
                            if driver
                            else None
                        ),
                    },

                    "attendant": {
                        "id": str(attendant.id) if attendant else None,
                        "name": attendant.name if attendant else None,
                        "mobile": attendant.mobile if attendant else None,
                        "experience": (
                            attendant.experience
                            if attendant
                            else None
                        ),
                        "profile_image": (
                            attendant.profile_image
                            if attendant
                            else None
                        ),
                    },

                    "route": {
                        "id": str(route.id),
                        "route_code": route.route_code,
                        "route_name": route.route_name,
                        "source": route.source,
                        "destination": route.destination,
                        "total_distance": route.total_distance,
                        "estimated_duration": route.estimated_duration,
                        "shift": route.shift,
                        "status": route.status,
                    },

                    "pickup_stop": {
                        "id": (
                            str(pickup_stop.id)
                            if pickup_stop
                            else None
                        ),
                        "stop_name": (
                            pickup_stop.stop_name
                            if pickup_stop
                            else None
                        ),
                        "stop_code": (
                            pickup_stop.stop_code
                            if pickup_stop
                            else None
                        ),
                        "landmark": (
                            pickup_stop.landmark
                            if pickup_stop
                            else None
                        ),
                        "address": (
                            pickup_stop.address
                            if pickup_stop
                            else None
                        ),
                        "latitude": (
                            pickup_stop.latitude
                            if pickup_stop
                            else None
                        ),
                        "longitude": (
                            pickup_stop.longitude
                            if pickup_stop
                            else None
                        ),
                        "pickup_time": (
                            pickup_stop.pickup_time
                            if pickup_stop
                            else None
                        ),
                    },

                    "drop_stop": {
                        "id": (
                            str(drop_stop.id)
                            if drop_stop
                            else None
                        ),
                        "stop_name": (
                            drop_stop.stop_name
                            if drop_stop
                            else None
                        ),
                        "stop_code": (
                            drop_stop.stop_code
                            if drop_stop
                            else None
                        ),
                        "landmark": (
                            drop_stop.landmark
                            if drop_stop
                            else None
                        ),
                        "address": (
                            drop_stop.address
                            if drop_stop
                            else None
                        ),
                        "latitude": (
                            drop_stop.latitude
                            if drop_stop
                            else None
                        ),
                        "longitude": (
                            drop_stop.longitude
                            if drop_stop
                            else None
                        ),
                        "drop_time": (
                            drop_stop.drop_time
                            if drop_stop
                            else None
                        ),
                    },

                    "route_stops": route_stops_data,

                    "trip_type": student_transport.trip_type,
                },
            )

        except Exception as e:
            application_logger.exception(
                "student_transport_details_failed",
                user_id=str(user.id),
                student_id=(
                    str(student_id)
                    if student_id
                    else None
                ),
                school_id=(
                    str(school.id)
                    if school
                    else None
                ),
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description="Internal server error.",
            )

class StudentRouteAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        student_id = request.query_params.get("student_id")

        try:
            school = request.school

            application_logger.info(
                "student_route_started",
                user_id=str(user.id),
                student_id=str(student_id) if student_id else None,
                school_id=str(school.id) if school else None,
            )

            if not school:
                return CustomResponse.errorResponse(
                    description="School is required."
                )

            if not student_id:
                return CustomResponse.errorResponse(
                    description="student_id is required."
                )

            student = (
                Student.objects
                .select_related(
                    "school",
                    "branch",
                    "academic_year",
                )
                .filter(
                    id=student_id,
                    school=school,
                    status=Student.Status.ACTIVE,
                )
                .first()
            )

            if student is None:
                application_logger.warning(
                    "student_route_failed",
                    user_id=str(user.id),
                    student_id=str(student_id),
                    school_id=str(school.id),
                    reason="student_not_found",
                )

                return CustomResponse.errorResponse(
                    description="Student not found."
                )

            student_transport = (
                StudentTransport.objects
                .select_related(
                    "vehicle_assignment",
                    "vehicle_assignment__route",
                    "pickup_stop",
                    "drop_stop",
                )
                .filter(
                    student=student,
                    school=school,
                    status=StudentTransport.Status.ACTIVE,
                )
                .first()
            )

            if student_transport is None:
                application_logger.warning(
                    "student_route_failed",
                    user_id=str(user.id),
                    student_id=str(student.id),
                    school_id=str(school.id),
                    reason="transport_assignment_not_found",
                )

                return CustomResponse.errorResponse(
                    description="Transport assignment not found for this student."
                )

            vehicle_assignment = student_transport.vehicle_assignment

            if vehicle_assignment is None:
                return CustomResponse.errorResponse(
                    description="Vehicle assignment not found."
                )

            route = vehicle_assignment.route

            if route is None:
                application_logger.warning(
                    "student_route_failed",
                    user_id=str(user.id),
                    student_id=str(student.id),
                    school_id=str(school.id),
                    reason="route_not_found",
                )

                return CustomResponse.errorResponse(
                    description="Route not found."
                )

            pickup_stop = student_transport.pickup_stop
            drop_stop = student_transport.drop_stop

            # Get all stops belonging to this route
            route_stops = (
                RouteStop.objects
                .select_related("stop")
                .filter(
                    route=route,
                )
                .order_by("stop_order")
            )

            route_stops_data = [
                {
                    "id": str(route_stop.stop.id),
                    "stop_name": route_stop.stop.stop_name,
                    "stop_code": route_stop.stop.stop_code,
                    "stop_type": route_stop.stop.stop_type,
                    "stop_order": route_stop.stop_order,
                    "landmark": route_stop.stop.landmark,
                    "address": route_stop.stop.address,
                    "latitude": route_stop.stop.latitude,
                    "longitude": route_stop.stop.longitude,
                    "pickup_time": route_stop.pickup_time,
                    "drop_time": route_stop.drop_time,
                    "distance_from_previous_stop": (
                        route_stop.distance_from_previous_stop
                    ),
                    "estimated_travel_time": (
                        route_stop.estimated_travel_time
                    ),
                }
                for route_stop in route_stops
            ]

            application_logger.info(
                "student_route_retrieved",
                user_id=str(user.id),
                student_id=str(student.id),
                school_id=str(school.id),
                route_id=str(route.id),
                student_transport_id=str(student_transport.id),
                route_stop_count=len(route_stops_data),
            )

            return CustomResponse.successResponse(
                description="Student route details retrieved successfully.",
                data={
                    "route": {
                        "id": str(route.id),
                        "route_code": route.route_code,
                        "route_name": route.route_name,
                        "source": route.source,
                        "destination": route.destination,
                        "total_distance": route.total_distance,
                        "estimated_duration": route.estimated_duration,
                        "shift": route.shift,
                        "status": route.status,
                    },

                    "pickup_stop": {
                        "id": str(pickup_stop.id)
                        if pickup_stop else None,
                        "stop_name": pickup_stop.stop_name
                        if pickup_stop else None,
                        "stop_code": pickup_stop.stop_code
                        if pickup_stop else None,
                        "landmark": pickup_stop.landmark
                        if pickup_stop else None,
                        "address": pickup_stop.address
                        if pickup_stop else None,
                        "latitude": pickup_stop.latitude
                        if pickup_stop else None,
                        "longitude": pickup_stop.longitude
                        if pickup_stop else None,
                        "pickup_time": pickup_stop.pickup_time
                        if pickup_stop else None,
                    },

                    "drop_stop": {
                        "id": str(drop_stop.id)
                        if drop_stop else None,
                        "stop_name": drop_stop.stop_name
                        if drop_stop else None,
                        "stop_code": drop_stop.stop_code
                        if drop_stop else None,
                        "landmark": drop_stop.landmark
                        if drop_stop else None,
                        "address": drop_stop.address
                        if drop_stop else None,
                        "latitude": drop_stop.latitude
                        if drop_stop else None,
                        "longitude": drop_stop.longitude
                        if drop_stop else None,
                        "drop_time": drop_stop.drop_time
                        if drop_stop else None,
                    },

                    "route_stops": route_stops_data,

                    "trip_type": student_transport.trip_type,
                },
            )

        except Exception as e:
            application_logger.exception(
                "student_route_failed",
                user_id=str(user.id),
                student_id=str(student_id) if student_id else None,
                school_id=str(school.id) if school else None,
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description="Internal server error.",
            )



class StudentLiveLocationAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        student_id = request.query_params.get("student_id")

        try:
            school = request.school

            application_logger.info(
                "student_live_location_started",
                user_id=str(user.id),
                student_id=str(student_id) if student_id else None,
                school_id=str(school.id) if school else None,
            )

            if not school:
                return CustomResponse.errorResponse(
                    description="School is required."
                )

            if not student_id:
                return CustomResponse.errorResponse(
                    description="student_id is required."
                )

            student = (
                Student.objects
                .select_related(
                    "school",
                    "branch",
                )
                .filter(
                    id=student_id,
                    school=school,
                    status=Student.Status.ACTIVE,
                )
                .first()
            )

            if student is None:
                application_logger.warning(
                    "student_live_location_failed",
                    user_id=str(user.id),
                    student_id=str(student_id),
                    school_id=str(school.id),
                    reason="student_not_found",
                )

                return CustomResponse.errorResponse(
                    description="Student not found."
                )

            student_transport = (
                StudentTransport.objects
                .select_related(
                    "vehicle_assignment",
                    "vehicle_assignment__vehicle",
                )
                .filter(
                    student=student,
                    school=school,
                    status=StudentTransport.Status.ACTIVE,
                )
                .first()
            )

            if student_transport is None:
                application_logger.warning(
                    "student_live_location_failed",
                    user_id=str(user.id),
                    student_id=str(student.id),
                    school_id=str(school.id),
                    reason="transport_assignment_not_found",
                )

                return CustomResponse.errorResponse(
                    description="Transport assignment not found for this student."
                )

            vehicle_assignment = student_transport.vehicle_assignment

            if vehicle_assignment is None:
                return CustomResponse.errorResponse(
                    description="Vehicle assignment not found."
                )

            vehicle = vehicle_assignment.vehicle

            if vehicle is None:
                return CustomResponse.errorResponse(
                    description="Vehicle not found."
                )

            # Get the latest live location for the assigned vehicle
            live_location = (
                LiveLocation.objects
                .select_related(
                    "trip",
                    "trip__vehicle_assignment",
                    "trip__vehicle_assignment__vehicle",
                )
                .filter(
                    school=school,
                    trip__vehicle_assignment__vehicle=vehicle,
                )
                .order_by("-device_timestamp")
                .first()
            )

            if live_location is None:
                application_logger.warning(
                    "student_live_location_failed",
                    user_id=str(user.id),
                    student_id=str(student.id),
                    school_id=str(school.id),
                    vehicle_id=str(vehicle.id),
                    reason="live_location_not_found",
                )

                return CustomResponse.successResponse(
                    description="Live location not available.",
                    data={
                        "vehicle": {
                            "id": str(vehicle.id),
                            "vehicle_number": vehicle.vehicle_number,
                        },
                        "is_available": False,
                        "location": None,
                    },
                )

            trip = live_location.trip

            application_logger.info(
                "student_live_location_retrieved",
                user_id=str(user.id),
                student_id=str(student.id),
                school_id=str(school.id),
                vehicle_id=str(vehicle.id),
                trip_id=str(trip.id) if trip else None,
                live_location_id=str(live_location.id),
            )

            return CustomResponse.successResponse(
                description="Live location retrieved successfully.",
                data={
                    "vehicle": {
                        "id": str(vehicle.id),
                        "vehicle_number": vehicle.vehicle_number,
                    },
                    "trip": {
                        "id": str(trip.id) if trip else None,
                        "status": trip.status if trip else None,
                    },
                    "is_available": True,
                    "location": {
                        "latitude": live_location.latitude,
                        "longitude": live_location.longitude,
                        "speed": live_location.speed,
                        "heading": live_location.heading,
                        "altitude": live_location.altitude,
                        "accuracy": live_location.accuracy,
                        "device_timestamp": live_location.device_timestamp,
                    },
                },
            )

        except Exception as e:
            application_logger.exception(
                "student_live_location_failed",
                user_id=str(user.id),
                student_id=str(student_id) if student_id else None,
                school_id=str(school.id) if school else None,
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description="Internal server error.",
            )