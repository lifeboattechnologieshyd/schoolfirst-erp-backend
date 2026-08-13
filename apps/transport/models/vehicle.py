import uuid

from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models

from apps.school.models import School
from apps.school.models.school import Branch, Staff, AcademicYear, Student
from shared.managers import SoftDeleteManager
from shared.mixins import AuditModel


class Vehicle(AuditModel):

    class VehicleType(models.TextChoices):
        BUS = "BUS", "Bus"
        MINI_BUS = "MINI_BUS", "Mini Bus"
        VAN = "VAN", "Van"
        TEMPO = "TEMPO", "Tempo Traveller"
        OTHER = "OTHER", "Other"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"
        MAINTENANCE = "MAINTENANCE", "Maintenance"
        OUT_OF_SERVICE = "OUT_OF_SERVICE", "Out of Service"

    objects = SoftDeleteManager()
    all_objects = models.Manager()
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)


    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name="vehicles"
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vehicles",
    )

    vehicle_number = models.CharField(
        max_length=30,
        unique=True
    )

    registration_number = models.CharField(
        max_length=30,
        unique=True
    )

    vehicle_type = models.CharField(
        max_length=20,
        choices=VehicleType.choices
    )

    capacity = models.PositiveIntegerField()

    model = models.CharField(max_length=100)

    manufacturer = models.CharField(max_length=100)

    chassis_number = models.CharField(
        max_length=100,
        unique=True
    )

    engine_number = models.CharField(
        max_length=100,
        unique=True
    )



    # gps_device = models.OneToOneField(
    #     "transport.GPSDevice",
    #     on_delete=models.SET_NULL,
    #     null=True,
    #     blank=True,
    #     related_name="vehicle"
    # )

    camera_installed = models.BooleanField(default=False)

    panic_button = models.BooleanField(default=False)

    rfid_reader = models.BooleanField(default=False)

    speed_limit = models.PositiveIntegerField(
        help_text="Maximum speed in km/h"
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE
    )

    class Meta:
        db_table = "transport_vehicle"
        ordering = ["vehicle_number"]
        verbose_name = "Vehicle"
        verbose_name_plural = "Vehicles"

    def __str__(self):
        return self.vehicle_number





class VehicleDocument(AuditModel):

    class DocumentType(models.TextChoices):
        RC_BOOK = "RC_BOOK", "RC Book"
        INSURANCE = "INSURANCE", "Insurance"
        FITNESS = "FITNESS", "Fitness Certificate"
        POLLUTION = "POLLUTION", "Pollution Certificate"
        PERMIT = "PERMIT", "Permit"
        ROAD_TAX = "ROAD_TAX", "Road Tax"
        OTHER = "OTHER", "Other"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        EXPIRED = "EXPIRED", "Expired"
        RENEWED = "RENEWED", "Renewed"

    objects = SoftDeleteManager()
    all_objects = models.Manager()
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)


    vehicle = models.ForeignKey(
        "transport.Vehicle",
        on_delete=models.CASCADE,
        related_name="documents"
    )

    document_type = models.CharField(
        max_length=30,
        choices=DocumentType.choices
    )

    document_number = models.CharField(
        max_length=100
    )

    issue_date = models.DateField(
        null=True,
        blank=True
    )

    expiry_date = models.DateField(
        null=True,
        blank=True
    )

    issued_by = models.CharField(
        max_length=255,
        blank=True
    )

    document_file = models.FileField(
        upload_to="transport/vehicle_documents/",
        null=True,
        blank=True
    )

    remarks = models.TextField(
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE
    )

    class Meta:
        db_table = "transport_vehicle_document"
        ordering = ["-expiry_date"]
        verbose_name = "Vehicle Document"
        verbose_name_plural = "Vehicle Documents"

    def __str__(self):
        return f"{self.vehicle.vehicle_number} - {self.get_document_type_display()}"


