from datetime import timedelta

from django.db.models import Q, Prefetch

from django.utils import timezone
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.backoffice.views.leads import normalize_email, normalize_mobile
from apps.core.models import UserRoles, Roles, Permissions, RolePermissions, UserOTP, UserMaster
from apps.school.models import SchoolLead
from apps.school.models.school import Organization, School, Branch, SchoolConfiguration, SchoolClient
from shared.enums.roles import RolesEnum
from shared.helpers.rbac import check_permission, has_role
from shared.mixins import CustomResponse, CustomPageNumberPagination

from django.contrib.auth.models import Group, Permission
from django.db import transaction
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from rest_framework import status

from django.shortcuts import get_object_or_404

from shared.permissions import HasPermission
from shared.utils.logger import application_logger
from shared.utils.otp import generate_otp, send_otp_to_mobile


class CreateSuperAdminAPIView(APIView):

    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):

        application_logger.info(
            "superadmin_create_started",
            user_id=str(request.user.id),
            username=request.user.username,
            mobile=request.user.mobile,
        )

        try:

            role, created = Roles.objects.get_or_create(
                role_name="SUPERADMIN",
                defaults={
                    "description": "Platform Super Admin",
                },
            )

            application_logger.info(
                "superadmin_role_processed",
                role_id=str(role.id),
                role_name=role.role_name,
                role_created=created,
            )

            all_permissions = Permissions.objects.all()

            application_logger.info(
                "superadmin_permissions_loaded",
                total_permissions=all_permissions.count(),
            )

            assigned_permissions = 0

            for permission in all_permissions:

                _, permission_created = RolePermissions.objects.get_or_create(
                    role=role,
                    permission=permission,
                )

                if permission_created:
                    assigned_permissions += 1

            application_logger.info(
                "superadmin_permissions_assigned",
                role_id=str(role.id),
                assigned_permissions=assigned_permissions,
            )

            user_role, user_role_created = UserRoles.objects.get_or_create(
                user=request.user,
                role=role,
                school=None,
            )

            application_logger.info(
                "superadmin_user_role_processed",
                user_role_id=str(user_role.id),
                user_id=str(request.user.id),
                role_name=role.role_name,
                created=user_role_created,
            )

            application_logger.info(
                "superadmin_created",
                user_id=str(request.user.id),
                role_id=str(role.id),
                permissions_count=all_permissions.count(),
                assigned_permissions=assigned_permissions,
            )

            return CustomResponse.successResponse(
                data={
                    "role_id": str(role.id),
                    "role_name": role.role_name,
                    "permissions_count": all_permissions.count(),
                    "user_role_created": user_role_created,
                },
                description="SUPERADMIN role created successfully.",
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:

            application_logger.exception(
                "superadmin_create_failed",
                user_id=str(request.user.id),
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description="Something went wrong while creating SUPERADMIN."
            )



class SuperAdminRequestOTPAPIView(APIView):

    permission_classes = [AllowAny]

    def post(self, request):

        mobile = normalize_mobile(
            request.data.get("phone_number")
        )

        application_logger.info(
            "superadmin_request_otp_started",
            mobile=mobile,
        )

        try:

            if not mobile:

                application_logger.warning(
                    "superadmin_request_otp_failed",
                    reason="mobile_missing",
                )

                return CustomResponse.errorResponse(
                    description="mobile is required.",
                    status=status.HTTP_400_BAD_REQUEST,
                )

            user = UserMaster.objects.filter(
                mobile=mobile,
                is_active=True,
            ).first()

            if not user:

                application_logger.warning(
                    "superadmin_request_otp_failed",
                    reason="user_not_found",
                    mobile=mobile,
                )

                return CustomResponse.errorResponse(
                    description="User not found.",
                    status=status.HTTP_404_NOT_FOUND,
                )

            application_logger.info(
                "superadmin_user_found",
                user_id=str(user.id),
                mobile=user.mobile,
            )

            is_superadmin = UserRoles.objects.filter(
                user=user,
                role__role_name="SUPERADMIN",
            ).exists()

            if not is_superadmin:

                application_logger.warning(
                    "superadmin_request_otp_failed",
                    reason="not_superadmin",
                    user_id=str(user.id),
                )

                return CustomResponse.errorResponse(
                    description="Only SUPERADMIN can login here.",
                    status=status.HTTP_403_FORBIDDEN,
                )

            otp = generate_otp()

            send_otp_to_mobile(
                otp,
                mobile,
            )

            UserOTP.objects.create(
                mobile=int(mobile),
                otp=otp,
                expires_at=timezone.now() + timedelta(minutes=15),
                is_used=False,
            )

            application_logger.info(
                "superadmin_otp_sent",
                user_id=str(user.id),
                mobile=mobile,
            )

            return CustomResponse.successResponse(
                data={
                    "mobile_otp": otp,
                },
                description="OTP sent successfully.",
                status=status.HTTP_200_OK,
            )

        except Exception as e:

            application_logger.exception(
                "superadmin_request_otp_failed",
                mobile=mobile,
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description="Something went wrong while sending OTP.",
            )


class SuperAdminVerifyOTPAPIView(APIView):

    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):

        phone_number = normalize_mobile(
            request.data.get("phone_number")
        )

        otp = str(
            request.data.get("otp", "")
        ).strip()

        application_logger.info(
            "superadmin_verify_otp_started",
            mobile=phone_number,
        )

        try:

            if not phone_number or not otp:

                application_logger.warning(
                    "superadmin_verify_otp_failed",
                    reason="mobile_or_otp_missing",
                )

                return CustomResponse.errorResponse(
                    description="mobile and otp are required.",
                    status=status.HTTP_400_BAD_REQUEST,
                )

            user = UserMaster.objects.filter(
                mobile=phone_number,
                is_active=True,
            ).first()

            if not user:

                application_logger.warning(
                    "superadmin_verify_otp_failed",
                    reason="user_not_found",
                    mobile=phone_number,
                )

                return CustomResponse.errorResponse(
                    description="User not found.",
                    status=status.HTTP_404_NOT_FOUND,
                )

            otp_obj = (
                UserOTP.objects.filter(
                    mobile=int(phone_number),
                    otp=otp,
                    is_used=False,
                    expires_at__gt=timezone.now(),
                )
                .order_by("-created_at")
                .first()
            )

            if not otp_obj:

                application_logger.warning(
                    "superadmin_verify_otp_failed",
                    reason="invalid_or_expired_otp",
                    mobile=phone_number,
                )

                return CustomResponse.errorResponse(
                    description="Invalid or expired OTP.",
                    status=status.HTTP_400_BAD_REQUEST,
                )

            otp_obj.is_used = True
            otp_obj.save(
                update_fields=[
                    "is_used",
                ]
            )

            user_role = UserRoles.objects.filter(
                user=user,
                role__role_name="SUPERADMIN",
            ).exists()

            if not user_role:

                application_logger.warning(
                    "superadmin_verify_otp_failed",
                    reason="role_not_assigned",
                    user_id=str(user.id),
                )

                return CustomResponse.errorResponse(
                    description="SUPERADMIN role not assigned.",
                    status=status.HTTP_403_FORBIDDEN,
                )

            refresh = RefreshToken.for_user(user)

            application_logger.info(
                "superadmin_login_success",
                user_id=str(user.id),
                mobile=user.mobile,
            )

            return CustomResponse.successResponse(
                data={
                    "user": {
                        "id": str(user.id),
                        "username": user.username,
                        "mobile": user.mobile,
                        "email": user.email,
                        "first_name": user.first_name,
                    },
                    "tokens": {
                        "access": str(refresh.access_token),
                        "refresh": str(refresh),
                    },
                },
                description="SUPERADMIN login successful.",
                status=status.HTTP_200_OK,
            )

        except Exception as e:

            application_logger.exception(
                "superadmin_verify_otp_failed",
                mobile=phone_number,
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description="Something went wrong while verifying OTP.",
            )


class SchoolLeadListAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        user = request.user

        application_logger.info(
            "school_lead_list_started",
            user_id=str(user.id),
        )

        try:

            is_superadmin = UserRoles.objects.filter(
                user=user,
                role__role_name="SUPERADMIN",
            ).exists()

            if not is_superadmin:

                application_logger.warning(
                    "school_lead_list_failed",
                    reason="not_superadmin",
                    user_id=str(user.id),
                )

                return CustomResponse.errorResponse(
                    description="Only SUPERADMIN can login here.",
                    status=status.HTTP_403_FORBIDDEN,
                )

            leads = SchoolLead.objects.all()

            application_logger.info(
                "school_lead_list_fetched",
                user_id=str(user.id),
                total_leads=leads.count(),
            )

            return CustomResponse.successResponse(
                {
                    "data": [
                        {
                            "id": str(lead.id),
                            "school_name": lead.school_name,
                            "contact_person": lead.contact_person,
                            "phone_number": lead.phone_number,
                            "email": lead.email,
                            "is_verified": lead.is_verified,
                            "status": lead.status,
                        }
                        for lead in leads
                    ]
                }
            )

        except Exception as e:

            application_logger.exception(
                "school_lead_list_failed",
                user_id=str(user.id),
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description="Something went wrong while fetching school leads.",
            )
class SchoolLeadUpdateAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def put(self, request, lead_id):

        user = request.user

        is_superadmin = UserRoles.objects.filter(

            user=user,

            role__role_name="SUPERADMIN",

        ).exists()

        if not is_superadmin:

            return CustomResponse.errorResponse(

                description="Only SUPERADMIN can update leads.",

                status=status.HTTP_403_FORBIDDEN,

            )

        lead = get_object_or_404(SchoolLead, id=lead_id)

        school_name = request.data.get("school_name", lead.school_name)

        contact_person = request.data.get("contact_person", lead.contact_person)

        number_of_students = request.data.get("number_of_students", lead.number_of_students)

        location = request.data.get("location", lead.location)

        email = request.data.get("email", lead.email)

        phone_number = request.data.get("phone_number", lead.phone_number)

        if email is not None:

            email = normalize_email(email)

        if phone_number is not None:

            phone_number = normalize_mobile(phone_number)

        lead.school_name = school_name

        lead.contact_person = contact_person

        lead.number_of_students = number_of_students

        lead.location = location

        lead.email = email

        lead.phone_number = phone_number

        lead.save()

        return CustomResponse.successResponse(

            data={

                "id": str(lead.id),

                "school_name": lead.school_name,

                "contact_person": lead.contact_person,

                "number_of_students": lead.number_of_students,

                "location": lead.location,

                "phone_number": lead.phone_number,

                "email": lead.email,

                "is_verified": lead.is_verified,

                "status": lead.status,

            },

            description="Lead updated successfully.",

            status=status.HTTP_200_OK,

        )



# ===========================
# CREATE ORGANIZATION
# ===========================

class CreateOrganizationAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "organization.create"

    def post(self, request):

        check_permission(
            request=request,
            permission_name="organization.create",
            school_id=None,
        )

        organization = Organization.objects.create(
            name=request.data.get("name"),
            code=request.data.get("code"),
            email=request.data.get("email"),
            phone_number=request.data.get("phone_number"),
            address=request.data.get("address"),
            website=request.data.get("website"),
            logo=request.data.get("logo"),
            status=request.data.get(
                "status",
                Organization.Status.ACTIVE,
            ),
        )

        return CustomResponse.successResponse(
            description="Organization created successfully",
            data={
                "id": organization.id,
            },
        )


# ===========================
# ORGANIZATION LIST
# ===========================

class OrganizationListAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "organization.view"

    def get(self, request):

        check_permission(
            request,
            "organization.view",
            None,
        )

        queryset = Organization.objects.all()

        search = request.GET.get("search")

        if search:
            queryset = queryset.filter(
                name__icontains=search
            )

        data = []

        for obj in queryset:

            data.append({
                "id": obj.id,
                "name": obj.name,
                "code": obj.code,
                "email": obj.email,
                "status": obj.status,
            })

        return CustomResponse.successResponse(
            data=data
        )


# ===========================
# UPDATE ORGANIZATION
# ===========================

class UpdateOrganizationAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "organization.update"

    def put(
        self,
        request,
        organization_id,
    ):

        check_permission(
            request,
            "organization.update",
            None,
        )

        organization = Organization.objects.filter(
            id=organization_id
        ).first()

        if not organization:
            return CustomResponse.errorResponse(
                description="Organization not found"
            )

        organization.name = request.data.get(
            "name",
            organization.name,
        )

        organization.address = request.data.get(
            "address",
            organization.address,
        )

        organization.website = request.data.get(
            "website",
            organization.website,
        )

        organization.logo = request.data.get(
            "logo",
            organization.logo,
        )

        organization.status = request.data.get(
            "status",
            organization.status,
        )

        organization.save()

        return CustomResponse.successResponse(
            description="Organization updated successfully"
        )


# ===========================
# CREATE SCHOOL
# ===========================

class CreateSchoolAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "school.create"

    def post(self, request):

        organization = Organization.objects.filter(
            id=request.data.get(
                "organization_id"
            )
        ).first()

        if not organization:
            return CustomResponse.errorResponse(
                description="Organization not found"
            )

        school = School.objects.create(
            organization=organization,
            name=request.data.get("name"),
            code=request.data.get("code"),
            board=request.data.get("board"),
            email=request.data.get("email"),
            phone_number=request.data.get("phone_number"),
            address=request.data.get("address"),
            city=request.data.get("city"),
            state=request.data.get("state"),
            country=request.data.get(
                "country",
                "India",
            ),
            primary_color=request.data.get("primary_color"),
            secondary_color=request.data.get("secondary_color"),

        )

        check_permission(
            request,
            "school.create",
            school.id,
        )

        return CustomResponse.successResponse(
            description="School created successfully",
            data={
                "id": school.id,
            },
        )


# ===========================
# SCHOOL LIST
# ===========================

class SchoolListAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "school.view"

    def get(self, request):

        application_logger.info(
            "school_list_started",
            user_id=str(request.user.id),
        )

        try:

            queryset = School.objects.select_related(
                "organization",
            ).prefetch_related(
                "branches",
            )

            data = []

            for obj in queryset:

                branches = []

                for branch in obj.branches.all():

                    branches.append({
                        "id": str(branch.id),
                        "name": branch.name,
                        "code": branch.code,
                        "status": branch.status,
                    })

                data.append({
                    "id": str(obj.id),
                    "name": obj.name,
                    "code": obj.code,
                    "organization_name": (
                        obj.organization.name
                        if obj.organization
                        else None
                    ),
                    "address": obj.address,
                    "logo": obj.logo,
                    "city": obj.city,
                    "primary_color": obj.primary_color,
                    "secondary_color": obj.secondary_color,
                    "board": obj.board,
                    "email": obj.email,
                    "phone_number": obj.phone_number,
                    "principal_name": obj.principal_name,
                    "principal_email": obj.principal_email,
                    "established_year": obj.established_year,
                    "pincode": obj.pincode,
                    "website": obj.website,
                    "state": obj.state,
                    "country": obj.country,
                    "is_email_verified": obj.is_email_verified,
                    "is_phone_verified": obj.is_phone_verified,
                    "status": obj.status,
                    "branches": branches,
                })

            application_logger.info(
                "school_list_fetched",
                user_id=str(request.user.id),
                total_count=len(data),
            )

            return CustomResponse.successResponse(
                data=data,
            )

        except Exception as e:

            application_logger.exception(
                "school_list_failed",
                user_id=str(request.user.id),
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description="Something went wrong while fetching schools.",
            )
# ===========================
# UPDATE SCHOOL
# ===========================

class UpdateSchoolAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "school.update"

    def put(
        self,
        request,
        school_id,
    ):

        school = School.objects.filter(
            id=school_id
        ).first()

        if not school:
            return CustomResponse.errorResponse(
                description="School not found"
            )

        check_permission(request,"school.update",school.id,)
        school.name = request.data.get("name",school.name,)
        school.address = request.data.get("address",school.address,)
        school.city = request.data.get("city",school.city,)
        school.state = request.data.get( "state",school.state,)
        school.status = request.data.get("status",school.status,)
        school.primary_color = request.data.get("primary_color",school.primary_color)
        school.secondary_color = request.data.get("secondary_color",school.secondary_color)
        school.principal_name = request.data.get("principal_name",school.principal_name)
        school.principal_email = request.data.get("principal_email",school.principal_email)
        school.email = request.data.get("email",school.email,)
        school.logo = request.data.get("logo",school.logo,)
        school.board = request.data.get("board",school.board,)
        school.website = request.data.get("website",school.website,)
        school.state = request.data.get("state",school.state,)
        school.country = request.data.get("country",school.country,)
        school.pincode = request.data.get("pincode",school.pincode,)


        school.save()

        return CustomResponse.successResponse(
            description="School updated successfully"
        )


# ===========================
# DELETE SCHOOL
# ===========================
class DeleteSchoolAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def delete(self,request,school_id,):

        check_permission(request=request,permission_name="school.delete",)

        school = School.objects.filter(id=school_id).first()
        if not school:
            return CustomResponse.errorResponse(description="School not found.",)

        school.soft_delete(request.user)

        return CustomResponse.successResponse(description="School deleted successfully.",)


# ===========================
# CREATE BRANCH
# ===========================

class CreateBranchAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "branch.create"

    def post(self, request):

        school = School.objects.filter(
            id=request.data.get(
                "school_id"
            )
        ).first()

        if not school:
            return CustomResponse.errorResponse(
                description="School not found"
            )

        check_permission(
            request,
            "branch.create",
            school.id,
        )

        branch = Branch.objects.create(
            school=school,
            name=request.data.get("name"),
            code=request.data.get("code"),
            email=request.data.get("email"),
            phone_number=request.data.get(
                "phone_number"
            ),
            address=request.data.get(
                "address"
            ),
            city=request.data.get("city"),
            state=request.data.get("state"),
        )

        return CustomResponse.successResponse(
            description="Branch created successfully",
            data={
                "id": branch.id,
            },
        )
# ===========================
#  BRANCH LIST
# ===========================


class BranchListAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "branch.view"

    def get(self, request):

        school_id = request.GET.get("school_id")

        check_permission(
            request=request,
            permission_name="branch.view",
            school_id=school_id,
        )

        queryset = Branch.objects.all()

        if school_id:
            queryset = queryset.filter(
                school_id=school_id,
            )

        search = request.GET.get("search")

        if search:
            queryset = queryset.filter(
                name__icontains=search,
            )

        data = []

        for branch in queryset:

            data.append({
                "id": branch.id,
                "school_id": branch.school_id,
                "school_name": branch.school.name,
                "name": branch.name,
                "code": branch.code,
                "email": branch.email,
                "phone_number": branch.phone_number,
                "city": branch.city,
                "state": branch.state,
                "status": branch.status,
            })

        return CustomResponse.successResponse(
            description="Branch list fetched successfully",
            data=data,
        )


# ===========================
# UPDATE BRANCH
# ===========================

class UpdateBranchAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "branch.update"

    def put(
        self,
        request,
        branch_id,
    ):

        branch = Branch.objects.filter(
            id=branch_id
        ).first()

        if not branch:
            return CustomResponse.errorResponse(
                description="Branch not found"
            )

        check_permission(
            request,
            "branch.update",
            branch.school_id,
        )

        branch.name = request.data.get(
            "name",
            branch.name,
        )

        branch.address = request.data.get(
            "address",
            branch.address,
        )

        branch.city = request.data.get(
            "city",
            branch.city,
        )

        branch.state = request.data.get(
            "state",
            branch.state,
        )

        branch.status = request.data.get(
            "status",
            branch.status,
        )

        branch.save()

        return CustomResponse.successResponse(
            description="Branch updated successfully"
        )






class UserListAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "user.view"

    def get(self, request):

        school = request.school
        user = request.user

        search = request.query_params.get(
            "search",
            "",
        ).strip()

        application_logger.info(
            "user_list_started",
            user_id=str(user.id),
            school_id=str(school.id) if school else None,
            search=search,
        )

        try:

            is_superadmin = has_role(
                user,
                RolesEnum.SUPERADMIN,
            )

            queryset = UserMaster.objects.filter(
                is_active=True,
            )

            if is_superadmin:

                queryset = queryset.prefetch_related(
                    Prefetch(
                        "user_roles",
                        queryset=UserRoles.objects.select_related(
                            "role",
                            "school",
                        ),
                    )
                )

            else:

                queryset = queryset.filter(
                    user_roles__school=school,
                ).distinct().prefetch_related(
                    Prefetch(
                        "user_roles",
                        queryset=UserRoles.objects.filter(
                            school=school,
                        ).select_related(
                            "role",
                            "school",
                        ),
                    )
                )

            if search:

                queryset = queryset.filter(
                    Q(first_name__icontains=search)
                    | Q(last_name__icontains=search)
                    | Q(username__icontains=search)
                    | Q(email__icontains=search)
                    | Q(mobile__icontains=search)
                )

            queryset = queryset.order_by(
                "first_name",
            )

            paginator = CustomPageNumberPagination()

            page = paginator.paginate_queryset(
                queryset,
                request,
            )

            data = []

            for obj in page:

                data.append({
                    "id": str(obj.id),
                    "first_name": obj.first_name,
                    "last_name": obj.last_name,
                    "mobile": obj.mobile,
                    "email": obj.email,
                    "roles": [
                        {
                            "id": str(user_role.role.id),
                            "name": user_role.role.role_name,
                            "school_id": (
                                str(user_role.school.id)
                                if user_role.school
                                else None
                            ),
                            "school_name": (
                                str(user_role.school.name)
                                if user_role.school
                                else None
                            )
                        }
                        for user_role in obj.user_roles.all()
                    ],
                })

            application_logger.info(
                "user_list_fetched",
                user_id=str(user.id),
                school_id=str(school.id) if school else None,
                total_count=len(data),
            )

            return paginator.get_paginated_response(
                data
            )

        except Exception as e:

            application_logger.exception(
                "user_list_failed",
                user_id=str(user.id),
                school_id=str(school.id) if school else None,
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description="Something went wrong while fetching users."
            )

class CreateSchoolConfigurationAPIView(APIView):

    permission_classes = [IsAuthenticated,HasPermission,]

    required_permission = "school.configuration.create"

    def post(self, request):

        # school = request.school
        school = request.data.get("school_id")
        if school is None:
            return CustomResponse.errorResponse(description="School not found.",)

        if SchoolConfiguration.objects.filter(
            school=school,
        ).exists():
            return CustomResponse.errorResponse(
                description="School configuration already exists.",
            )

        clients = request.data.get(
            "clients",
            [],

        )

        if not isinstance(
            clients,
            list,
        ):
            return CustomResponse.errorResponse(

                description="clients must be a list.",
            )

        client_types = []
        for client in clients:
            client_type = client.get(
                "client_type",
            )
            identifier = client.get(
                "identifier",
            )

            if not client_type:
                return CustomResponse.errorResponse(
                    description="client_type is required.",
                )

            if client_type not in SchoolClient.ClientType.values:
                return CustomResponse.errorResponse(
                    description=f"Invalid client_type '{client_type}'.",
                )

            if not identifier:
                return CustomResponse.errorResponse(
                    description=f"Identifier is required for {client_type}.",
                )

            if client_type in client_types:
                return CustomResponse.errorResponse(
                    description=f"Duplicate client_type '{client_type}'.",
                )

            client_types.append(client_type,)

        try:

            with transaction.atomic():

                configuration = SchoolConfiguration.objects.create(
                    school=school,
                    website_url=request.data.get(
                        "website_url",
                    ),
                    backoffice_url=request.data.get(
                        "backoffice_url",
                    ),
                    api_base_url=request.data.get(
                        "api_base_url",
                    ),
                    logo_url=request.data.get(
                        "logo_url",

                    ),

                    favicon_url=request.data.get(

                        "favicon_url",

                    ),

                    primary_color=request.data.get(

                        "primary_color",

                        "#2563EB",

                    ),

                    secondary_color=request.data.get(

                        "secondary_color",

                        "#FFFFFF",

                    ),

                    parent_android_version=request.data.get(

                        "parent_android_version",

                    ),

                    parent_android_force_update=request.data.get(

                        "parent_android_force_update",

                        False,

                    ),

                    parent_playstore_url=request.data.get(

                        "parent_playstore_url",

                    ),

                    parent_ios_version=request.data.get(

                        "parent_ios_version",

                    ),

                    parent_ios_force_update=request.data.get(

                        "parent_ios_force_update",

                        False,

                    ),

                    parent_appstore_url=request.data.get(

                        "parent_appstore_url",

                    ),

                    admin_android_version=request.data.get(

                        "admin_android_version",

                    ),

                    admin_android_force_update=request.data.get(

                        "admin_android_force_update",

                        False,

                    ),

                    admin_playstore_url=request.data.get(

                        "admin_playstore_url",

                    ),

                    admin_ios_version=request.data.get(

                        "admin_ios_version",

                    ),

                    admin_ios_force_update=request.data.get(

                        "admin_ios_force_update",

                        False,

                    ),

                    admin_appstore_url=request.data.get(

                        "admin_appstore_url",

                    ),

                    support_email=request.data.get(

                        "support_email",

                    ),

                    support_mobile=request.data.get(

                        "support_mobile",

                    ),

                )

                school_clients = []

                for client in clients:

                    school_clients.append(
                        SchoolClient(
                            school=school,
                            client_type=client.get(
                                "client_type",
                            ),
                            identifier=client.get(
                                "identifier",

                            ),

                        )

                    )

                if school_clients:
                    SchoolClient.objects.bulk_create(
                        school_clients,

                    )

        except Exception as e:
            return CustomResponse.errorResponse(
                description=str(e),
            )

        return CustomResponse.successResponse(

            description="School configuration created successfully.",

            data={
                "configuration_id": str(
                    configuration.id,
                ),
                "clients_created": len(
                    school_clients,
                ),

            },

        )

class GetSchoolConfigurationAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "school.configuration.view"

    def get(self, request):

        # school = request.school
        school = request.GET.get("school_id")

        if school is None:

            return CustomResponse.errorResponse(
                description="School not found.",
            )

        configuration = (
            SchoolConfiguration.objects.filter(
                school=school,
            )
            .first()
        )

        if configuration is None:

            return CustomResponse.errorResponse(
                description="School configuration not found.",
            )

        clients = SchoolClient.objects.filter(
            school=school,
            is_active=True,
        ).values(
            "id",
            "client_type",
            "identifier",
        )

        return CustomResponse.successResponse(

            description="School configuration fetched successfully.",

            data={

                "configuration": {

                    "id": str(configuration.id),

                    "website_url": configuration.website_url,

                    "backoffice_url": configuration.backoffice_url,

                    "api_base_url": configuration.api_base_url,

                    "logo_url": configuration.logo_url,

                    "favicon_url": configuration.favicon_url,

                    "primary_color": configuration.primary_color,

                    "secondary_color": configuration.secondary_color,

                    "parent_android_version": configuration.parent_android_version,

                    "parent_android_force_update": configuration.parent_android_force_update,

                    "parent_playstore_url": configuration.parent_playstore_url,

                    "parent_ios_version": configuration.parent_ios_version,

                    "parent_ios_force_update": configuration.parent_ios_force_update,

                    "parent_appstore_url": configuration.parent_appstore_url,

                    "admin_android_version": configuration.admin_android_version,

                    "admin_android_force_update": configuration.admin_android_force_update,

                    "admin_playstore_url": configuration.admin_playstore_url,

                    "admin_ios_version": configuration.admin_ios_version,

                    "admin_ios_force_update": configuration.admin_ios_force_update,

                    "admin_appstore_url": configuration.admin_appstore_url,

                    "support_email": configuration.support_email,

                    "support_mobile": configuration.support_mobile,

                },

                "clients": [

                    {
                        "id": str(client["id"]),
                        "client_type": client["client_type"],
                        "identifier": client["identifier"],
                    }

                    for client in clients

                ],

            },

        )

