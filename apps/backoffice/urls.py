from django.urls import path

from apps.backoffice.views.leads import SchoolLeadListCreateAPIView, SchoolLeadDetailAPIView, SchoolLeadSendOTPAPIView, \
    SchoolLeadVerifyOTPAPIView
from apps.backoffice.views.rbac import ModuleListCreateAPIView, PermissionListCreateAPIView, RoleListCreateAPIView, \
    RoleDetailAPIView, AssignPermissionsToRoleAPIView, AssignRoleToUserAPIView, AssignPermissionToUserAPIView

urlpatterns = [

    path("leads", SchoolLeadListCreateAPIView.as_view(), name="school-lead-list-create"),

    path("leads/<uuid:lead_id>", SchoolLeadDetailAPIView.as_view(), name="school-lead-detail"),

    path("leads/<uuid:lead_id>/send-otp", SchoolLeadSendOTPAPIView.as_view(), name="school-lead-send-otp"),

    path("leads/<uuid:lead_id>/verify-otp", SchoolLeadVerifyOTPAPIView.as_view(), name="school-lead-verify-otp"),

    path("modules", ModuleListCreateAPIView.as_view(), name="module-list-create"),

    path("permissions", PermissionListCreateAPIView.as_view(), name="permission-list-create"),

    path("roles", RoleListCreateAPIView.as_view(), name="role-list-create"),

    path("roles/<uuid:role_id>", RoleDetailAPIView.as_view(), name="role-detail"),

    path("roles/<uuid:role_id>/assign-permissions", AssignPermissionsToRoleAPIView.as_view(), name="role-assign-permissions"),

    path("user-roles/assign", AssignRoleToUserAPIView.as_view(), name="assign-role-to-user"),

    path("user-permissions/assign", AssignPermissionToUserAPIView.as_view(), name="assign-permission-to-user"),



]