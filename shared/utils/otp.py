import secrets
from django.conf import settings

import requests

from apps.school.models import School


# def generate_otp(digits=4):
#     if digits < 1:
#         raise ValueError("Digits must be at least 1")
#     otp = secrets.randbelow(10**digits - 10 ** (digits - 1)) + 10 ** (digits - 1)
#     return otp


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


        base_url = "https://full2ads.com/smsapi/index"

        msg = (
            f"Use {otp} to complete your verification on the SchoolFirst App. "
            f"The code remains valid for 10 minutes. With care, SchoolFirst."
        )

        tlv_payload = {
            "DLT_ENTITY_ID": getattr(settings, "FULL2ADS_DLT_ENTITY_ID", ""),
            "DLT_TEMPLATE_ID": getattr(settings, "FULL2ADS_DLT_TEMPLATE_ID", "")
        }

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


        from urllib.parse import urlencode

        final_url = base_url + "?" + urlencode(params, safe=":/,{}\"'")


        resp = requests.get(
            base_url,
            params=params,
            timeout=30
        )



        text = resp.text or ""

        if resp.status_code == 200 and (
            "ok" in text.lower()
            or "success" in text.lower()
        ):
            return True

        stripped = text.strip()

        if stripped.isdigit():
            return True

        if any(ch.isdigit() for ch in stripped):
            return True



        return False

    except Exception as e:



        return False