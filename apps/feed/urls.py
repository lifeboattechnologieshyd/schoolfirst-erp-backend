from django.urls import path

from apps.feed.views.feed import (
    FeedCommentDestroyView,
    FeedCommentListCreateView,
    FeedDetailView,
    FeedListCreateView,
    FeedReactionView,
    FeedSavedListView,
    FeedSaveView,
    FeedShareView,
)

urlpatterns = [
    path("v1/feed", FeedListCreateView.as_view(), name="feed-list-create"),
    path("v1/feed/saved", FeedSavedListView.as_view(), name="feed-saved-list"),
    path("v1/feed/<uuid:feed_id>", FeedDetailView.as_view(), name="feed-detail"),
    path("v1/feed/<uuid:feed_id>/comments", FeedCommentListCreateView.as_view(), name="feed-comment-list-create"),
    path(
        "v1/feed/<uuid:feed_id>/comments/<uuid:comment_id>",
        FeedCommentDestroyView.as_view(),
        name="feed-comment-detail",
    ),
    path("v1/feed/<uuid:feed_id>/react", FeedReactionView.as_view(), name="feed-react"),
    path("v1/feed/<uuid:feed_id>/save", FeedSaveView.as_view(), name="feed-save"),
    path("v1/feed/<uuid:feed_id>/share", FeedShareView.as_view(), name="feed-share"),
]
