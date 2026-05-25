import structlog
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

logger = structlog.get_logger("default")


def _send_email(subject, template_name, context, to_email):
    """
    Internal helper to send an HTML email. Respects ENABLE_EMAIL flag.
    """
    if not getattr(settings, "ENABLE_EMAIL", False):
        logger.info("Email disabled, skipping", to=to_email, subject=subject)
        return

    html_body = render_to_string(template_name, context)
    send_mail(
        subject=subject,
        message="",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[to_email],
        html_message=html_body,
        fail_silently=True,
    )


def send_family_added_email(to_email, inviter_name, family_name):
    """
    Email 1 for family invites: "You've been added to the family by X."
    Sent regardless of whether the user has an account.
    """
    _send_email(
        subject=f"{inviter_name} added you to {family_name} on SamsR",
        template_name="emails/family_added.html",
        context={
            "inviter_name": inviter_name,
            "family_name": family_name,
        },
        to_email=to_email,
    )


def send_close_group_added_email(to_email, adder_name):
    """
    Email for close group: "X added you to their close group."
    """
    _send_email(
        subject=f"{adder_name} added you to their close group on SamsR",
        template_name="emails/close_group_added.html",
        context={
            "adder_name": adder_name,
        },
        to_email=to_email,
    )


def send_app_invite_email(to_email, inviter_name, invite_code):
    """
    Email 2 for non-existent users: App signup invitation with a targeted invite code.
    """
    _send_email(
        subject=f"{inviter_name} invited you to join SamsR",
        template_name="emails/app_invite.html",
        context={
            "inviter_name": inviter_name,
            "invite_code": invite_code,
        },
        to_email=to_email,
    )


def send_otp_email(to_email, otp):
    """
    OTP email for signup email verification.
    """
    _send_email(
        subject="Your SamsR verification code",
        template_name="emails/otp_verification.html",
        context={"otp": otp},
        to_email=to_email,
    )


def send_password_reset_email(to_email, otp):
    """
    OTP email for password reset.
    """
    _send_email(
        subject="Reset your SamsR password",
        template_name="emails/password_reset.html",
        context={"otp": otp},
        to_email=to_email,
    )
