from django.db import transaction
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.calendar.models import CalendarEventTarget, CalendarEvent
from apps.school.models.school import AcademicYear, Branch, Grade, Section, Student, Staff
from shared.mixins import CustomResponse
from shared.permissions import HasPermission
from shared.utils.logger import application_logger, audit_logger


class CreateCalendarEventAPIView(APIView):

    permission_classes = [IsAuthenticated,HasPermission,]

    required_permission = "calendar.create"

    @transaction.atomic
    def post(self, request):

        user = request.user
        school = request.school

        application_logger.info(
            "calendar_event_create_started",
            user_id=str(user.id),
            school_id=str(school.id),
        )

        title = request.data.get("title")
        event_type = request.data.get("event_type")
        event_date = request.data.get("event_date")
        target_type = request.data.get("target_type")

        if not title:
            return CustomResponse.errorResponse(
                description="title is required."
            )

        if not event_type:
            return CustomResponse.errorResponse(
                description="event_type is required."
            )

        if not event_date:
            return CustomResponse.errorResponse(
                description="event_date is required."
            )

        if target_type not in CalendarEventTarget.TargetType.values:
            return CustomResponse.errorResponse(
                description="Invalid target type."
            )

        academic_year = None

        academic_year_id = request.data.get(
            "academic_year_id"
        )

        if academic_year_id:

            academic_year = AcademicYear.objects.filter(
                id=academic_year_id,
                school=school,
            ).first()

            if academic_year is None:

                return CustomResponse.errorResponse(
                    description="Academic year not found."
                )

        event = CalendarEvent.objects.create(
            school=school,
            title=title,
            description=request.data.get("description"),
            event_type=event_type,
            event_date=event_date,
            start_time=request.data.get("start_time"),
            end_time=request.data.get("end_time"),
            is_all_day=request.data.get(
                "is_all_day",
                False,
            ),
        )

        targets = []

        if target_type == CalendarEventTarget.TargetType.SCHOOL:

            targets.append(
                CalendarEventTarget(
                    event=event,
                    target_type=target_type,
                    academic_year=academic_year,
                )
            )

        elif target_type == CalendarEventTarget.TargetType.BRANCH:

            branch_ids = request.data.get(
                "branch_ids",
                [],
            )

            branches = Branch.objects.filter(
                school=school,
                id__in=branch_ids,
            )

            for branch in branches:

                targets.append(
                    CalendarEventTarget(
                        event=event,
                        target_type=target_type,
                        academic_year=academic_year,
                        branch=branch,
                    )
                )

        elif target_type == CalendarEventTarget.TargetType.GRADE:

            grade_ids = request.data.get(
                "grade_ids",
                [],
            )

            grades = Grade.objects.filter(
                school=school,
                id__in=grade_ids,
            )

            for grade in grades:

                targets.append(
                    CalendarEventTarget(
                        event=event,
                        target_type=target_type,
                        academic_year=academic_year,
                        grade=grade,
                    )
                )

        elif target_type == CalendarEventTarget.TargetType.SECTION:

            section_ids = request.data.get(
                "section_ids",
                [],
            )

            sections = Section.objects.filter(
                grade__school=school,
                id__in=section_ids,
            )

            for section in sections:

                targets.append(
                    CalendarEventTarget(
                        event=event,
                        target_type=target_type,
                        academic_year=academic_year,
                        grade=section.grade,
                        section=section,
                        branch=section.branch,
                    )
                )

        elif target_type == CalendarEventTarget.TargetType.STUDENT:

            student_ids = request.data.get(
                "student_ids",
                [],
            )

            students = Student.objects.filter(
                school=school,
                id__in=student_ids,
            )

            for student in students:

                targets.append(
                    CalendarEventTarget(
                        event=event,
                        target_type=target_type,
                        academic_year=student.academic_year,
                        branch=student.branch,
                        grade=student.grade,
                        section=student.section,
                        student=student,
                    )
                )

        elif target_type == CalendarEventTarget.TargetType.STAFF:

            staff_ids = request.data.get(
                "staff_ids",
                [],
            )

            staffs = Staff.objects.filter(
                school=school,
                id__in=staff_ids,
            )

            for staff in staffs:

                targets.append(
                    CalendarEventTarget(
                        event=event,
                        target_type=target_type,
                        branch=staff.branch,
                        staff=staff,
                    )
                )

        CalendarEventTarget.objects.bulk_create(
            targets
        )

        audit_logger.info(
            "calendar_event_created",
            user_id=str(user.id),
            school_id=str(school.id),
            event_id=str(event.id),
            target_type=target_type,
            target_count=len(targets),
        )

        return CustomResponse.successResponse(
            description="Calendar event created successfully.",
            data={
                "id": str(event.id),
            },
        )

