from datetime import timedelta

from django.db.models import Q
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.backoffice.views.leads import normalize_email, normalize_mobile
from apps.core.models import UserRoles, Roles, Permissions, RolePermissions, UserOTP, UserMaster
from apps.school.models import SchoolLead
from apps.school.models.school import Organization, School, Branch
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


class CreateSuperAdminAPIView(APIView):

    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):

        print("=" * 50)
        print("CreateSuperAdminAPIView Started")
        print("Request User ID:", request.user.id)
        print("Request Username:", request.user.username)
        print("Request Mobile:", request.user.mobile)

        role, created = Roles.objects.get_or_create(
            role_name="SUPERADMIN",
            defaults={
                "description": "Platform Super Admin",
            },
        )

        print("Role ID:", role.id)
        print("Role Name:", role.role_name)
        print("Role Created:", created)

        all_permissions = Permissions.objects.all()

        print("Total Permissions Found:", all_permissions.count())

        assigned_permissions = 0

        for permission in all_permissions:
            _, permission_created = RolePermissions.objects.get_or_create(
                role=role,
                permission=permission,
            )

            if permission_created:
                assigned_permissions += 1

            print(
                f"Permission: {permission.permission_name} | Created: {permission_created}"
            )

        print("Total Permissions Assigned:", assigned_permissions)

        user_role, user_role_created = UserRoles.objects.get_or_create(
            user=request.user,
            role=role,
            school=None,
        )

        print("UserRole Created:", user_role_created)
        print("UserRole ID:", user_role.id)
        print("UserRole User:", user_role.user.username)
        print("UserRole Role:", user_role.role.role_name)
        print("UserRole School:", user_role.school)

        print(
            "Verify SUPERADMIN Exists:",
            UserRoles.objects.filter(
                user=request.user,
                role__role_name="SUPERADMIN",
            ).exists()
        )

        print("=" * 50)

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



class SuperAdminRequestOTPAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        phone_number = normalize_mobile(
            request.data.get("phone_number")
        )

        if not phone_number:
            return CustomResponse.errorResponse(
                description="mobile is required.",
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = UserMaster.objects.filter(
            mobile=phone_number,
            is_active=True,
        ).first()

        print("USER ID:", user.id)
        print("MOBILE:", user.mobile)

        print(
            UserRoles.objects.filter(user=user).values(
                "role__role_name",
                "school_id"
            )
        )

        if not user:
            return CustomResponse.errorResponse(
                description="User not found.",
                status=status.HTTP_404_NOT_FOUND,
            )

        is_superadmin = UserRoles.objects.filter(
            user=user,
            role__role_name="SUPERADMIN",
        ).exists()

        if not is_superadmin:
            return CustomResponse.errorResponse(
                description="Only SUPERADMIN can login here.",
                status=status.HTTP_403_FORBIDDEN,
            )
        otp = 1234

        # otp = generate_otp()

        UserOTP.objects.create(
            mobile=int(phone_number),
            otp=otp,
            expires_at=timezone.now() + timedelta(minutes=15),
            is_used=False,
        )

        # send sms here

        return CustomResponse.successResponse(
            data={
                "mobile_otp": otp ,
            },
            description="OTP sent successfully.",
            status=status.HTTP_200_OK,
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

        if not phone_number or not otp:
            return CustomResponse.errorResponse(
                description="mobile and otp are required.",
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = UserMaster.objects.filter(
            mobile=phone_number,
            is_active=True,
        ).first()

        if not user:
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
            return CustomResponse.errorResponse(
                description="Invalid or expired OTP.",
                status=status.HTTP_400_BAD_REQUEST,
            )

        otp_obj.is_used = True
        otp_obj.save(update_fields=["is_used"])

        user_role = UserRoles.objects.filter(
            user=user,
            role__role_name="SUPERADMIN",
        ).exists()

        if not user_role:
            return CustomResponse.errorResponse(
                description="SUPERADMIN role not assigned.",
                status=status.HTTP_403_FORBIDDEN,
            )

        refresh = RefreshToken.for_user(user)

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

class SchoolLeadListAPIView(APIView):
    permission_classes = [IsAuthenticated]


    def get(self, request):
        user = request.user
        is_superadmin = UserRoles.objects.filter(
            user=user,
            role__role_name="SUPERADMIN",
        ).exists()

        if not is_superadmin:
            return CustomResponse.errorResponse(
                description="Only SUPERADMIN can login here.",
                status=status.HTTP_403_FORBIDDEN,
            )


        leads = SchoolLead.objects.all()

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

        school_id = request.GET.get(
            "school_id"
        )

        check_permission(
            request,
            "school.view",
            school_id,
        )

        queryset = School.objects.select_related("organization",).all()

        data = []

        for obj in queryset:

            data.append({
                "id": obj.id,
                "name": obj.name,
                "code": obj.code,
                "organization_name": obj.organization.name if obj.organization else None,
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

            })

        return CustomResponse.successResponse(
            data=data
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

        search = request.query_params.get(
            "search",
            "",
        ).strip()

        if has_role(
            request.user,
            RolesEnum.SUPERADMIN,
        ):

            queryset = UserMaster.objects.filter(
                is_active=True,
            )

        else:

            queryset = UserMaster.objects.filter(
                user_roles__school=school,
                is_active=True,
            ).distinct()

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

        data = [
            {
                "id": str(user.id),
                "first_name": user.first_name,
                "last_name": user.last_name,
                "mobile":user.mobile,
                "email":user.email,

            }
            for user in page
        ]

        return paginator.get_paginated_response(data)