class Route(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Shift(models.TextChoices):
        MORNING = "MORNING", "Morning"
        AFTERNOON = "AFTERNOON", "Afternoon"
        EVENING = "EVENING", "Evening"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name="routes",
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="routes",
    )

    route_name = models.CharField(max_length=255)

    route_code = models.CharField(max_length=50)

    source = models.CharField(max_length=255)

    destination = models.CharField(max_length=255)

    total_distance = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
    )

    estimated_duration = models.PositiveIntegerField(
        help_text="Duration in minutes",
        null=True,
        blank=True,
    )

    shift = models.CharField(
        max_length=20,
        choices=Shift.choices,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    class Meta:
        db_table = "transport_routes"

        constraints = [
            models.UniqueConstraint(
                fields=["school", "route_code"],
                name="unique_route_code",
            )
        ]

        indexes = [
            models.Index(fields=["school"]),
            models.Index(fields=["status"]),
        ]

class Stop(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name="stops",
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stops",
    )

    stop_name = models.CharField(
        max_length=255,
    )

    stop_code = models.CharField(
        max_length=50,
    )

    landmark = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    address = models.TextField(
        null=True,
        blank=True,
    )

    latitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
    )

    longitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
    )

    pickup_time = models.TimeField(
        null=True,
        blank=True,
    )

    drop_time = models.TimeField(
        null=True,
        blank=True,
    )
    annual_transport_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    class Meta:
        db_table = "transport_stops"

        constraints = [
            models.UniqueConstraint(
                fields=["school", "stop_code"],
                name="unique_stop_code",
            ),
            models.UniqueConstraint(
                fields=["school", "stop_name"],
                name="unique_stop_name",
            ),
        ]

        indexes = [
            models.Index(fields=["school"]),
            models.Index(fields=["branch"]),
            models.Index(fields=["status"]),
            models.Index(fields=["stop_name"]),
        ]

    def __str__(self):
        return self.stop_name

class RouteStop(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    route = models.ForeignKey(
        "transport.Route",
        on_delete=models.CASCADE,
        related_name="route_stops",
    )

    stop = models.ForeignKey(
        "transport.Stop",
        on_delete=models.CASCADE,
        related_name="route_stops",
    )

    stop_order = models.PositiveSmallIntegerField()

    pickup_time = models.TimeField(
        null=True,
        blank=True,
    )

    drop_time = models.TimeField(
        null=True,
        blank=True,
    )

    distance_from_previous_stop = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0,
        help_text="Distance in kilometres",
    )

    estimated_travel_time = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Travel time from previous stop in minutes",
    )

    class Meta:
        db_table = "transport_route_stops"

        constraints = [
            models.UniqueConstraint(
                fields=["route", "stop"],
                name="unique_route_stop",
            ),
            models.UniqueConstraint(
                fields=["route", "stop_order"],
                name="unique_route_stop_order",
            ),
        ]

        indexes = [
            models.Index(fields=["route"]),
            models.Index(fields=["stop"]),
            models.Index(fields=["stop_order"]),
        ]

        ordering = ["route", "stop_order"]

    def __str__(self):
        return f"{self.route.route_name} - {self.stop.stop_name} ({self.stop_order})"

