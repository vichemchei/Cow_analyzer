from __future__ import print_function
import africastalking
import os
from dotenv import load_dotenv

load_dotenv()

class SMS:
    def __init__(self):
        self.username = os.getenv("AFRICAS_TALKING_USERNAME", "sandbox")
        self.api_key = os.getenv("AFRICAS_TALKING_API_KEY")
        
        if not self.api_key:
            raise ValueError("AFRICAS_TALKING_API_KEY environment variable is required. Please set it in .env file.")

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
