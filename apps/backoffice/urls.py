from django.urls import path

from apps.backoffice.views.fee import CreateFeeTypeAPIView, FeeTypeListAPIView, UpdateFeeTypeAPIView, \
    DeleteFeeTypeAPIView, CreateFeeTemplateAPIView, FeeTemplateListAPIView, FeeTemplateDetailAPIView, \
    UpdateFeeTemplateAPIView, DeleteFeeTemplateAPIView, CreateFeeTemplateItemAPIView, FeeTemplateItemListAPIView, \
    FeeTemplateItemDetailAPIView, UpdateFeeTemplateItemAPIView, DeleteFeeTemplateItemAPIView, \
    CreateFeeCollectionPlanAPIView, FeeCollectionPlanListAPIView, FeeCollectionPlanDetailAPIView, \
    UpdateFeeCollectionPlanAPIView, CreateFeeInstallmentAPIView, FeeInstallmentListAPIView, FeeInstallmentDetailAPIView, \
    UpdateFeeInstallmentAPIView, CreateFeeInstallmentItemAPIView, FeeInstallmentItemListAPIView, \
    FeeInstallmentItemDetailAPIView, UpdateFeeInstallmentItemAPIView, CreateLateFeeRuleAPIView, LateFeeRuleListAPIView, \
    LateFeeRuleDetailAPIView, UpdateLateFeeRuleAPIView, CreateFeeConcessionAPIView, FeeConcessionListAPIView, \
    UpdateFeeConcessionAPIView, CreateStudentFeeAssignmentAPIView, StudentFeeAssignmentListAPIView, \
    StudentFeeListAPIView, StudentFeeDetailAPIView, GenerateStudentFeesAPIView
from apps.backoffice.views.leads import \
    SchoolLeadRequestOTPAPIView, SchoolLeadListAPIView, SchoolLeadVerifyOTPAPIView
from apps.backoffice.views.ptm import CreateParentTeacherMeetingAPIView, ParentTeacherMeetingListAPIView, \
    UpdateParentTeacherMeetingAPIView, BulkPTMAttendanceAPIView
from apps.backoffice.views.rbac import ModuleListCreateAPIView, PermissionListCreateAPIView, RoleListCreateAPIView, \
    AssignPermissionsToRoleAPIView, AssignRoleToUserAPIView, RBACDashboardAPIView, UserAccessAPIView, ModulesAPIView, \
    ModulePermissionsAPIView, RolesAPIView, RoleAccessAPIView
from apps.backoffice.views.school import AcademicYearListAPIView, CreateAcademicYearAPIView, UpdateAcademicYearAPIView, \
    CreateGradeAPIView, GradeListAPIView, UpdateGradeAPIView, CreateSectionAPIView, SectionListAPIView, \
    UpdateSectionAPIView, CreateStudentAPIView, BulkUploadStudentAPIView, StudentListAPIView, \
    CreateStudentDocumentAPIView, StudentDocumentListAPIView, UpdateStudentDocumentAPIView, \
    DownloadStudentTemplateAPIView, CreateStaffAPIView, GetStaffAPIView, UpdateStaffAPIView, CreateStaffDocumentAPIView, \
    StaffDocumentListAPIView, UpdateStaffDocumentAPIView