class VehicleAssignment(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name="vehicle_assignments",
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vehicle_assignments",
    )

    vehicle = models.ForeignKey(
        "transport.Vehicle",
        on_delete=models.CASCADE,
        related_name="assignments",
    )

    route = models.ForeignKey(
        "transport.Route",
        on_delete=models.CASCADE,
        related_name="vehicle_assignments",
    )

    driver = models.ForeignKey(
        Staff,
        on_delete=models.PROTECT,
        related_name="driver_assignments",
        limit_choices_to={"staff_type": Staff.StaffType.DRIVER},
    )

    attendant = models.ForeignKey(
        Staff,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendant_assignments",
        limit_choices_to={"staff_type": Staff.StaffType.BUS_ATTENDANT},
    )

    effective_from = models.DateField()

    effective_to = models.DateField(
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    remarks = models.TextField(
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "transport_vehicle_assignments"

        constraints = [
            models.UniqueConstraint(
                fields=["vehicle", "effective_from"],
                name="unique_vehicle_assignment_date",
            ),
        ]

        indexes = [
            models.Index(fields=["school"]),
            models.Index(fields=["branch"]),
            models.Index(fields=["vehicle"]),
            models.Index(fields=["route"]),
            models.Index(fields=["driver"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.vehicle.vehicle_number} - {self.route.route_name}"

class StudentTransport(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"
        CANCELLED = "CANCELLED", "Cancelled"

    class TripType(models.TextChoices):
        PICKUP = "PICKUP", "Pickup Only"
        DROPOFF = "DROPOFF", "Drop Only"
        BOTH = "BOTH", "Pickup & Drop"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name="student_transports",
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="student_transports",
    )

    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name="student_transports",
    )

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="transport_assignments",
    )

    vehicle_assignment = models.ForeignKey(
        "transport.VehicleAssignment",
        on_delete=models.CASCADE,
        related_name="student_assignments",
    )

    pickup_stop = models.ForeignKey(
        "transport.Stop",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pickup_students",
    )

    drop_stop = models.ForeignKey(
        "transport.Stop",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="drop_students",
    )

    trip_type = models.CharField(
        max_length=20,
        choices=TripType.choices,
        default=TripType.BOTH,
    )



    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    remarks = models.TextField(
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "student_transport"

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "academic_year",
                    "student",
                ],
                name="unique_student_transport",
            ),
        ]

        indexes = [
            models.Index(fields=["school"]),
            models.Index(fields=["student"]),
            models.Index(fields=["vehicle_assignment"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.student} - {self.vehicle_assignment}"




class Trip(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Shift(models.TextChoices):
        MORNING = "MORNING", "Morning"
        AFTERNOON = "AFTERNOON", "Afternoon"
        EVENING = "EVENING", "Evening"

    class Status(models.TextChoices):
        SCHEDULED = "SCHEDULED", "Scheduled"
        STARTED = "STARTED", "Started"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name="trips",
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trips",
    )

    vehicle_assignment = models.ForeignKey(
        "transport.VehicleAssignment",
        on_delete=models.PROTECT,
        related_name="trips",
    )

    trip_date = models.DateField()

    shift = models.CharField(
        max_length=20,
        choices=Shift.choices,
    )

    scheduled_start_time = models.TimeField()

    scheduled_end_time = models.TimeField(
        null=True,
        blank=True,
    )

    actual_start_time = models.DateTimeField(
        null=True,
        blank=True,
    )

    actual_end_time = models.DateTimeField(
        null=True,
        blank=True,
    )

    start_odometer = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="In kilometres",
    )

    end_odometer = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="In kilometres",
    )

    total_distance = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="In kilometres",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SCHEDULED,
    )

    remarks = models.TextField(
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "transport_trips"

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "vehicle_assignment",
                    "trip_date",
                    "shift",
                ],
                name="unique_vehicle_assignment_trip",
            ),
        ]

        indexes = [
            models.Index(fields=["school"]),
            models.Index(fields=["branch"]),
            models.Index(fields=["trip_date"]),
            models.Index(fields=["status"]),
        ]

        ordering = [
            "-trip_date",
            "scheduled_start_time",
        ]

    def __str__(self):
        return (
            f"{self.vehicle_assignment.vehicle.vehicle_number} - "
            f"{self.trip_date} ({self.shift})"
        )





class TripAttendance(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class PickupStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        BOARDED = "BOARDED", "Boarded"
        ABSENT = "ABSENT", "Absent"
        NO_SHOW = "NO_SHOW", "No Show"

    class DropStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        DROPPED = "DROPPED", "Dropped"
        NOT_DROPPED = "NOT_DROPPED", "Not Dropped"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name="trip_attendances",
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trip_attendances",
    )

    trip = models.ForeignKey(
        "transport.Trip",
        on_delete=models.CASCADE,
        related_name="attendances",
    )

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="trip_attendances",
    )

    pickup_status = models.CharField(
        max_length=20,
        choices=PickupStatus.choices,
        default=PickupStatus.PENDING,
    )

    pickup_time = models.DateTimeField(
        null=True,
        blank=True,
    )

    drop_status = models.CharField(
        max_length=20,
        choices=DropStatus.choices,
        default=DropStatus.PENDING,
    )

    drop_time = models.DateTimeField(
        null=True,
        blank=True,
    )

    remarks = models.TextField(
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "transport_trip_attendance"

        constraints = [
            models.UniqueConstraint(
                fields=["trip", "student"],
                name="unique_trip_student",
            ),
        ]

        indexes = [
            models.Index(fields=["school"]),
            models.Index(fields=["trip"]),
            models.Index(fields=["student"]),
            models.Index(fields=["pickup_status"]),
            models.Index(fields=["drop_status"]),
        ]

    def __str__(self):
        return f"{self.trip} - {self.student}"





class LiveLocation(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class LocationSource(models.TextChoices):
        MOBILE = "MOBILE", "Driver Mobile"
        GPS_DEVICE = "GPS_DEVICE", "GPS Device"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name="live_locations",
    )

    trip = models.ForeignKey(
        "transport.Trip",
        on_delete=models.CASCADE,
        related_name="live_locations",
    )

    latitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
    )

    longitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
    )

    speed = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Speed in km/h",
    )

    heading = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Direction (0-359 degrees)",
    )

    altitude = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Altitude in meters",
    )

    accuracy = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="GPS accuracy in meters",
    )
    device_timestamp = models.DateTimeField(
        null=True,
        blank=True,
    )
    source = models.CharField(
        max_length=20,
        choices=LocationSource.choices,
        default=LocationSource.MOBILE,
    )

    recorded_at = models.DateTimeField()

    class Meta:
        db_table = "transport_live_locations"

        indexes = [
            models.Index(fields=["school"]),
            models.Index(fields=["trip"]),
            models.Index(fields=["recorded_at"]),
        ]

        ordering = [
            "-recorded_at",
        ]

    def __str__(self):
        return (
            f"{self.trip} - "
            f"({self.latitude}, {self.longitude})"
        )

