


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