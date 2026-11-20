from django.urls import path

from apps.edutainment.views.feed import FeedLISTAPIView, FeedLikeAPIView, FeedUnlikeAPIView, FeedShareAPIView, \
    FeedCommentDeleteAPIView, FeedCommentCreateAPIView, FeedCommentsListAPIView

urlpatterns = [

    path("feeds",FeedLISTAPIView.as_view(),),

    path("feeds/<uuid:feed_id>/like",FeedLikeAPIView.as_view(),),

    path("feeds/<uuid:feed_id>/unlike",FeedUnlikeAPIView.as_view(),),

    path("feeds/<uuid:feed_id>/comments",FeedCommentsListAPIView.as_view(),),

    path("feeds/<uuid:feed_id>/comments/create",FeedCommentCreateAPIView.as_view(),),

    path("feeds/<uuid:feed_id>/comments/<uuid:comment_id>/delete",FeedCommentDeleteAPIView.as_view(),),

    path("feeds/<uuid:feed_id>/share",FeedShareAPIView.as_view(),
    ),
]