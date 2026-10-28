
from django.urls import path

from apps.fee.views.fee import PendingStudentFeeAPIView, CreatePaymentAPIView, PhonePeWebhookAPIView, \
        CompletedStudentFeePaymentsAPIView, VerifyPaymentAPIView

urlpatterns = [
        path("student-fee/pending",PendingStudentFeeAPIView.as_view(),),
        path("create/payment",CreatePaymentAPIView.as_view(),),
        path("verify/payment",VerifyPaymentAPIView.as_view(),),
        path("phonepe/webhook",PhonePeWebhookAPIView.as_view(),),
        path("completed/payment",CompletedStudentFeePaymentsAPIView.as_view(),),

]