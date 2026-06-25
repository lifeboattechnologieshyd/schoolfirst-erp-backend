from apps.payment.services.phonepe import PhonePeService
from apps.payment.services.razorpay import RazorpayService


class PaymentGatewayService:

    def __init__(self, gateway):
        self.gateway = gateway

    def create_payment(self, transaction):

        print("=" * 80)
        print("Inside PaymentGatewayService")
        print("Gateway:", self.gateway.gateway)
        print("=" * 80)

        if self.gateway.gateway == "PHONEPE":

            print("Using PhonePe")

            return PhonePeService(
                self.gateway,
            ).create_payment(transaction)

        elif self.gateway.gateway == "RAZORPAY":

            print("Using Razorpay")

            return RazorpayService(
                self.gateway,
            ).create_payment(transaction)

        raise Exception(
            f"Unsupported gateway: {self.gateway.gateway}"
        )