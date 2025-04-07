import sys
import pyotp
import time
import pytz
from SmartApi import SmartConnect
from datetime import datetime, timedelta
from twilio.rest import Client
import os

# 🔹 Credentials & Configurations
API_KEY = 'I39xpH90'
PASSWORD = '1611'
CLIENT_CODE = 'AAAI570791'
TOTP_SECRET = 'ZXI5JF7SKHJND6W2XCBHYPLEJU'
LOT_SIZE = 75  # Quantity per lot
account_sid = 'AC6ef902b81d63731c13b746613aadb2aa'
auth_token = '06c408e1a82a20ae2b839f2cceac4705'  # Replace with actual token
current_date = datetime.now().strftime("%Y-%m-%d")
smart_api = SmartConnect(api_key=API_KEY)
#For twilio
client = Client(account_sid, auth_token)

def send_whatsapp_message(message_body):
    """
    Sends a WhatsApp message using Twilio API.
    :param message_body: The message content to send.
    """
    recipients = [
        'whatsapp:+919042528367',  # Recipient 1
        'whatsapp:+918012991200'   # Recipient 2 (add as many as needed)
    ]
    try:
        message = client.messages.create(
            from_='whatsapp:+14155238886',  # Twilio sandbox number
            #to='whatsapp:+919042528367',
            to=recipients,  
            body=message_body
        )
        print(f"WhatsApp Message Sent: {message_body}")
    except Exception as e:
        print(f"Failed to send message: {e}")

def login():
    """Logs in and generates authentication tokens."""
    global smart_api
    totp = pyotp.TOTP(TOTP_SECRET).now()
    session = smart_api.generateSession(CLIENT_CODE, PASSWORD, totp)
    if session.get("status") is True:
        print("✅ Login successful!")
    else:
        send_whatsapp_message("❌ Login failed:")
        raise Exception(f"❌ Login failed: {session.get('message', 'Unknown error')}")

def logout():
    """Logs in and generates authentication tokens."""
    try:
        # Check if access_token is set (indicates logged in)
        if hasattr(smart_api, "access_token") and smart_api.access_token:
            response = smart_api.terminateSession(CLIENT_CODE)
            print("✅ Logout successful!")
        else:
            print("⚠️ Not logged in. Skipping logout.")
    except Exception as e:
        print(f"❌ Logout failed: {str(e)}")

def calculate_balance():
    funds = smart_api.rmsLimit()
    return int(float(funds["data"]["availablecash"]))
    
if __name__ == "__main__":
    login()
    funds = calculate_balance()
    send_whatsapp_message(f"Angel One balance is :{funds}")
    #smart_api.terminateSession("AAAI570791")
    logout()
