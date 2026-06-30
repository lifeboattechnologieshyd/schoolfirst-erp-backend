import json
import secrets
from django.conf import settings

import requests

from apps.school.models import School


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
    try:
        print(f"[OTP] Starting SMS send. Mobile: {mobile}, OTP: {otp}")

        base_url = "https://full2ads.com/smsapi/index"

        msg = (
            f"Use {otp} to complete your verification on the SchoolFirst App. "
            f"The code remains valid for 10 minutes. With care, SchoolFirst."
        )

        print(f"[OTP] Message: {msg}")

        tlv_payload = {
            "DLT_ENTITY_ID": getattr(settings, "FULL2ADS_DLT_ENTITY_ID", ""),
            "DLT_TEMPLATE_ID": getattr(settings, "FULL2ADS_DLT_TEMPLATE_ID", "")
        }

        print(f"[OTP] TLV Payload: {tlv_payload}")

        params = {
            "key": getattr(settings, "FULL2ADS_KEY"),
            "campaign": "0",
            "routeid": getattr(settings, "FULL2ADS_ROUTE_ID", "1"),
            "type": "text",
            "contacts": mobile,
            "senderid": getattr(settings, "FULL2ADS_SENDER_ID"),
            "tlv": json.dumps(tlv_payload),
            "msg": msg
        }

        safe_params = params.copy()
        safe_params["key"] = "****HIDDEN_API_KEY****"

        print(f"[OTP] Request Params: {safe_params}")

        from urllib.parse import urlencode

        final_url = base_url + "?" + urlencode(params, safe=":/,{}\"'")
        print(f"[OTP] Final URL: {final_url.replace(params['key'], '****HIDDEN_API_KEY****')}")

        print("[OTP] Sending request...")

        resp = requests.get(
            base_url,
            params=params,
            timeout=30
        )

        print(f"[OTP] Response Status Code: {resp.status_code}")
        print(f"[OTP] Response Headers: {dict(resp.headers)}")
        print(f"[OTP] Response Text: {resp.text}")

        text = resp.text or ""

        if resp.status_code == 200 and (
            "ok" in text.lower()
            or "success" in text.lower()
        ):
            print("[OTP] SMS sent successfully (success keyword found)")
            return True

        stripped = text.strip()

        if stripped.isdigit():
            print("[OTP] SMS sent successfully (numeric response)")
            return True

        if any(ch.isdigit() for ch in stripped):
            print("[OTP] SMS sent successfully (contains numeric message id)")
            return True

        print("[OTP] SMS sending failed")
        return False

    except Exception as e:
        print(f"[OTP] Exception occurred: {str(e)}")
        import traceback
        traceback.print_exc()
        return False