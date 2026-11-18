from datetime import date

from django.db.models import Q
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.activities.models import Activities, ActivitySteps
from shared.mixins import CustomResponse, CustomPageNumberPagination
from shared.permissions import HasPermission
from shared.utils.logger import application_logger


class ActivitiesListAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    pagination_class = CustomPageNumberPagination
    required_permission = "activity.view"

    def get(self, request):

        try:
            queryset = Activities.objects.all().order_by("date")

            search = request.query_params.get("search")
            if search:
                queryset = queryset.filter(
                    Q(title__icontains=search) |
                    Q(theme__icontains=search) |
                    Q(description__icontains=search)
                )

            activity_date = request.query_params.get("date")
            if activity_date:
                queryset = queryset.filter(date=activity_date)

            theme = request.query_params.get("theme")
            if theme:
                queryset = queryset.filter(theme__icontains=theme)

            total = queryset.count()

            paginator = self.pagination_class()

            paginated_queryset = paginator.paginate_queryset(
                queryset,
                request,
                view=self
            )

            if paginated_queryset is None:
                paginated_queryset = queryset

            data = [
                {
                    "id": str(activity.id),
                    "date": activity.date,
                    "title": activity.title,
                    "theme": activity.theme,
                    "prompt": activity.prompt,
                    "benefit": activity.benefit,
                    "youtube_video_url": activity.youtube_video_url,
                    "description": activity.description,
                    "image": activity.image,
                }
                for activity in paginated_queryset
            ]

            return CustomResponse.successResponse(
                data=data,
                total=total,
                description="Activities fetched successfully."
            )

        except Exception as e:

            application_logger.exception(
                f"Activities list error: {str(e)}"
            )

            return CustomResponse.errorResponse(
                description="Unable to fetch activities."
            )

class ActivitiesCreateAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "activity.view"


    def post(self, request):

        try:
            data = request.data

            activity_date = data.get("date")
            title = data.get("title")

            if not activity_date:
                return CustomResponse.errorResponse(
                    description="Date is required."
                )

            if not title:
                return CustomResponse.errorResponse(
                    description="Title is required."
                )

            try:
                activity_date = date.fromisoformat(activity_date)
            except (ValueError, TypeError):
                return CustomResponse.errorResponse(
                    description="Invalid date format. Use YYYY-MM-DD."
                )

            if Activities.objects.filter(date=activity_date).exists():
                return CustomResponse.errorResponse(
                    description="An activity already exists for this date."
                )

            activity = Activities.objects.create(
                date=activity_date,
                title=title,
                theme=data.get("theme"),
                prompt=data.get("prompt"),
                benefit=data.get("benefit"),
                youtube_video_url=data.get("youtube_video_url"),
                description=data.get("description"),
                image=data.get("image"),
            )

            application_logger.info(
                f"Activity created successfully: {activity.id}"
            )

            return CustomResponse.successResponse(
                data={
                    "id": str(activity.id),
                    "date": activity.date,
                    "title": activity.title,
                },
                total=1,
                description="Activity created successfully."
            )

        except Exception as e:
            application_logger.exception(
                f"Activity creation error: {str(e)}"
            )
            return CustomResponse.errorResponse(
                description="Unable to create activity."
            )

class ActivityStepsAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]






    def get(self, request, activity_id):

        try:
            activity = self.get_activity(activity_id)

            steps = activity.activity_steps.all()

            data = [
                {
                    "id": str(step.id),
                    "step_number": step.step_number,
                    "title": step.title,
                    "description": step.description,
                    "image": step.image,
                }
                for step in steps
            ]

            return CustomResponse.successResponse(
                data=data,
                total=len(data),
                description="Activity steps fetched successfully."
            )

        except Activities.DoesNotExist:
            return CustomResponse.errorResponse(
                description="Activity not found."
            )

        except Exception as e:
            application_logger.exception(
                f"Activity steps fetch error: {str(e)}"
            )
            return CustomResponse.errorResponse(
                description="Unable to fetch activity steps."
            )

    def post(self, request, activity_id):

        try:
            activity = self.get_activity(activity_id)
            data = request.data

            step_number = data.get("step_number")
            description = data.get("description")

            if step_number is None:
                return CustomResponse.errorResponse(
                    description="Step number is required."
                )

            if not description:
                return CustomResponse.errorResponse(
                    description="Step description is required."
                )

            try:
                step_number = int(step_number)
                if step_number <= 0:
                    raise ValueError
            except (ValueError, TypeError):
                return CustomResponse.errorResponse(
                    description="Step number must be a positive integer."
                )

            if ActivitySteps.objects.filter(
                activities=activity,
                step_number=step_number
            ).exists():
                return CustomResponse.errorResponse(
                    description="This step number already exists."
                )

            step = ActivitySteps.objects.create(
                activities=activity,
                step_number=step_number,
                title=data.get("title"),
                description=description,
                image=data.get("image"),
            )

            return CustomResponse.successResponse(
                data={
                    "id": str(step.id),
                    "step_number": step.step_number,
                    "title": step.title,
                    "description": step.description,
                    "image": step.image,
                },
                total=1,
                description="Activity step created successfully."
            )

        except Activities.DoesNotExist:
            return CustomResponse.errorResponse(
                description="Activity not found."
            )

        except Exception as e:
            application_logger.exception(
                f"Activity step creation error: {str(e)}"
            )
            return CustomResponse.errorResponse(
                description="Unable to create activity step."
            )