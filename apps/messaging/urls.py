from django.urls import path

from apps.messaging.views.messaging import MessagingContactLISTAPIView, MessagingTeacherDetailAPIView, \
    ParentNoteCreateAPIView, ParentNoteDeleteAPIView, StartConversationAPIView, ParentMessageLISTAPIView, \
    ParentMessageSendAPIView

urlpatterns = [

    path("contacts", MessagingContactLISTAPIView.as_view()),

    path("teachers/<uuid:staff_id>", MessagingTeacherDetailAPIView.as_view()),

    path("notes/create", ParentNoteCreateAPIView.as_view()),

    path("notes/delete/<uuid:note_id>", ParentNoteDeleteAPIView.as_view()),

    path("conversations/start", StartConversationAPIView.as_view()),

    path("conversations/<uuid:conversation_id>/messages", ParentMessageLISTAPIView.as_view()),

    path("conversations/<uuid:conversation_id>/messages/send", ParentMessageSendAPIView.as_view()),

]
