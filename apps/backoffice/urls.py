from django.urls import path

from apps.backoffice.views.leads import \
    SchoolLeadRequestOTPAPIView, SchoolLeadListAPIView, SchoolLeadVerifyOTPAPIView
from apps.backoffice.views.rbac import ModuleListCreateAPIView, PermissionListCreateAPIView, RoleListCreateAPIView, \
    RoleDetailAPIView, AssignPermissionsToRoleAPIView, AssignRoleToUserAPIView, AssignPermissionToUserAPIView

urlpatterns = [



    path("leads/request-otp", SchoolLeadRequestOTPAPIView.as_view(), name="school-lead-request-otp"),

    path("leads/verify-otp", SchoolLeadVerifyOTPAPIView.as_view(), name="school-lead-verify-otp"),

    path("leads", SchoolLeadListAPIView.as_view(), name="school-lead-list"),


    path("modules", ModuleListCreateAPIView.as_view(), name="module-list-create"),

    path("permissions", PermissionListCreateAPIView.as_view(), name="permission-list-create"),

    path("roles", RoleListCreateAPIView.as_view(), name="role-list-create"),

    path("roles/<uuid:role_id>", RoleDetailAPIView.as_view(), name="role-detail"),

    path("roles/<uuid:role_id>/assign-permissions", AssignPermissionsToRoleAPIView.as_view(), name="role-assign-permissions"),

    path("user-roles/assign", AssignRoleToUserAPIView.as_view(), name="assign-role-to-user"),

    path("user-permissions/assign", AssignPermissionToUserAPIView.as_view(), name="assign-permission-to-user"),



]