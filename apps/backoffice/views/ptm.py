from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.ptm.models import ParentTeacherMeeting, ParentTeacherMeetingSection
from apps.school.models.school import AcademicYear, Branch, Grade, Section
from shared.mixins import CustomResponse
from shared.permissions import HasPermission
from shared.utils.logger import application_logger
from django.db import transaction

class CreateParentTeacherMeetingAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]

    required_permission = "parent_teacher_meeting.create"

    def post(self, request):

        school = request.school

        application_logger.info(
            "parent_teacher_meeting_create_started",
            user_id=str(request.user.id),
            school_id=str(school.id) if school else None,
        )

        if school is None:

            application_logger.warning(
                "parent_teacher_meeting_create_failed",
                reason="school_not_found",
                user_id=str(request.user.id),
            )

            return CustomResponse.errorResponse(
                description="School not found."
            )

        required_fields = [
            "academic_year_id",
            "grade_id",
            "section_ids",
            "title",
            "meeting_type",
            "meeting_date",
            "start_time",
            "end_time",
            "meeting_mode",
        ]

        for field in required_fields:

            if request.data.get(field) in [None, "", []]:

                application_logger.warning(
                    "parent_teacher_meeting_create_failed",
                    reason="required_field_missing",
                    field=field,
                    school_id=str(school.id),
                )

                return CustomResponse.errorResponse(
                    description=f"{field} is required."
                )

        academic_year = AcademicYear.objects.filter(
            id=request.data.get("academic_year_id"),
            school=school,
        ).first()

        if academic_year is None:

            application_logger.warning(
                "parent_teacher_meeting_create_failed",
                reason="academic_year_not_found",
                academic_year_id=request.data.get("academic_year_id"),
                school_id=str(school.id),
            )

            return CustomResponse.errorResponse(
                description="Academic year not found."
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
                    "parent_teacher_meeting_create_failed",
                    reason="branch_not_found",
                    branch_id=branch_id,
                    school_id=str(school.id),
                )

                return CustomResponse.errorResponse(
                    description="Branch not found."
                )

        grade = Grade.objects.filter(
            id=request.data.get("grade_id"),
            school=school,
            academic_year=academic_year,
        ).first()

        if grade is None:

            application_logger.warning(
                "parent_teacher_meeting_create_failed",
                reason="grade_not_found",
                grade_id=request.data.get("grade_id"),
                school_id=str(school.id),
            )

            return CustomResponse.errorResponse(
                description="Grade not found."
            )

        section_ids = request.data.get("section_ids")

        if not isinstance(section_ids, list):

            return CustomResponse.errorResponse(
                description="section_ids must be a list."
            )

        section_ids = list(set(section_ids))

        sections = Section.objects.filter(
            id__in=section_ids,
            grade=grade,
            branch=branch,
        )

        if sections.count() != len(section_ids):

            application_logger.warning(
                "parent_teacher_meeting_create_failed",
                reason="invalid_sections",
                section_ids=section_ids,
                grade_id=str(grade.id),
                branch_id=str(branch.id) if branch else None,
            )

            return CustomResponse.errorResponse(
                description="One or more sections are invalid."
            )

        meeting_type = request.data.get("meeting_type")

        if meeting_type not in ParentTeacherMeeting.MeetingType.values:

            return CustomResponse.errorResponse(
                description="Invalid meeting type."
            )

        meeting_mode = request.data.get("meeting_mode")

        if meeting_mode not in ParentTeacherMeeting.MeetingMode.values:

            return CustomResponse.errorResponse(
                description="Invalid meeting mode."
            )

        meeting_status = request.data.get(
            "status",
            ParentTeacherMeeting.Status.DRAFT,
        )

        if meeting_status not in ParentTeacherMeeting.Status.values:

            return CustomResponse.errorResponse(
                description="Invalid status."
            )

        start_time = request.data.get("start_time")
        end_time = request.data.get("end_time")

        if start_time >= end_time:

            return CustomResponse.errorResponse(
                description="End time must be greater than start time."
            )

        location = request.data.get("location")
        meeting_link = request.data.get("meeting_link")

        if (
            meeting_mode == ParentTeacherMeeting.MeetingMode.OFFLINE
            and not location
        ):

            return CustomResponse.errorResponse(
                description="Location is required for offline meeting."
            )

        if (
            meeting_mode == ParentTeacherMeeting.MeetingMode.ONLINE
            and not meeting_link
        ):

            return CustomResponse.errorResponse(
                description="Meeting link is required for online meeting."
            )

        try:

            with transaction.atomic():

                meeting = ParentTeacherMeeting.objects.create(
                    school=school,
                    branch=branch,
                    academic_year=academic_year,
                    grade=grade,
                    title=request.data.get("title").strip(),
                    description=request.data.get("description"),
                    meeting_type=meeting_type,
                    meeting_date=request.data.get("meeting_date"),
                    start_time=start_time,
                    end_time=end_time,
                    meeting_mode=meeting_mode,
                    location=location,
                    meeting_link=meeting_link,
                    status=meeting_status,
                )

                ParentTeacherMeetingSection.objects.bulk_create(
                    [
                        ParentTeacherMeetingSection(
                            meeting=meeting,
                            section=section,
                        )
                        for section in sections
                    ]
                )

        except Exception as e:

            application_logger.exception(
                "parent_teacher_meeting_create_failed",
                school_id=str(school.id),
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description=str(e)
            )

        application_logger.info(
            "parent_teacher_meeting_created",
            meeting_id=str(meeting.id),
            school_id=str(school.id),
            branch_id=str(branch.id) if branch else None,
            grade_id=str(grade.id),
            section_count=len(section_ids),
            user_id=str(request.user.id),
        )

        return CustomResponse.successResponse(
            description="Parent teacher meeting created successfully.",
            data={
                "id": str(meeting.id),
                "title": meeting.title,
            },
        )
class ParentTeacherMeetingListAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]

    required_permission = "parent_teacher_meeting.view"

    def get(self, request):

        school = request.school

        application_logger.info(
            "parent_teacher_meeting_list_started",
            user_id=str(request.user.id),
            school_id=str(school.id) if school else None,
        )

        if school is None:

            application_logger.warning(
                "parent_teacher_meeting_list_failed",
                reason="school_not_found",
                user_id=str(request.user.id),
            )

            return CustomResponse.errorResponse(
                description="School not found."
            )

        academic_year_id = request.query_params.get("academic_year_id")
        branch_id = request.query_params.get("branch_id")
        grade_id = request.query_params.get("grade_id")
        section_id = request.query_params.get("section_id")
        meeting_type = request.query_params.get("meeting_type")
        meeting_mode = request.query_params.get("meeting_mode")
        meeting_status = request.query_params.get("status")
        meeting_date = request.query_params.get("meeting_date")

        meetings = ParentTeacherMeeting.objects.select_related(
            "academic_year",
            "branch",
            "grade",
        ).prefetch_related(
            "meeting_sections__section",
        ).filter(
            school=school,
        )

        if academic_year_id:
            meetings = meetings.filter(
                academic_year_id=academic_year_id,
            )

        if branch_id:
            meetings = meetings.filter(
                branch_id=branch_id,
            )

        if grade_id:
            meetings = meetings.filter(
                grade_id=grade_id,
            )

        if section_id:
            meetings = meetings.filter(
                meeting_sections__section_id=section_id,
            )

        if meeting_type:
            meetings = meetings.filter(
                meeting_type=meeting_type,
            )

        if meeting_mode:
            meetings = meetings.filter(
                meeting_mode=meeting_mode,
            )

        if meeting_status:
            meetings = meetings.filter(
                status=meeting_status,
            )

        if meeting_date:
            meetings = meetings.filter(
                meeting_date=meeting_date,
            )

        meetings = meetings.distinct().order_by(
            "-meeting_date",
            "-start_time",
        )

        data = []

        for meeting in meetings:

            data.append({
                "id": str(meeting.id),

                "title": meeting.title,

                "description": meeting.description,

                "meeting_type": meeting.meeting_type,

                "meeting_date": meeting.meeting_date,

                "start_time": meeting.start_time,

                "end_time": meeting.end_time,

                "meeting_mode": meeting.meeting_mode,

                "location": meeting.location,

                "meeting_link": meeting.meeting_link,

                "status": meeting.status,

                "academic_year": {
                    "id": str(meeting.academic_year.id),
                    "name": meeting.academic_year.name,
                },

                "branch": {
                    "id": str(meeting.branch.id),
                    "name": meeting.branch.name,
                } if meeting.branch else None,

                "grade": {
                    "id": str(meeting.grade.id),
                    "name": meeting.grade.name,
                },

                "sections": [
                    {
                        "id": str(item.section.id),
                        "name": item.section.name,
                    }
                    for item in meeting.meeting_sections.all()
                ],
            })

        application_logger.info(
            "parent_teacher_meeting_list_fetched",
            school_id=str(school.id),
            total_count=len(data),
            user_id=str(request.user.id),
        )

        return CustomResponse.successResponse(
            description="Parent teacher meetings fetched successfully.",
            data=data,
        )



class UpdateParentTeacherMeetingAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]

    required_permission = "parent_teacher_meeting.update"

    def put(self, request, meeting_id):

        school = request.school

        application_logger.info(
            "parent_teacher_meeting_update_started",
            meeting_id=str(meeting_id),
            school_id=str(school.id) if school else None,
            user_id=str(request.user.id),
        )

        if school is None:
            return CustomResponse.errorResponse(
                description="School not found."
            )

        meeting = ParentTeacherMeeting.objects.select_related(
            "branch",
            "academic_year",
            "grade",
        ).filter(
            id=meeting_id,
            school=school,
        ).first()

        if meeting is None:

            application_logger.warning(
                "parent_teacher_meeting_update_failed",
                reason="meeting_not_found",
                meeting_id=str(meeting_id),
                school_id=str(school.id),
            )

            return CustomResponse.errorResponse(
                description="Parent teacher meeting not found."
            )

        academic_year = meeting.academic_year

        if "academic_year_id" in request.data:

            academic_year = AcademicYear.objects.filter(
                id=request.data.get("academic_year_id"),
                school=school,
            ).first()

            if academic_year is None:
                return CustomResponse.errorResponse(
                    description="Academic year not found."
                )

        branch = meeting.branch

        if "branch_id" in request.data:

            branch_id = request.data.get("branch_id")

            if branch_id in [None, ""]:
                branch = None

            else:

                branch = Branch.objects.filter(
                    id=branch_id,
                    school=school,
                ).first()

                if branch is None:
                    return CustomResponse.errorResponse(
                        description="Branch not found."
                    )

        grade = meeting.grade

        if "grade_id" in request.data:

            grade = Grade.objects.filter(
                id=request.data.get("grade_id"),
                school=school,
                academic_year=academic_year,
            ).first()

            if grade is None:
                return CustomResponse.errorResponse(
                    description="Grade not found."
                )

        sections = None

        scope_changed = (
            "academic_year_id" in request.data
            or "branch_id" in request.data
            or "grade_id" in request.data
        )

        if "section_ids" in request.data:

            section_ids = request.data.get("section_ids")

            if not isinstance(section_ids, list) or not section_ids:
                return CustomResponse.errorResponse(
                    description="At least one section is required."
                )

            section_ids = list(set(section_ids))

            sections = Section.objects.filter(
                id__in=section_ids,
                grade=grade,
                branch=branch,
            )

            if sections.count() != len(section_ids):
                return CustomResponse.errorResponse(
                    description="One or more sections are invalid."
                )

        elif scope_changed:

            existing_section_ids = list(
                meeting.meeting_sections.values_list(
                    "section_id",
                    flat=True,
                )
            )

            sections = Section.objects.filter(
                id__in=existing_section_ids,
                grade=grade,
                branch=branch,
            )

            if sections.count() != len(existing_section_ids):

                return CustomResponse.errorResponse(
                    description=(
                        "Existing sections do not belong to the selected "
                        "grade or branch. Please provide section_ids."
                    )
                )

        meeting_type = request.data.get(
            "meeting_type",
            meeting.meeting_type,
        )

        if meeting_type not in ParentTeacherMeeting.MeetingType.values:
            return CustomResponse.errorResponse(
                description="Invalid meeting type."
            )

        meeting_mode = request.data.get(
            "meeting_mode",
            meeting.meeting_mode,
        )

        if meeting_mode not in ParentTeacherMeeting.MeetingMode.values:
            return CustomResponse.errorResponse(
                description="Invalid meeting mode."
            )

        meeting_status = request.data.get(
            "status",
            meeting.status,
        )

        if meeting_status not in ParentTeacherMeeting.Status.values:
            return CustomResponse.errorResponse(
                description="Invalid status."
            )

        start_time = request.data.get(
            "start_time",
            meeting.start_time,
        )

        end_time = request.data.get(
            "end_time",
            meeting.end_time,
        )

        if str(start_time) >= str(end_time):

            return CustomResponse.errorResponse(
                description="End time must be greater than start time."
            )

        location = request.data.get(
            "location",
            meeting.location,
        )

        meeting_link = request.data.get(
            "meeting_link",
            meeting.meeting_link,
        )

        if (
            meeting_mode == ParentTeacherMeeting.MeetingMode.OFFLINE
            and not location
        ):
            return CustomResponse.errorResponse(
                description="Location is required for offline meeting."
            )

        if (
            meeting_mode == ParentTeacherMeeting.MeetingMode.ONLINE
            and not meeting_link
        ):
            return CustomResponse.errorResponse(
                description="Meeting link is required for online meeting."
            )

        try:

            with transaction.atomic():

                meeting.academic_year = academic_year
                meeting.branch = branch
                meeting.grade = grade
                meeting.title = request.data.get("title", meeting.title)
                meeting.description = request.data.get("description", meeting.description)
                meeting.meeting_type = meeting_type
                meeting.meeting_date = request.data.get("meeting_date", meeting.meeting_date)
                meeting.start_time = start_time
                meeting.end_time = end_time
                meeting.meeting_mode = meeting_mode
                meeting.location = location
                meeting.meeting_link = meeting_link
                meeting.status = meeting_status

                meeting.save()

                if sections is not None:

                    ParentTeacherMeetingSection.objects.filter(
                        meeting=meeting
                    ).delete()

                    ParentTeacherMeetingSection.objects.bulk_create(
                        [
                            ParentTeacherMeetingSection(
                                meeting=meeting,
                                section=section,
                            )
                            for section in sections
                        ]
                    )

        except Exception as e:

            application_logger.exception(
                "parent_teacher_meeting_update_failed",
                meeting_id=str(meeting.id),
                school_id=str(school.id),
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description=str(e)
            )

        application_logger.info(
            "parent_teacher_meeting_updated",
            meeting_id=str(meeting.id),
            school_id=str(school.id),
            branch_id=str(branch.id) if branch else None,
            grade_id=str(grade.id),
            user_id=str(request.user.id),
        )

        return CustomResponse.successResponse(
            description="Parent teacher meeting updated successfully.",
            data={
                "id": str(meeting.id),
                "title": meeting.title,
            },
        )