import random
import secrets
import traceback

from django.db.models import Q
from datetime import timedelta

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils import timezone

from rest_framework.permissions import AllowAny, IsAuthenticated

from rest_framework.response import Response

from rest_framework import status

from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models import UserOTP, UserMaster, UserRoles, UserDeviceSession, Roles
from django.db import transaction

from apps.school.models.school import Student
from shared.enums.roles import RolesEnum
from shared.helpers import get_user_roles, get_user_permissions
from shared.mixins import CustomResponse

from rest_framework.parsers import FormParser, MultiPartParser
from django.conf import settings

from shared.utils.logger import auth_logger, application_logger
from shared.utils.otp import send_otp_to_mobile, generate_otp
from shared.utils.s3 import add_unique_suffix_to_filename, sanitize_filename

def normalize_email(value):

    if value is None:

        return None

    value = str(value).strip().lower()

    return value or None

def normalize_mobile(value):

    if value is None:

        return None

    value = str(value).strip()

    return value or None



class ADMINSendOTPAPIView(APIView):

    permission_classes = [AllowAny]

    def post(self, request):

        mobile = normalize_mobile(request.data.get("mobile"))

        auth_logger.info(
            "admin_send_otp_started",
            mobile=mobile,
        )

        if not mobile:

            auth_logger.warning(
                "admin_send_otp_failed",
                reason="mobile_required",
            )

            return CustomResponse.errorResponse(
                description="Mobile is required.",
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = UserMaster.objects.filter(
            mobile=mobile,
            is_active=True,
        ).first()

        if user is None:

            auth_logger.warning(
                "admin_send_otp_failed",
                reason="user_not_found",
                mobile=mobile,
            )

            return CustomResponse.errorResponse(
                description="User not found.",
                status=status.HTTP_404_NOT_FOUND,
            )

        roles = get_user_roles(user=user)

        allowed_roles = [
            RolesEnum.SUPERADMIN,
            RolesEnum.ADMIN,
            RolesEnum.SCHOOL_ADMIN,
            RolesEnum.TEACHER,
            RolesEnum.DRIVER,
            RolesEnum.PRINCIPAL,
        ]

        if not any(role in allowed_roles for role in roles):

            auth_logger.warning(
                "admin_send_otp_failed",
                reason="unauthorized_role",
                user_id=str(user.id),
                roles=roles,
            )

            return CustomResponse.errorResponse(
                description="You are not authorized to login.",
                status=status.HTTP_403_FORBIDDEN,
            )

        try:

            otp = generate_otp()

            send_otp_to_mobile(
                otp,
                mobile,
            )

            otp_obj = UserOTP.objects.create(
                user=user,
                mobile=int(mobile),
                otp=otp,
                expires_at=timezone.now() + timedelta(minutes=10),
                is_used=False,
            )

        except Exception as e:

            auth_logger.exception(
                "admin_send_otp_failed",
                reason="otp_generation_or_delivery_failed",
                user_id=str(user.id),
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description="Failed to send OTP.",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        auth_logger.info(
            "admin_send_otp_success",
            user_id=str(user.id),
            otp_id=str(otp_obj.id),
            roles=roles,
        )

        return CustomResponse.successResponse(
            data={
                # "mobile_otp": otp,
            },
            description="OTP sent successfully.",
        )



class ADMINVerifyOTPAPIView(APIView):

    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):

        mobile = normalize_mobile(request.data.get("mobile"))
        otp = str(request.data.get("otp", "")).strip()

        auth_logger.info(
            "admin_otp_verification_started",
            mobile=mobile,
        )

        if not mobile or not otp:

            auth_logger.warning(
                "admin_otp_verification_failed",
                reason="mobile_or_otp_missing",
                mobile=mobile,
            )

            return CustomResponse.errorResponse(
                description="Mobile and OTP are required.",
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = UserMaster.objects.filter(
            mobile=mobile,
            is_active=True,
        ).first()

        if user is None:

            auth_logger.warning(
                "admin_otp_verification_failed",
                reason="user_not_found",
                mobile=mobile,
            )

            return CustomResponse.errorResponse(
                description="User not found.",
                status=status.HTTP_404_NOT_FOUND,
            )

        roles = get_user_roles(
            user=user,
        )

        otp_obj = UserOTP.objects.filter(
            mobile=int(mobile),
            otp=otp,
            is_used=False,
            expires_at__gt=timezone.now(),
        ).order_by(
            "-created_at",
        ).first()

        if otp_obj is None:

            auth_logger.warning(
                "admin_otp_verification_failed",
                reason="invalid_or_expired_otp",
                user_id=str(user.id),
                mobile=mobile,
            )

            return CustomResponse.errorResponse(
                description="Invalid or expired OTP.",
                status=status.HTTP_400_BAD_REQUEST,
            )

        otp_obj.is_used = True
        otp_obj.save(
            update_fields=["is_used"],
        )

        auth_logger.info(
            "admin_otp_verified",
            user_id=str(user.id),
            mobile=mobile,
            otp_id=str(otp_obj.id),
        )

        refresh = RefreshToken.for_user(
            user,
        )

        permissions = get_user_permissions(
            user=user,
        )

        assigned_schools = UserRoles.objects.filter(
            user=user,
            school__isnull=False,
        ).select_related(
            "school",
        ).values(
            "school__id",
            "school__name",
        ).distinct()

        schools = [
            {
                "id": str(school["school__id"]),
                "name": school["school__name"],
            }
            for school in assigned_schools
        ]

        auth_logger.info(
            "admin_login_successful",
            user_id=str(user.id),
            mobile=mobile,
            roles=roles,
            permission_count=len(permissions),
            school_count=len(schools),
        )

        return CustomResponse.successResponse(
            data={
                "user": {
                    "id": str(user.id),
                    "username": user.username,
                    "mobile": user.mobile,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                },
                "roles": roles,
                "permissions": permissions,
                "schools": schools,
                "tokens": {
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                },
            },
            description="Login successful.",
        )


class LogoutAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):

        user = request.user

        auth_logger.info(
            "logout_started",
            user_id=str(user.id),
            username=user.username,
        )

        try:

            user.status = UserMaster.Status.INACTIVE
            user.save(update_fields=["status"])

        except Exception as e:

            auth_logger.exception(
                "logout_failed",
                user_id=str(user.id),
                username=user.username,
                error=str(e),
            )

            return Response(
                {
                    "message": "Logout failed."
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        auth_logger.info(
            "logout_successful",
            user_id=str(user.id),
            username=user.username,
        )

        return Response(
            {
                "message": "Logged out successfully"
            },
            status=status.HTTP_200_OK,
        )

class FileUploadView(APIView):

    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):

        files = request.FILES.getlist("files")
        path = request.data.get("path", "temp")

        application_logger.info(
            "file_upload_started",
            user_id=str(request.user.id) if request.user.is_authenticated else None,
            upload_path=path,
            file_count=len(files),
        )

        if not files:

            application_logger.warning(
                "file_upload_failed",
                reason="no_files_provided",
                upload_path=path,
                user_id=str(request.user.id) if request.user.is_authenticated else None,
            )

            return CustomResponse().successResponse(
                {"error": "No file was provided."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        uploaded_files = []

        try:

            for file_obj in files:

                application_logger.info(
                    "file_upload_processing",
                    original_filename=file_obj.name,
                    file_size=file_obj.size,
                    content_type=file_obj.content_type,
                    upload_path=path,
                )

                sanitized_filename = add_unique_suffix_to_filename(
                    sanitize_filename(file_obj.name)
                )

                file_path = default_storage.save(
                    f"{path}/{sanitized_filename}",
                    ContentFile(file_obj.read()),
                )

                file_url = settings.MEDIA_URL + file_path

                uploaded_files.append({
                    "original_filename": file_obj.name,
                    "file_url": file_url,
                    "file_path": file_path,
                })

                application_logger.info(
                    "file_uploaded",
                    original_filename=file_obj.name,
                    stored_filename=sanitized_filename,
                    file_path=file_path,
                    file_size=file_obj.size,
                    content_type=file_obj.content_type,
                )

            application_logger.info(
                "file_upload_completed",
                user_id=str(request.user.id) if request.user.is_authenticated else None,
                upload_path=path,
                uploaded_count=len(uploaded_files),
            )

            return CustomResponse().successResponse(
                uploaded_files,
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:

            application_logger.exception(
                "file_upload_failed",
                upload_path=path,
                uploaded_count=len(uploaded_files),
                total_file_count=len(files),
                user_id=str(request.user.id) if request.user.is_authenticated else None,
                error=str(e),
            )

            return CustomResponse().errorResponse(
                {"error": str(e)},
                description="File upload failed",
                status=status.HTTP_400_BAD_REQUEST,
            )


class SendOTPAPIView(APIView):

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):

        mobile = request.data.get("mobile")

        auth_logger.info(
            "otp_send_requested",
            mobile=mobile,
        )

        try:

            if not mobile:

                auth_logger.warning(
                    "otp_send_failed",
                    reason="mobile_required",
                )

                return CustomResponse.errorResponse(
                    description="Mobile number is required."
                )

            mobile = str(mobile).strip()

            if not mobile.isdigit() or len(mobile) != 10:

                auth_logger.warning(
                    "otp_send_failed",
                    mobile=mobile,
                    reason="invalid_mobile",
                )

                return CustomResponse.errorResponse(
                    description="Enter valid mobile number."
                )

            invalidated_count = UserOTP.objects.filter(
                mobile=mobile,
                is_used=False,
            ).update(
                is_used=True,
            )

            auth_logger.info(
                "previous_otps_invalidated",
                mobile=mobile,
                invalidated_count=invalidated_count,
            )

            otp = generate_otp()

            user = UserMaster.objects.filter(
                mobile=mobile,
            ).first()

            otp_obj = UserOTP.objects.create(
                user=user,
                mobile=mobile,
                otp=otp,
                expires_at=timezone.now() + timedelta(minutes=10),
                is_used=False,
            )

            auth_logger.info(
                "otp_created",
                otp_id=str(otp_obj.id),
                mobile=mobile,
                user_id=str(user.id) if user else None,
                user_exists=user is not None,
                expires_in_minutes=10,
            )

            sms_status = send_otp_to_mobile(
                otp=otp,
                mobile=mobile,
            )

            if not sms_status:

                auth_logger.error(
                    "otp_sms_send_failed",
                    otp_id=str(otp_obj.id),
                    mobile=mobile,
                    provider="full2ads",
                )

                return CustomResponse.errorResponse(
                    description="Unable to send OTP."
                )

            auth_logger.info(
                "otp_sent_successfully",
                otp_id=str(otp_obj.id),
                mobile=mobile,
                provider="full2ads",
            )

            return CustomResponse.successResponse(
                description="OTP sent successfully."
            )

        except Exception:

            auth_logger.exception(
                "send_otp_api_failed",
                mobile=mobile,
            )

            return CustomResponse.errorResponse(
                description="Something went wrong while sending OTP."
            )

class VerifyOTPAPIView(APIView):

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):

        mobile = request.data.get("mobile")
        otp = request.data.get("otp")
        device_id = request.data.get("device_id")
        session_id = request.data.get("session_id")
        device_type = request.data.get("device_type")
        fcm_token = request.data.get("fcm_token")

        auth_logger.info(
            "otp_verification_requested",
            mobile=mobile,
            device_id=device_id,
            device_type=device_type,
        )

        try:

            if not mobile or not otp:

                auth_logger.warning(
                    "otp_verification_failed",
                    mobile=mobile,
                    reason="mobile_or_otp_required",
                )

                return CustomResponse.errorResponse(
                    description="Mobile and OTP are required."
                )

            mobile = str(mobile).strip()
            otp = str(otp).strip()

            if not mobile.isdigit() or len(mobile) != 10:

                auth_logger.warning(
                    "otp_verification_failed",
                    mobile=mobile,
                    reason="invalid_mobile",
                )

                return CustomResponse.errorResponse(
                    description="Enter valid mobile number."
                )

            otp_obj = UserOTP.objects.filter(
                mobile=mobile,
                otp=otp,
                is_used=False,
            ).order_by(
                "-created_at",
            ).first()

            if otp_obj is None:

                auth_logger.warning(
                    "otp_verification_failed",
                    mobile=mobile,
                    reason="invalid_otp",
                )

                return CustomResponse.errorResponse(
                    description="Invalid OTP."
                )

            if otp_obj.expires_at < timezone.now():

                auth_logger.warning(
                    "otp_verification_failed",
                    otp_id=str(otp_obj.id),
                    mobile=mobile,
                    reason="otp_expired",
                )

                return CustomResponse.errorResponse(
                    description="OTP expired."
                )

            with transaction.atomic():

                otp_obj.is_used = True

                otp_obj.save(
                    update_fields=["is_used"]
                )

                auth_logger.info(
                    "otp_verified",
                    otp_id=str(otp_obj.id),
                    mobile=mobile,
                )

                user, user_created = UserMaster.objects.get_or_create(
                    mobile=mobile,
                    defaults={
                        "username": mobile,
                        "status": UserMaster.Status.ACTIVE,
                    },
                )

                if user_created:
                    auth_logger.info(
                        "parent_user_created",
                        user_id=str(user.id),
                        mobile=mobile,
                    )
                else:
                    auth_logger.info(
                        "parent_user_found",
                        user_id=str(user.id),
                        mobile=mobile,
                    )

                students = Student.objects.select_related(
                    "grade",
                    "section",
                    "academic_year",
                    "school",
                ).filter(
                    Q(father_mobile=mobile)
                    | Q(mother_mobile=mobile)
                    | Q(guardian_mobile=mobile)
                )
                student_count = students.count()

                student_data = []
                if student_count > 0:

                    auth_logger.info(
                        "parent_students_fetched",
                        user_id=str(user.id),
                        mobile=mobile,
                        student_count=student_count,
                    )

                    role = Roles.objects.filter(
                        role_name=RolesEnum.PARENT,
                    ).first()

                    if role is None:
                        auth_logger.error("parent_role_not_found")
                        raise ValueError("Parent role not configured.")

                    UserRoles.objects.get_or_create(
                        user=user,
                        role=role,
                        school=None,
                    )

                    for student in students:


                        if student.father_mobile == mobile:
                            relationship = "Father"
                        elif student.mother_mobile == mobile:
                            relationship = "Mother"
                        else:
                            relationship = "Guardian"

                        student_data.append({
                            "student_id": str(student.id),
                            "admission_number": student.admission_number,
                            "roll_number": student.roll_number,
                            "name": student.name,
                            "photo_url": student.photo_url,
                            "gender": student.gender,
                            "date_of_birth": student.date_of_birth,
                            "school": {
                                "id": str(student.school.id),
                                "name": student.school.name,
                            },
                            "grade": {
                                "id": str(student.grade.id),
                                "name": student.grade.name,
                            } if student.grade else None,
                            "section": {
                                "id": str(student.section.id),
                                "name": student.section.name,
                            } if student.section else None,
                            "academic_year": (
                                student.academic_year.name
                                if student.academic_year
                                else None
                            ),
                            "relationship": relationship,
                            "father_name": student.father_name,
                            "mother_name": student.mother_name,
                            "father_mobile": student.father_mobile,
                            "mother_mobile": student.mother_mobile,
                            "guardian_name": student.guardian_name,
                            "guardian_mobile": student.guardian_mobile,
                            "status": student.status,
                        })





                refresh = RefreshToken.for_user(user)

                access_token = str(refresh.access_token)
                refresh_token = str(refresh)

                client_ip = self.get_client_ip(request)

                device_session, session_created = UserDeviceSession.objects.update_or_create(
                    user=user,
                    device_id=device_id,
                    defaults={
                        "session_id": session_id,
                        "device_type": device_type,
                        "fcm_token": fcm_token,
                        "ip_address": client_ip,
                        "user_agent": request.META.get("HTTP_USER_AGENT"),
                        "is_active": True,
                    },
                )

                auth_logger.info(
                    "parent_device_session_saved",
                    user_id=str(user.id),
                    device_session_id=str(device_session.id),
                    device_id=device_id,
                    device_type=device_type,
                    session_created=session_created,
                )



            auth_logger.info(
                "parent_login_successful",
                user_id=str(user.id),
                mobile=mobile,
                user_created=user_created,
                student_count=student_count,
                device_id=device_id,
                device_type=device_type,
            )

            return CustomResponse.successResponse(
                description="Login successful.",
                data={
                    "access": access_token,
                    "refresh": refresh_token,
                    "user_id": str(user.id),
                    "students": student_data,
                },
            )

        except Exception:

            auth_logger.exception(
                "otp_verification_api_failed",
                mobile=mobile,
                device_id=device_id,
                device_type=device_type,
            )

            return CustomResponse.errorResponse(
                description="Something went wrong while verifying OTP."
            )

    def get_client_ip(self, request):

        x_forwarded_for = request.META.get(
            "HTTP_X_FORWARDED_FOR"
        )

        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()

        return request.META.get(
            "REMOTE_ADDR"
        )


