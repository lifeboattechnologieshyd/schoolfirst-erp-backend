import json
import secrets
import traceback

from django.conf import settings

import requests

from apps.school.models import School
from shared.utils.logger import auth_logger


def generate_otp():

    return str(random.randint(1000, 9999))


import random
import string

def generate_school_code():
    while True:
        code = "SCH" + "".join(
            random.choices(string.ascii_uppercase + string.digits, k=6)
        )

        if not School.objects.filter(code=code).exists():
            return code



def send_otp_to_mobile(otp, mobile):
    """
    Send OTP using Full2Ads.

    If Full2Ads fails, automatically send using Lifeboat SMS.
    """

    # if _send_full2ads_sms(otp, mobile):
    #
    #     return True

    auth_logger.warning(
        "full2ads_sms_failed_fallback_to_lifeboat",
        mobile=mobile,
    )

    return _send_lifeboat_sms(
        otp,
        mobile,
    )


def _send_lifeboat_sms(otp, mobile):

    try:

        auth_logger.info(
            "lifeboat_sms_send_started",
            mobile=mobile,
        )

        url = "https://sms.lifeboattechnologies.com/dev/bulkV2"

        headers = {
            "authorization": settings.API_KEY,
            "Content-Type": "application/json",
        }

        payload = {
            "route": "dlt",
            "sender_id": settings.SENDER_ID,
            "message": settings.TEMPLATE_ID,
            "variables_values": otp,
            "numbers": mobile,
        }

        safe_headers = headers.copy()
        safe_headers["authorization"] = "****HIDDEN****"

        auth_logger.info(
            "lifeboat_sms_request",
            mobile=mobile,
            headers=safe_headers,
            payload=payload,
        )

        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=30,
        )

        auth_logger.info(
            "lifeboat_sms_response",
            mobile=mobile,
            status_code=response.status_code,
            response=response.text,
        )

        if response.status_code in (200, 201):

            auth_logger.info(
                "lifeboat_sms_sent_successfully",
                mobile=mobile,
            )

            return True

        auth_logger.warning(
            "lifeboat_sms_send_failed",
            mobile=mobile,
            status_code=response.status_code,
            response=response.text,
        )

        return False

    except Exception:

        auth_logger.exception(
            "lifeboat_sms_exception",
            mobile=mobile,
        )

        return False

# def _send_full2ads_sms(otp, mobile):
#
#     try:
#
#         print(f"[OTP][Full2Ads] Sending OTP to {mobile}")
#
#         base_url = "https://full2ads.com/smsapi/index"
#
#         msg = (
#
#             f"Use {otp} to complete your verification on the SchoolFirst App. "
#
#             f"The code remains valid for 10 minutes. With care, SchoolFirst."
#
#         )
#
#         tlv_payload = {
#
#             "DLT_ENTITY_ID": getattr(settings, "FULL2ADS_DLT_ENTITY_ID", ""),
#
#             "DLT_TEMPLATE_ID": getattr(settings, "FULL2ADS_DLT_TEMPLATE_ID", ""),
#
#         }
#
#         params = {
#
#             "key": settings.FULL2ADS_KEY,
#
#             "campaign": "0",
#
#             "routeid": getattr(settings, "FULL2ADS_ROUTE_ID", "1"),
#
#             "type": "text",
#
#             "contacts": mobile,
#
#             "senderid": settings.FULL2ADS_SENDER_ID,
#
#             "tlv": json.dumps(tlv_payload),
#
#             "msg": msg,
#
#         }
#
#         safe_params = params.copy()
#
#         safe_params["key"] = "****HIDDEN****"
#
#         print(f"[OTP][Full2Ads] Params: {safe_params}")
#
#         response = requests.get(
#
#             base_url,
#
#             params=params,
#
#             timeout=30,
#
#         )
#
#         print(f"[OTP][Full2Ads] Status: {response.status_code}")
#
#         print(f"[OTP][Full2Ads] Response: {response.text}")
#
#         text = (response.text or "").strip()
#
#         if response.status_code == 200:
#
#             if (
#
#                 "success" in text.lower()
#
#                 or "ok" in text.lower()
#
#                 or text.isdigit()
#
#                 or any(ch.isdigit() for ch in text)
#
#             ):
#
#                 print("[OTP][Full2Ads] SMS sent successfully.")
#
#                 return True
#
#         print("[OTP][Full2Ads] SMS failed.")
#
#         return False
#
#     except Exception as e:
#
#         print(f"[OTP][Full2Ads] Exception: {e}")
#
#         traceback.print_exc()
#
#         return False





