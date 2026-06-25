
from django.urls import path

from apps.fee.views.fee import PendingStudentFeeAPIView

urlpatterns = [
        path("student-fee/pending",PendingStudentFeeAPIView.as_view(),),

]