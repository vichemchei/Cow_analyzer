from __future__ import print_function
import africastalking
import os
from dotenv import load_dotenv

load_dotenv()

class SMS:
    """SMS sender with lazy initialization for API credentials"""
    
    def __init__(self):
        self.username = os.getenv("AFRICAS_TALKING_USERNAME", "sandbox")
        self.api_key = os.getenv("AFRICAS_TALKING_API_KEY")
        self.sms = None
        self.sender = "1403"  # Optional sender ID
        self._initialized = False

    def _initialize(self):
        """Lazy initialization of Africa's Talking API"""
        if self._initialized:
            return True
        
        if not self.api_key:
            return False
        
        try:
            africastalking.initialize(self.username, self.api_key)
            self.sms = africastalking.SMS
            self._initialized = True
            return True
        except Exception as e:
            print(f"Error initializing Africa's Talking: {e}")
            return False

    def send(self, recipients, message):
        """Send SMS message. Returns dict with status"""
        if not self._initialize():
            return {
                "success": False,
                "error": "SMS not configured - missing AFRICAS_TALKING_API_KEY",
                "status": "unconfigured"
            }
        
        try:
            response = self.sms.send(message, recipients, self.sender)
            return {
                "success": True,
                "response": response,
                "status": "sent"
            }
        except Exception as e:
            print(f"Error sending SMS: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to send SMS: {str(e)[:100]}",
                "status": "error"
            }


def main():
    sms = SMS()
    result = sms.send(["+254743134869"], "Hello from Africa's Talking Python SDK!")
    print("Response:", result)


if __name__ == "__main__":
    main()
