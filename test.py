import sys
import pyotp
import time
import pytz
from SmartApi import SmartConnect
from datetime import datetime, timedelta
from twilio.rest import Client
import os
import platform
import getpass
import requests
# ------------------ Platform-Specific Path Setup ------------------ #
system_platform = platform.system()
current_user = getpass.getuser()

if system_platform == "Windows":
    holiday_location = "C:\\Kani_Personal\\Automate_Trading\\AlgoTrading\\"
    log_path = f"C:/Kani_Personal/Automate_Trading/Option_Selling_Vikas/job_logs/job_option_selling_vikas_{datetime.now().strftime('%Y-%m-%d')}.txt"

elif system_platform == "Darwin":  # Mac
    holiday_location = "/Users/kanisgar/Documents/AlgoTrading/"
    log_path = f"/Users/kanisgar/Documents/Option_Selling_Vikas/job_logs/job_option_selling_vikas_{datetime.now().strftime('%Y-%m-%d')}.txt"

elif system_platform == "Linux":
    if current_user == "ec2-user":
        holiday_location = "/home/ec2-user/AlgoTrading/"
        log_path = f"/home/ec2-user/Option_Selling_Vikas/job_logs/job_option_selling_vikas_{datetime.now().strftime('%Y-%m-%d')}.txt"

# ------------------ Shared Utils Path ------------------ #
shared_utils_path = os.path.join(holiday_location, "common")
sys.path.append(shared_utils_path)

CACHE_FILE = os.path.join(shared_utils_path, "orderbook_cache.json")
LOCK_FILE = os.path.join(shared_utils_path, "orderbook_cache.lock")

# ------------------ Logging Function ------------------ #
def log(msg):
    with open(log_path, "a") as log_f:
        log_f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {msg}\n")
    print(msg)

# ------------------ Cache Cleanup ------------------ #
def remove_file_if_exists(file_path):
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            #log(f"✅ Removed: {file_path}")
        else:
            print(f"ℹ️ File not found: {file_path}")
    except Exception as e:
        print(f"❌ Error removing {file_path}: {str(e)}")

# ------------------ Twilio & SmartAPI Setup ------------------ #
API_KEY = 'I39xpH90'
PASSWORD = '1611'
CLIENT_CODE = 'AAAI570791'
TOTP_SECRET = 'ZXI5JF7SKHJND6W2XCBHYPLEJU'
LOT_SIZE = 75  # Quantity per lot

account_sid = 'AC6ef902b81d63731c13b746613aadb2aa'
auth_token = '06c408e1a82a20ae2b839f2cceac4705'

#For Telegram Bot
BOT_TOKEN = "8313800040:AAFbD8M5e6g8OF2SlGJzgfM9c9oyfZyah6c"
# List of Telegram Chat IDs (Replace with actual chat IDs of your recipients)
RECIPIENT_CHAT_IDS = [
    "632084234",  # Recipient 1
]

smart_api = SmartConnect(api_key=API_KEY)
client = Client(account_sid, auth_token)
"""
def send_whatsapp_message(message_body):
    recipients = [
        'whatsapp:+919042528367',
        'whatsapp:+918012991200'
    ]
    try:
        for r in recipients:
            message = client.messages.create(
                from_='whatsapp:+14155238886',
                to=r,
                body=message_body
            )
        print(f"✅ WhatsApp message sent: {message_body}")
    except Exception as e:
        print(f"❌ Failed to send WhatsApp message: {e}")
"""
def send_whatsapp_message(message_body):
    """
    Sends a message using Telegram Bot API to multiple recipients.
    :param message_body: The message content to send.
    """
    try:
        for chat_id in RECIPIENT_CHAT_IDS:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": message_body
            }
            response = requests.post(url, data=payload)
            if response.status_code == 200:
                print(f"Telegram Message Sent to {chat_id}: {message_body}")
            else:
                print(f"Failed to send Telegram message to {chat_id}: {response.text}")
    except Exception as e:
        print(f"Error sending Telegram message: {e}")

def login():
    global smart_api
    totp = pyotp.TOTP(TOTP_SECRET).now()
    session = smart_api.generateSession(CLIENT_CODE, PASSWORD, totp)
    if session.get("status") is True:
        print("✅ Login successful")
    else:
        send_whatsapp_message("❌ Login failed")
        raise Exception(f"❌ Login failed: {session.get('message', 'Unknown error')}")

def logout():
    try:
        if hasattr(smart_api, "access_token") and smart_api.access_token:
            smart_api.terminateSession(CLIENT_CODE)
            print("✅ Logout successful")
        else:
            print("⚠️ Not logged in. Skipping logout.")
    except Exception as e:
        print(f"❌ Logout failed: {str(e)}")

def calculate_balance():
    funds = smart_api.rmsLimit()
    return int(float(funds["data"]["availablecash"]))

# ------------------ Main ------------------ #
if __name__ == "__main__":
    print("🚀 Starting cache cleanup and balance check...")
    remove_file_if_exists(CACHE_FILE)
    remove_file_if_exists(LOCK_FILE)

    try:
        login()
        funds = calculate_balance()
        send_whatsapp_message(f"📈 Angel One balance is ₹{funds}")
    except Exception as e:
        send_whatsapp_message(f"❌ Error in balance check: {str(e)}")
        print(f"❌ Error during execution: {str(e)}")
    finally:
        logout()
        print("✅ Execution completed\n")
