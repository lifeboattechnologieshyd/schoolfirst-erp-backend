from django.conf import settings
from phonepe.sdk.pg.common.models.request.meta_info import MetaInfo
from phonepe.sdk.pg.payments.v2.models.request.create_sdk_order_request import CreateSdkOrderRequest
from phonepe.sdk.pg.payments.v2.models.request.standard_checkout_pay_request import StandardCheckoutPayRequest
from phonepe.sdk.pg.payments.v2.standard_checkout_client import StandardCheckoutClient
from phonepe.sdk.pg.env import Env

from apps.fee.models import SchoolPaymentGateway
from apps.payment.services import gateway


class PhonePeService:

    def __init__(self, gateway):

        self.gateway = gateway

    def create_payment(self, transaction):

        print("=" * 80)
        print("PHONEPE PAYMENT")
        print("Merchant :", self.gateway.merchant_id)
        print("Transaction :", transaction.transaction_number)
        print("Amount :", transaction.amount)
        print("=" * 80)

        return create_phonepe_payment(
            transaction,
        )



def create_phonepe_payment(transaction):

    gateway = transaction.gateway

    amount_paisa = int(transaction.amount * 100)

    client = get_phonepe_client(gateway)

    request = StandardCheckoutPayRequest.build_request(
        merchant_order_id=transaction.transaction_number,
        amount=amount_paisa,
        redirect_url=settings.PHONEPE_REDIRECT_URL,
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

def get_phonepe_client(gateway):

    return StandardCheckoutClient.get_instance(
        client_id=gateway.merchant_id,
        client_secret=gateway.secret_key,
        client_version=int(settings.PHONEPE_CLIENT_VERSION),
        env=Env.SANDBOX,
        should_publish_events=False,
    )


def phone_pe_initate(order_id, gateway):

    client = get_phonepe_client(gateway)

    unique_order_id = str(order_id)

    amount = 100

    meta_info = MetaInfo(
        udf1="onboarding",
    )

    sdk_order_request = CreateSdkOrderRequest.build_standard_checkout_request(
        merchant_order_id=unique_order_id,
        amount=amount,
        meta_info=meta_info,
        disable_payment_retry=True,
    )

    create_order_response = client.create_sdk_order(
        sdk_order_request=sdk_order_request,
    )

    return create_order_response