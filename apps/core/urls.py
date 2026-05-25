from django.urls import path

from apps.core.views import FileUploadView
from apps.core.views.auth.invitations import (
    InvitationCodeCreateView,
    InvitationCodeDeleteView,
    InvitationCodeListView,
    InvitationCodeUsersView,
    InvitationCodeValidateView,
)
from apps.core.views.close_group import (
    CloseGroupAddedMeView,
    CloseGroupDetailView,
    CloseGroupListView,
    CloseGroupMemberDeleteView,
    CloseGroupMemberListCreateView,
)
from apps.core.views.family import (
    FamilyDetailView,
    FamilyExitView,
    FamilyInvitationAcceptView,
    FamilyInvitationDeclineView,
    FamilyListCreateView,
    FamilyMemberDeleteView,
    FamilyMemberListCreateView,
)
from apps.core.views.membership import MembershipApplicationCrud
from apps.core.views.profile.profile import Profile
from apps.core.views.signup import (
    CustomTokenRefreshView,
    EmailVerifyView,
    InviteCodeValidateView,
    LoginView,
    PasswordResetRequestView,
    PasswordResetVerifyView,
    SetPasswordView,
)
from apps.core.views.user_lookup import UserLookupView

urlpatterns = [
    # --- Auth & Invitations ---
    path("v1/auth/signup/invite/validate", InvitationCodeValidateView.as_view()),
    path("v1/auth/invitations/create", InvitationCodeCreateView.as_view()),
    path("v1/auth/invitations/list", InvitationCodeListView.as_view()),
    path("v1/auth/invitations/<str:code>/delete", InvitationCodeDeleteView.as_view()),
    path("v1/auth/invitations/<str:code>/users", InvitationCodeUsersView.as_view()),
    path("v1/auth/signup/email", InviteCodeValidateView.as_view()),
    path("v1/auth/signup/email/verify", EmailVerifyView.as_view()),
    path("v1/auth/login", LoginView.as_view()),
    path("v1/auth/refresh", CustomTokenRefreshView.as_view(), name="token_refresh"),
    path("v1/auth/password-reset/request", PasswordResetRequestView.as_view(), name="password-reset-request"),
    path("v1/auth/password-reset/verify", PasswordResetVerifyView.as_view(), name="password-reset-verify"),
    path("v1/auth/set-password", SetPasswordView.as_view(), name="set-password"),
    path("v1/membership/apply", MembershipApplicationCrud.as_view()),
    path("v1/user/profile", Profile.as_view()),
    path("v1/upload", view=FileUploadView.as_view()),
    # --- Family ---
    path("v1/family", FamilyListCreateView.as_view(), name="family-list-create"),
    path("v1/family/<uuid:family_id>", FamilyDetailView.as_view(), name="family-detail"),
    path("v1/family/<uuid:family_id>/members", FamilyMemberListCreateView.as_view(), name="family-member-list-create"),
    path(
        "v1/family/<uuid:family_id>/members/<uuid:member_id>",
        FamilyMemberDeleteView.as_view(),
        name="family-member-delete",
    ),
    path("v1/family/<uuid:family_id>/exit", FamilyExitView.as_view(), name="family-exit"),
    path("v1/family/<uuid:family_id>/accept", FamilyInvitationAcceptView.as_view(), name="family-invitation-accept"),
    path(
        "v1/family/<uuid:family_id>/decline",
        FamilyInvitationDeclineView.as_view(),
        name="family-invitation-decline",
    ),
    # --- Close Group ---
    path("v1/close-group", CloseGroupListView.as_view(), name="close-group-list"),
    path("v1/close-group/added-me", CloseGroupAddedMeView.as_view(), name="close-group-added-me"),
    path("v1/close-group/<uuid:close_group_id>", CloseGroupDetailView.as_view(), name="close-group-detail"),
    path(
        "v1/close-group/<uuid:close_group_id>/members",
        CloseGroupMemberListCreateView.as_view(),
        name="close-group-member-list-create",
    ),
    path(
        "v1/close-group/<uuid:close_group_id>/members/<uuid:member_id>",
        CloseGroupMemberDeleteView.as_view(),
        name="close-group-member-delete",
    ),
    # --- User Lookup ---
    path("v1/users/lookup", UserLookupView.as_view(), name="user-lookup"),
]
