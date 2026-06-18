from django.urls import path

from apps.backoffice.views.leads import \
    SchoolLeadRequestOTPAPIView, SchoolLeadListAPIView, SchoolLeadVerifyOTPAPIView
from apps.backoffice.views.rbac import ModuleListCreateAPIView, PermissionListCreateAPIView, RoleListCreateAPIView, \
    AssignPermissionsToRoleAPIView, AssignRoleToUserAPIView, RBACDashboardAPIView, UserAccessAPIView, ModulesAPIView, \
    ModulePermissionsAPIView, RolesAPIView, RoleAccessAPIView
from apps.backoffice.views.school import AcademicYearListAPIView, CreateAcademicYearAPIView, UpdateAcademicYearAPIView, \
    CreateGradeAPIView, GradeListAPIView, UpdateGradeAPIView, CreateSectionAPIView, SectionListAPIView, \
    UpdateSectionAPIView, CreateStudentAPIView, BulkUploadStudentAPIView, StudentListAPIView, \
    CreateStudentDocumentAPIView, StudentDocumentListAPIView, UpdateStudentDocumentAPIView
from apps.backoffice.views.superadmin import CreateSuperAdminAPIView, SuperAdminRequestOTPAPIView, \
    SuperAdminVerifyOTPAPIView, SchoolLeadUpdateAPIView, OrganizationListAPIView, CreateOrganizationAPIView, \
    UpdateOrganizationAPIView, SchoolListAPIView, CreateSchoolAPIView, UpdateSchoolAPIView, CreateBranchAPIView, \
    UpdateBranchAPIView, BranchListAPIView, UserListAPIView

urlpatterns = [



    path("leads/request-otp", SchoolLeadRequestOTPAPIView.as_view(), name="school-lead-request-otp"),

    path("leads/verify-otp", SchoolLeadVerifyOTPAPIView.as_view(), name="school-lead-verify-otp"),

    path("create/super-admin", CreateSuperAdminAPIView.as_view(), name="create-super-admin"),

    path("super-admin/request-otp",SuperAdminRequestOTPAPIView.as_view()),

    path("super-admin/verify-otp",SuperAdminVerifyOTPAPIView.as_view(),),

    path("leads", SchoolLeadListAPIView.as_view(), name="school-lead-list"),

    path("leads/<uuid:lead_id>", SchoolLeadUpdateAPIView.as_view(), name="lead-update"),


    path("modules", ModuleListCreateAPIView.as_view(), name="module-list-create"),

    path("permissions", PermissionListCreateAPIView.as_view(), name="permission-list-create"),

    path("roles", RoleListCreateAPIView.as_view(), name="role-list-create"),


    path("roles/<uuid:role_id>/assign-permissions", AssignPermissionsToRoleAPIView.as_view(), name="role-assign-permissions"),

    path("user-roles/assign", AssignRoleToUserAPIView.as_view(), name="assign-role-to-user"),

    path("rbac/dashboard", RBACDashboardAPIView.as_view(), name="rbac-dashboard"),

    path("user/list",UserListAPIView.as_view(),name="user-list"),

    path("users/<uuid:user_id>/access",UserAccessAPIView.as_view(),),

    path("rbac/roles",RolesAPIView.as_view(),name="roles",),


   path("rbac/modules/filter",ModulesAPIView.as_view(),name="module-filter",),

   path("rbac/roles/<uuid:role_id>/access",RoleAccessAPIView.as_view(),name="role-access") ,

   path( "rbac/modules/<uuid:module_id>/permissions",ModulePermissionsAPIView.as_view(),name="module-permissions"),

    # ====================================
    # Organization APIs
    # ====================================

    path("organizations",OrganizationListAPIView.as_view(),name="organization-list",),

    path("organizations/create",CreateOrganizationAPIView.as_view(),name="organization-create",),

    path("organizations/<uuid:organization_id>",UpdateOrganizationAPIView.as_view(),name="organization-update",),

    # ====================================
    # School APIs
    # ====================================

    path("schools",SchoolListAPIView.as_view(),name="school-list",),

    path("schools/create",CreateSchoolAPIView.as_view(),name="school-create",),

    path("schools/<uuid:school_id>", UpdateSchoolAPIView.as_view(),name="school-update",),

    # ====================================
    # Branch APIs
    # ====================================

    path( "branches",BranchListAPIView.as_view(),name="branch-list",),

    path("branches/create",CreateBranchAPIView.as_view(),name="branch-create",),

    path("branches/<uuid:branch_id>",UpdateBranchAPIView.as_view(),name="branch-update",),

    # ====================================
    # academic year APIs
    # ====================================

    path("academic-years",AcademicYearListAPIView.as_view(),name="academic-year-list", ),

    path("academic-years/create",CreateAcademicYearAPIView.as_view(),name="academic-year-create",),

    path("academic-years/<uuid:academic_year_id>",UpdateAcademicYearAPIView.as_view(),name="academic-year-update",),

    # ====================================
    # Grade  APIs
    # ====================================

    path("grade/create",CreateGradeAPIView.as_view()),

    path("grades",GradeListAPIView.as_view(),),

    path("grades/<uuid:grade_id>",UpdateGradeAPIView.as_view(),),

    # ====================================
    #  Section APIs
    # ====================================

    path("sections/create",CreateSectionAPIView.as_view(),),

    path("sections",SectionListAPIView.as_view()),

    path("sections/<uuid:section_id>",UpdateSectionAPIView.as_view(),),

    path("students/create",CreateStudentAPIView.as_view(),name="student-create",),

    path("students/bulkupload",BulkUploadStudentAPIView.as_view(),name="bulk-upload-student",),

    path("students",StudentListAPIView.as_view(),name="student-list",),

    path("students/document/create",CreateStudentDocumentAPIView.as_view(),name="student-document",),

    path("students/document",StudentDocumentListAPIView.as_view(),name="student-document-list",),

    path("students/document/<uuid:document_id>",UpdateStudentDocumentAPIView.as_view(),name="student-document-update",),




]