class CalendarEventListAPIView(APIView):

    permission_classes = [IsAuthenticated,HasPermission,]

    required_permission = "calendar.view"

    def get(self, request):

        school = request.school

        application_logger.info(
            "calendar_event_list_started",
            user_id=str(request.user.id),
            school_id=str(school.id),
        )

        events = CalendarEvent.objects.filter(
            school=school,
            status=CalendarEvent.Status.ACTIVE,
        ).prefetch_related(
            "targets",
            "targets__branch",
            "targets__grade",
            "targets__section",
            "targets__student",
            "targets__staff",
            "targets__academic_year",
        ).order_by(
            "event_date",
            "start_time",
        )

        event_type = request.query_params.get("event_type")
        event_date = request.query_params.get("event_date")
        from_date = request.query_params.get("from_date")
        to_date = request.query_params.get("to_date")

        if event_type:
            events = events.filter(
                event_type=event_type,
            )

        if event_date:
            events = events.filter(
                event_date=event_date,
            )

        if from_date:
            events = events.filter(
                event_date__gte=from_date,
            )

        if to_date:
            events = events.filter(
                event_date__lte=to_date,
            )

        data = []

        for event in events:

            targets = []

            for target in event.targets.all():

                targets.append({
                    "id": str(target.id),
                    "target_type": target.target_type,
                    "academic_year": {
                        "id": str(target.academic_year.id),
                        "name": target.academic_year.name,
                    } if target.academic_year else None,
                    "branch": {
                        "id": str(target.branch.id),
                        "name": target.branch.name,
                    } if target.branch else None,
                    "grade": {
                        "id": str(target.grade.id),
                        "name": target.grade.name,
                    } if target.grade else None,
                    "section": {
                        "id": str(target.section.id),
                        "name": target.section.name,
                    } if target.section else None,
                    "student": {
                        "id": str(target.student.id),
                        "name": target.student.name,
                    } if target.student else None,
                    "staff": {
                        "id": str(target.staff.id),
                        "name": target.staff.name,
                    } if target.staff else None,
                })

            data.append({
                "id": str(event.id),
                "title": event.title,
                "description": event.description,
                "event_type": event.event_type,
                "event_date": event.event_date,
                "start_time": event.start_time,
                "end_time": event.end_time,
                "is_all_day": event.is_all_day,
                "status": event.status,
                "reference_id": str(event.reference_id) if event.reference_id else None,
                "targets": targets,
            })

        audit_logger.info(
            "calendar_event_list_fetched",
            user_id=str(request.user.id),
            school_id=str(school.id),
            total_count=len(data),
        )

        return CustomResponse.successResponse(
            description="Calendar events fetched successfully.",
            data=data,
        )


