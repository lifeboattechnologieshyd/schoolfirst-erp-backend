from django.conf import settings
from phonepe.sdk.pg.common.models.request.meta_info import MetaInfo
from phonepe.sdk.pg.payments.v2.models.request.standard_checkout_pay_request import StandardCheckoutPayRequest
from phonepe.sdk.pg.payments.v2.standard_checkout_client import StandardCheckoutClient
from phonepe.sdk.pg.env import Env

from apps.fee.models import SchoolPaymentGateway


class PhonePeService:

    def __init__(self, gateway):

        self.gateway = gateway

    def create_payment(self, transaction):

        print("=" * 80)
        print("PHONEPE PAYMENT")
        print("Merchant :", self.gateway.merchant_id)
        print("Amount :", transaction.amount)
        print("=" * 80)

        return {

            "order_id": f"PHONEPE_{transaction.transaction_number}",

            "payment_url": "https://phonepe.com/pay",

        }

def get_phonepe_client():
    client = StandardCheckoutClient.get_instance(
        client_id=SchoolPaymentGateway.merchant_id,
        client_secret=SchoolPaymentGateway.secret_key,
        client_version=int(settings.PHONEPE_CLIENT_VERSION),
        env=Env.SANDBOX,  # change to PRODUCTION later
        should_publish_events=False
    )
    return client

def create_phonepe_payment(transaction, amount_paisa):

    client = get_phonepe_client()

    request = StandardCheckoutPayRequest.build_request(
        merchant_order_id=transaction.transaction_number,
        amount=amount_paisa,
        redirect_url="https://google.com",
        meta_info=MetaInfo(
            udf1=str(transaction.student.id),
        ),
        message="Student Fee Payment",
        expire_after=3600,
    )

    response = client.pay(request)

    return {
        "order_id": response.order_id,
        "redirect_url": response.redirect_url,
    }