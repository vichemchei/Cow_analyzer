from __future__ import print_function
import africastalking


class SMS:
    def __init__(self):
        self.username = "sandbox"
        self.api_key = "atsk_c476b74ddda6a1e9566cb6ebaf83cdb47396a4e7c0af1c5d88de9e1c0144807ee1b5e4d6"

        africastalking.initialize(self.username, self.api_key)

        self.sms = africastalking.SMS
        self.sender = "1403"  # Optional sender ID

    def send(self, recipients, message):
        try:
            response = self.sms.send(message, recipients, self.sender)
            print("Response:", response)
            return response
        except Exception as e:
            print("Error occurred when sending message:", str(e))
            return None


def main():
    sms = SMS()
    sms.send(["+254743134869"], "Hello from Africa's Talking Python SDK!")


if __name__ == "__main__":
    main()
