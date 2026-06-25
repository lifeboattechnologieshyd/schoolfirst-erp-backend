from apps.payment.services.phonepe import PhonePeService
from apps.payment.services.razorpay import RazorpayService


class PaymentGatewayService:

    def __init__(self, gateway):

        self.gateway = gateway

    def create_payment(self, transaction):

        if self.gateway.gateway == "PHONEPE":

            return PhonePeService(

                self.gateway,

            ).create_payment(transaction)

        elif self.gateway.gateway == "RAZORPAY":

            return RazorpayService(

                self.gateway,

            ).create_payment(transaction)

        raise Exception(

            f"{self.gateway.gateway} gateway is not supported."

        )