class LocationHistory(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class LocationSource(models.TextChoices):
        MOBILE = "MOBILE", "Driver Mobile"
        GPS_DEVICE = "GPS_DEVICE", "GPS Device"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name="location_history",
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="location_history",
    )

    trip = models.ForeignKey(
        Trip,
        on_delete=models.CASCADE,
        related_name="location_history",
    )

    latitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
    )

    longitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
    )

    speed = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Speed in km/h",
    )

    heading = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Direction (0–359°)",
        validators=[
            MinValueValidator(0),
            MaxValueValidator(359),
        ],
    )

    altitude = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Altitude in meters",
    )

    accuracy = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="GPS accuracy in meters",
    )

    source = models.CharField(
        max_length=20,
        choices=LocationSource.choices,
        default=LocationSource.MOBILE,
    )

    device_timestamp = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp received from the GPS device/mobile.",
    )

    recorded_at = models.DateTimeField(
        db_index=True,
        help_text="Time when this location was recorded.",
    )

    class Meta:

        db_table = "transport_location_history"

        ordering = [
            "-recorded_at",
        ]

        get_latest_by = "recorded_at"

        indexes = [
            models.Index(
                fields=[
                    "trip",
                    "-recorded_at",
                ],
                name="trip_recorded_idx",
            ),
            models.Index(
                fields=[
                    "school",
                    "-recorded_at",
                ],
                name="school_recorded_idx",
            ),
        ]

    def __str__(self):

        return (
            f"{self.trip} - "
            f"({self.latitude}, {self.longitude})"
        )

class TripEvent(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class EventType(models.TextChoices):
        TRIP_STARTED = "TRIP_STARTED", "Trip Started"
        TRIP_COMPLETED = "TRIP_COMPLETED", "Trip Completed"

        REACHED_STOP = "REACHED_STOP", "Reached Stop"
        LEFT_STOP = "LEFT_STOP", "Left Stop"

        STUDENT_BOARDED = "STUDENT_BOARDED", "Student Boarded"
        STUDENT_DROPPED = "STUDENT_DROPPED", "Student Dropped"

        OVERSPEED = "OVERSPEED", "Overspeed"
        HARSH_BRAKE = "HARSH_BRAKE", "Harsh Brake"
        SHARP_TURN = "SHARP_TURN", "Sharp Turn"

        IDLE = "IDLE", "Idle"
        GPS_OFFLINE = "GPS_OFFLINE", "GPS Offline"
        GPS_ONLINE = "GPS_ONLINE", "GPS Online"

        PANIC_BUTTON = "PANIC_BUTTON", "Panic Button"
        SOS = "SOS", "SOS Alert"

        GEOFENCE_ENTER = "GEOFENCE_ENTER", "Geofence Enter"
        GEOFENCE_EXIT = "GEOFENCE_EXIT", "Geofence Exit"

        OTHER = "OTHER", "Other"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name="trip_events",
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trip_events",
    )

    trip = models.ForeignKey(
        "transport.Trip",
        on_delete=models.CASCADE,
        related_name="events",
    )

    live_location = models.ForeignKey(
        "transport.LiveLocation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
    )

    stop = models.ForeignKey(
        "transport.Stop",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trip_events",
    )

    student = models.ForeignKey(
        "school.Student",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trip_events",
    )

    event_type = models.CharField(
        max_length=30,
        choices=EventType.choices,
    )

    vendor_event_code = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Raw event code received from GPS device",
    )

    event_time = models.DateTimeField()

    remarks = models.TextField(
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "transport_trip_events"

        indexes = [
            models.Index(fields=["school"]),
            models.Index(fields=["trip"]),
            models.Index(fields=["event_type"]),
            models.Index(fields=["event_time"]),
            models.Index(fields=["student"]),
            models.Index(fields=["stop"]),
        ]

        ordering = [
            "-event_time",
        ]

    def __str__(self):
        return f"{self.trip} - {self.get_event_type_display()}"