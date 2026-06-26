
from django.urls import path

from apps.fee.views.fee import PendingStudentFeeAPIView, CreatePaymentAPIView, PhonePeWebhookAPIView

urlpatterns = [
        path("student-fee/pending",PendingStudentFeeAPIView.as_view(),),
        path("create/payment",CreatePaymentAPIView.as_view(),),
        path("phonepe/webhook",PhonePeWebhookAPIView.as_view(),),

]