

class RazorpayService:

    def __init__(self, gateway):

        self.gateway = gateway

    def create_payment(self, transaction):

        print("=" * 80)
        print("RAZORPAY PAYMENT")
        print("Merchant :", self.gateway.merchant_id)
        print("Amount :", transaction.amount)
        print("=" * 80)

        return {

            "order_id": f"RAZORPAY_{transaction.transaction_number}",

            "payment_url": "https://razorpay.com/pay",

        }