# def send_otp_to_mobile(otp, mobile):
#     try:
#         print(f"[OTP] Starting SMS send. Mobile: {mobile}, OTP: {otp}")
#
#         base_url = "https://full2ads.com/smsapi/index"
#
#         msg = (
#             f"Use {otp} to complete your verification on the SchoolFirst App. "
#             f"The code remains valid for 10 minutes. With care, SchoolFirst."
#         )
#
#         print(f"[OTP] Message: {msg}")
#
#         tlv_payload = {
#             "DLT_ENTITY_ID": getattr(settings, "FULL2ADS_DLT_ENTITY_ID", ""),
#             "DLT_TEMPLATE_ID": getattr(settings, "FULL2ADS_DLT_TEMPLATE_ID", "")
#         }
#
#         print(f"[OTP] TLV Payload: {tlv_payload}")
#
#         params = {
#             "key": getattr(settings, "FULL2ADS_KEY"),
#             "campaign": "0",
#             "routeid": getattr(settings, "FULL2ADS_ROUTE_ID", "1"),
#             "type": "text",
#             "contacts": mobile,
#             "senderid": getattr(settings, "FULL2ADS_SENDER_ID"),
#             "tlv": json.dumps(tlv_payload),
#             "msg": msg
#         }
#
#         safe_params = params.copy()
#         safe_params["key"] = "****HIDDEN_API_KEY****"
#
#         print(f"[OTP] Request Params: {safe_params}")
#
#         from urllib.parse import urlencode
#
#         final_url = base_url + "?" + urlencode(params, safe=":/,{}\"'")
#         print(f"[OTP] Final URL: {final_url.replace(params['key'], '****HIDDEN_API_KEY****')}")
#
#         print("[OTP] Sending request...")
#
#         resp = requests.get(
#             base_url,
#             params=params,
#             timeout=30
#         )
#
#         print(f"[OTP] Response Status Code: {resp.status_code}")
#         print(f"[OTP] Response Headers: {dict(resp.headers)}")
#         print(f"[OTP] Response Text: {resp.text}")
#
#         text = resp.text or ""
#
#         if resp.status_code == 200 and (
#             "ok" in text.lower()
#             or "success" in text.lower()
#         ):
#             print("[OTP] SMS sent successfully (success keyword found)")
#             return True
#
#         stripped = text.strip()
#
#         if stripped.isdigit():
#             print("[OTP] SMS sent successfully (numeric response)")
#             return True
#
#         if any(ch.isdigit() for ch in stripped):
#             print("[OTP] SMS sent successfully (contains numeric message id)")
#             return True
#
#         print("[OTP] SMS sending failed")
#         return False
#
#     except Exception as e:
#         print(f"[OTP] Exception occurred: {str(e)}")
#         import traceback
#         traceback.print_exc()
#         return False

# POST https://sms.lifeboattechnologies.com/dev/bulkV2
#
# Request Header :
#
# {
# "authorization":"CfnZ********************"
# "Content-Type":"application/json"
# }
#
# Request Json Body :
#
# {
# "route" : "dlt",
# "sender_id" : "PAPREC",
# "message" : "12560",
# "variables_values" : "|",
# "numbers" : "",
# }