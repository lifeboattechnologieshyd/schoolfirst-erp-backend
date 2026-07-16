from apps.fee.models import SchoolPaymentGateway
from apps.payment.services.phonepe import PhonePeService
from apps.payment.services.razorpay import RazorpayService


class PaymentGatewayService:

    def __init__(self, gateway):

        self.gateway = gateway

    def create_payment(self, transaction):

        print("=" * 80)
        print("PAYMENT GATEWAY")
        print("Gateway :", self.gateway.gateway)
        print("=" * 80)

        if self.gateway.gateway == SchoolPaymentGateway.Gateway.PHONEPE:

            return PhonePeService(
                self.gateway,
            ).create_payment(
                transaction,
            )

        if self.gateway.gateway == SchoolPaymentGateway.Gateway.RAZORPAY:

            return RazorpayService(
                self.gateway,
            ).create_payment(
                transaction,
            )

        raise Exception(
            f"Unsupported payment gateway: {self.gateway.gateway}"
        )