class UpdateSchoolConfigurationAPIView(APIView):

    permission_classes = [IsAuthenticated,HasPermission,]

    required_permission = "school.configuration.update"

    def put(self, request):

        # school = request.school
        school = request.GET.get("school_id")

        if school is None:

            return CustomResponse.errorResponse(description="School not found.",)

        configuration = SchoolConfiguration.objects.filter(school=school,).first()

        if configuration is None:

            return CustomResponse.errorResponse(description="School configuration not found.",)

        clients = request.data.get("clients",[],)

        if not isinstance(clients, list):

            return CustomResponse.errorResponse(description="clients must be a list.",)

        client_types = []

        for client in clients:

            client_type = client.get("client_type",)

            identifier = client.get("identifier",)

            if not client_type:

                return CustomResponse.errorResponse(description="client_type is required.", )

            if client_type not in SchoolClient.ClientType.values:

                return CustomResponse.errorResponse(

                    description=f"Invalid client_type '{client_type}'.",

                )

            if not identifier:

                return CustomResponse.errorResponse(

                    description=f"Identifier is required for '{client_type}'.",

                )

            if client_type in client_types:

                return CustomResponse.errorResponse(

                    description=f"Duplicate client_type '{client_type}'.",

                )

            client_types.append(

                client_type,

            )

        try:

            with transaction.atomic():

                restricted_fields = ["id","school","created_at","updated_at","deleted_at",]

                for field, value in request.data.items():

                    if field in restricted_fields:

                        continue

                    if field == "clients":

                        continue

                    if hasattr(

                        configuration,

                        field,

                    ):

                        setattr(

                            configuration,

                            field,

                            value,

                        )

                configuration.save()

                for client in clients:

                    SchoolClient.objects.update_or_create(school=school,

                        client_type=client.get(

                            "client_type",

                        ),

                        defaults={

                            "identifier": client.get(

                                "identifier",

                            ),

                            "is_active": True,

                        },

                    )

        except Exception as e:

            return CustomResponse.errorResponse(

                description=str(e),

            )

        return CustomResponse.successResponse(

            description="School configuration updated successfully.",

        )
class GetSchoolClientInfoAPIView(APIView):

    permission_classes = [AllowAny]

    authentication_classes = []

    def post(self, request):

        identifier = request.data.get(
            "identifier",
        )

        if not identifier:

            return CustomResponse.errorResponse(
                description="Identifier is required.",
            )

        client = (
            SchoolClient.objects.select_related(
                "school__configuration",
            )
            .filter(
                identifier=identifier.strip(),
                is_active=True,
            )
            .first()
        )

        if client is None:

            return CustomResponse.errorResponse(
                description="Invalid client identifier.",
            )

        configuration = getattr(
            client.school,
            "configuration",
            None,
        )

        if configuration is None:

            return CustomResponse.errorResponse(
                description="School configuration not found.",
            )

        return CustomResponse.successResponse(

            description="School configuration fetched successfully.",

            data={

                "school": {

                    "id": str(client.school.id),

                    "name": client.school.name,

                },

                "client_type": client.client_type,

                "configuration": {

                    "website_url": configuration.website_url,

                    "backoffice_url": configuration.backoffice_url,

                    "api_base_url": configuration.api_base_url,

                    "logo_url": configuration.logo_url,

                    "favicon_url": configuration.favicon_url,

                    "primary_color": configuration.primary_color,

                    "secondary_color": configuration.secondary_color,

                    "support_email": configuration.support_email,

                    "support_mobile": configuration.support_mobile,

                    "parent_app": {

                        "android_version": configuration.parent_android_version,

                        "android_force_update": configuration.parent_android_force_update,

                        "playstore_url": configuration.parent_playstore_url,

                        "ios_version": configuration.parent_ios_version,

                        "ios_force_update": configuration.parent_ios_force_update,

                        "appstore_url": configuration.parent_appstore_url,

                    },

                    "admin_app": {

                        "android_version": configuration.admin_android_version,

                        "android_force_update": configuration.admin_android_force_update,

                        "playstore_url": configuration.admin_playstore_url,

                        "ios_version": configuration.admin_ios_version,

                        "ios_force_update": configuration.admin_ios_force_update,

                        "appstore_url": configuration.admin_appstore_url,

                    },

                },

            },

        )