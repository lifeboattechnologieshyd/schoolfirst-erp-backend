from datetime import date

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from apps.activities.models import Activities
from shared.mixins import CustomResponse
from shared.utils.logger import application_logger


class ActivityAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        try:
            activity_date = request.query_params.get("date")

            if not activity_date:
                return CustomResponse.errorResponse(
                    description="Date is required.",
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                activity_date = date.fromisoformat(activity_date)

            except (ValueError, TypeError):
                return CustomResponse.errorResponse(
                    description="Invalid date format. Use YYYY-MM-DD.",
                    status=status.HTTP_400_BAD_REQUEST,
                )

            activity = Activities.objects.filter(
                date=activity_date
            ).first()

            if not activity:
                return CustomResponse.successResponse(
                    data={},
                    total=0,
                    description="No activity found for the selected date."
                )

            data = {
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

            return CustomResponse.successResponse(
                data=data,
                total=1,
                description="Activity fetched successfully."
            )

        except Exception as e:

            application_logger.exception(
                "frontend_activity_fetch_failed user_id=%s error=%s",
                request.user.id,
                str(e),
            )

            return CustomResponse.errorResponse(
                description="Unable to fetch activity."
            )