from apps.backoffice.views.superadmin import CreateSuperAdminAPIView, SuperAdminRequestOTPAPIView, \
    SuperAdminVerifyOTPAPIView, SchoolLeadUpdateAPIView, OrganizationListAPIView, CreateOrganizationAPIView, \
    UpdateOrganizationAPIView, SchoolListAPIView, CreateSchoolAPIView, UpdateSchoolAPIView, CreateBranchAPIView, \
    UpdateBranchAPIView, BranchListAPIView, UserListAPIView, GetSchoolClientInfoAPIView, \
    CreateSchoolConfigurationAPIView, GetSchoolConfigurationAPIView, UpdateSchoolConfigurationAPIView

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

    path("configuration/create",CreateSchoolConfigurationAPIView.as_view(),),

    path("configuration",GetSchoolConfigurationAPIView.as_view(),),

    path("configuration/update",UpdateSchoolConfigurationAPIView.as_view(),),

    path("client-info",GetSchoolClientInfoAPIView.as_view(),name="client-info"),

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

    path("grades/create",CreateGradeAPIView.as_view()),

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

    path("students/download-template",DownloadStudentTemplateAPIView.as_view(),name="download-student-template",),

    path("students",StudentListAPIView.as_view(),name="student-list",),

    path("students/document/create",CreateStudentDocumentAPIView.as_view(),name="student-document",),

    path("students/document",StudentDocumentListAPIView.as_view(),name="student-document-list",),

    path("students/document/<uuid:document_id>",UpdateStudentDocumentAPIView.as_view(),name="student-document-update",),

    # ====================================
    #  Fee APIs
    # ====================================

    path("fee-types/create",CreateFeeTypeAPIView.as_view(),name="fee-type-create",),

    path("fee-types",FeeTypeListAPIView.as_view(),name="fee-type-list",),

    path("fee-types/<uuid:fee_type_id>",UpdateFeeTypeAPIView.as_view(),name="fee-type-update",),

    path("fee-types/<uuid:fee_type_id>/delete",DeleteFeeTypeAPIView.as_view(),name="fee-type-delete",),

    path("fee-templates/create",CreateFeeTemplateAPIView.as_view(),name="fee-template-create",),

    path("fee-templates",FeeTemplateListAPIView.as_view(),name="fee-template-list",),

    # path("fee-templates/<uuid:fee_template_id>",FeeTemplateDetailAPIView.as_view(),name="fee-template-detail",),

    path( "fee-templates/<uuid:fee_template_id>",UpdateFeeTemplateAPIView.as_view(),name="fee-template-update",),

    path("fee-templates/<uuid:fee_template_id>/delete",DeleteFeeTemplateAPIView.as_view(),name="fee-template-delete",),

    path("fee-template-items/create",CreateFeeTemplateItemAPIView.as_view(),),

    path("fee-template-items",FeeTemplateItemListAPIView.as_view(),),

    # path("fee-template-items/<uuid:fee_template_item_id>",FeeTemplateItemDetailAPIView.as_view(),),

    path("fee-template-items/<uuid:fee_template_item_id>", UpdateFeeTemplateItemAPIView.as_view(),),

    path("fee-template-items/<uuid:fee_template_item_id>/delete",DeleteFeeTemplateItemAPIView.as_view(),),

    path("fee-collection-plans/create",CreateFeeCollectionPlanAPIView.as_view(),),

    path("fee-collection-plans",FeeCollectionPlanListAPIView.as_view(),),

    # path("fee-collection-plans/<uuid:collection_plan_id>",FeeCollectionPlanDetailAPIView.as_view(),),

    path("fee-collection-plans/<uuid:collection_plan_id>",UpdateFeeCollectionPlanAPIView.as_view(),),

    path("fee-installments/create",CreateFeeInstallmentAPIView.as_view(),),

    path("fee-installments",FeeInstallmentListAPIView.as_view(),),

    # path("fee-installments/<uuid:installment_id>",FeeInstallmentDetailAPIView.as_view(),),

    path("fee-installments/<uuid:installment_id>",UpdateFeeInstallmentAPIView.as_view(),),

    path("fee-installment-items/create",CreateFeeInstallmentItemAPIView.as_view(),),

    path( "fee-installment-items",FeeInstallmentItemListAPIView.as_view(),),

    # path("fee-installment-items/<uuid:installment_item_id>",FeeInstallmentItemDetailAPIView.as_view(),),

    path("fee-installment-items/<uuid:installment_item_id>",UpdateFeeInstallmentItemAPIView.as_view(),),

    path("late-fee-rules/create",CreateLateFeeRuleAPIView.as_view(),),

    path("late-fee-rules",LateFeeRuleListAPIView.as_view()),

    # path("late-fee-rules/<uuid:late_fee_rule_id>",LateFeeRuleDetailAPIView.as_view(),),

    path("late-fee-rules/<uuid:late_fee_rule_id>",UpdateLateFeeRuleAPIView.as_view(),),

    path("fee-concessions/create",CreateFeeConcessionAPIView.as_view()),

    path("fee-concessions",FeeConcessionListAPIView.as_view(),),

    path("fee-concessions/<uuid:concession_id>", UpdateFeeConcessionAPIView.as_view(),),

    path("student-fee-assignments/create",CreateStudentFeeAssignmentAPIView.as_view(),),

    path("student-fee-assignments", StudentFeeAssignmentListAPIView.as_view(),),

    path("student-fees",StudentFeeListAPIView.as_view(),),

    path("student-fees/<uuid:student_fee_id>",StudentFeeDetailAPIView.as_view(),),

    path("generate-student-fees",GenerateStudentFeesAPIView.as_view(),),

    # ====================================
    #  staff APIs
    # ====================================

    path("staff/create",CreateStaffAPIView.as_view(),),

    path("staff",GetStaffAPIView.as_view(),),

    path("staff/<uuid:staff_id>",UpdateStaffAPIView.as_view(),),

    path("staff/documents/create",CreateStaffDocumentAPIView.as_view(),),

    path("staff/documents",StaffDocumentListAPIView.as_view(),),

    path("staff/documents/<uuid:document_id>",UpdateStaffDocumentAPIView.as_view(),),

    # ====================================
    #  ptm APIs
    # ====================================

    path("ptm/create",CreateParentTeacherMeetingAPIView.as_view(),),

    path("ptm",ParentTeacherMeetingListAPIView.as_view(),),

    path("ptm/<uuid:meeting_id>",UpdateParentTeacherMeetingAPIView.as_view(),),

    path("ptm/attendance",BulkPTMAttendanceAPIView.as_view(),),








]