class UpdateCalendarEventAPIView(APIView):

    permission_classes = [IsAuthenticated,HasPermission,]

    required_permission = "calendar.update"

    @transaction.atomic
    def put(self, request, event_id):

        school = request.school

        application_logger.info(
            "calendar_event_update_started",
            user_id=str(request.user.id),
            school_id=str(school.id),
            event_id=str(event_id),
        )

        event = CalendarEvent.objects.filter(
            id=event_id,
            school=school,
        ).first()

        if event is None:

            application_logger.warning(
                "calendar_event_update_failed",
                user_id=str(request.user.id),
                school_id=str(school.id),
                event_id=str(event_id),
                reason="event_not_found",
            )

            return CustomResponse.errorResponse(
                description="Calendar event not found.",
            )

        target_type = request.data.get("target_type")

        if target_type and target_type not in CalendarEventTarget.TargetType.values:

            return CustomResponse.errorResponse(
                description="Invalid target type.",
            )

        event.title = request.data.get(
            "title",
            event.title,
        )

        event.description = request.data.get(
            "description",
            event.description,
        )

        event.event_type = request.data.get(
            "event_type",
            event.event_type,
        )

        event.event_date = request.data.get(
            "event_date",
            event.event_date,
        )

        event.start_time = request.data.get(
            "start_time",
            event.start_time,
        )

        event.end_time = request.data.get(
            "end_time",
            event.end_time,
        )

        event.is_all_day = request.data.get(
            "is_all_day",
            event.is_all_day,
        )

        event.status = request.data.get(
            "status",
            event.status,
        )

        event.save()

        if target_type:

            CalendarEventTarget.objects.filter(
                event=event,
            ).delete()

            academic_year = None

            academic_year_id = request.data.get(
                "academic_year_id",
            )

            if academic_year_id:

                academic_year = AcademicYear.objects.filter(
                    id=academic_year_id,
                    school=school,
                ).first()

                if academic_year is None:

                    return CustomResponse.errorResponse(
                        description="Academic year not found.",
                    )

            targets = []

            if target_type == CalendarEventTarget.TargetType.SCHOOL:

                targets.append(
                    CalendarEventTarget(
                        event=event,
                        target_type=target_type,
                        academic_year=academic_year,
                    )
                )

            elif target_type == CalendarEventTarget.TargetType.BRANCH:

                branches = Branch.objects.filter(
                    school=school,
                    id__in=request.data.get(
                        "branch_ids",
                        [],
                    ),
                )

                for branch in branches:

                    targets.append(
                        CalendarEventTarget(
                            event=event,
                            target_type=target_type,
                            academic_year=academic_year,
                            branch=branch,
                        )
                    )

            elif target_type == CalendarEventTarget.TargetType.GRADE:

                grades = Grade.objects.filter(
                    school=school,
                    id__in=request.data.get(
                        "grade_ids",
                        [],
                    ),
                )

                for grade in grades:

                    targets.append(
                        CalendarEventTarget(
                            event=event,
                            target_type=target_type,
                            academic_year=academic_year,
                            grade=grade,
                        )
                    )

            elif target_type == CalendarEventTarget.TargetType.SECTION:

                sections = Section.objects.select_related(
                    "grade",
                    "branch",
                ).filter(
                    grade__school=school,
                    id__in=request.data.get(
                        "section_ids",
                        [],
                    ),
                )

                for section in sections:

                    targets.append(
                        CalendarEventTarget(
                            event=event,
                            target_type=target_type,
                            academic_year=academic_year,
                            branch=section.branch,
                            grade=section.grade,
                            section=section,
                        )
                    )

            elif target_type == CalendarEventTarget.TargetType.STUDENT:

                students = Student.objects.select_related(
                    "academic_year",
                    "branch",
                    "grade",
                    "section",
                ).filter(
                    school=school,
                    id__in=request.data.get(
                        "student_ids",
                        [],
                    ),
                )

                for student in students:

                    targets.append(
                        CalendarEventTarget(
                            event=event,
                            target_type=target_type,
                            academic_year=student.academic_year,
                            branch=student.branch,
                            grade=student.grade,
                            section=student.section,
                            student=student,
                        )
                    )

            elif target_type == CalendarEventTarget.TargetType.STAFF:

                staffs = Staff.objects.select_related(
                    "branch",
                ).filter(
                    school=school,
                    id__in=request.data.get(
                        "staff_ids",
                        [],
                    ),
                )

                for staff in staffs:

                    targets.append(
                        CalendarEventTarget(
                            event=event,
                            target_type=target_type,
                            branch=staff.branch,
                            staff=staff,
                        )
                    )

            CalendarEventTarget.objects.bulk_create(
                targets,
            )

        audit_logger.info(
            "calendar_event_updated",
            user_id=str(request.user.id),
            school_id=str(school.id),
            event_id=str(event.id),
        )

        return CustomResponse.successResponse(
            description="Calendar event updated successfully.",
            data={
                "id": str(event.id),
            },
        )

