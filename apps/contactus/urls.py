from django.urls import path

from apps.contactus.views.contactus import CreateSupportTicketAPIView, SupportTicketDetailAPIView, \
    SendSupportMessageAPIView, SubmitSupportTicketRatingAPIView

urlpatterns = [

    path("support/tickets",CreateSupportTicketAPIView.as_view()),
    path("support/tickets/<uuid:ticket_id>",SupportTicketDetailAPIView.as_view()),
    path("support/tickets/message", SendSupportMessageAPIView.as_view()),
    path("support/tickets/rate",SubmitSupportTicketRatingAPIView.as_view()),
]