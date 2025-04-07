import os
from twilio.rest import Client
from datetime import datetime, timedelta

API_KEY = 'I39xpH90'
PASSWORD = '1611'
CLIENT_CODE = 'AAAI570791'
TOTP_SECRET = 'ZXI5JF7SKHJND6W2XCBHYPLEJU'
LOT_SIZE = 75  # Quantity per lot
account_sid = 'AC6ef902b81d63731c13b746613aadb2aa'
auth_token = '06c408e1a82a20ae2b839f2cceac4705'  # Replace with actual token
current_date = datetime.now().strftime("%Y-%m-%d")
client = Client(account_sid, auth_token)
holiday_location="C:\Kani_Personal\Automate_Trading\AlgoTrading\\"

def get_expiry_day():
    """Get the correct expiry day based on holidays and weekends."""
    today = datetime.today()
    holiday_file = holiday_location + "nifty_expiry_holidays.txt"
    holidays = []

    print("Loading holiday list...")
    # Load holidays from file
    if os.path.exists(holiday_file):
        with open(holiday_file, "r") as file:
            holidays = [line.strip() for line in file.readlines()] 

    # Find next Thursday (weekday = 3)
    days_ahead = (3 - today.weekday() + 7) % 7
    if days_ahead == 0:
        days_ahead = 7  # Always get *next* Thursday, not today if it's Thursday
    expiry_day = today + timedelta(days=days_ahead)
    print(f"Initial expiry day (next Thursday): {expiry_day.strftime('%Y-%m-%d')}")

    # Adjust expiry_day if it's a holiday or falls on weekend
    while expiry_day.strftime("%d%b%y") in holidays or expiry_day.weekday() in [5, 6]:  # 5 = Saturday, 6 = Sunday
        expiry_day -= timedelta(days=1)
        print(f"Adjusted expiry day due to holiday/weekend: {expiry_day.strftime('%Y-%m-%d')}")

    return expiry_day

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


if __name__ == "__main__":
    expiry = get_expiry_day()
    print(f"Final expiry day: {expiry.strftime('%Y-%m-%d')}")
    send_whatsapp_message(f"Final expiry day: {expiry.strftime('%Y-%m-%d')}")

    # Write to out.txt
    with open(holiday_location + "out.txt", "w") as f:
        f.write(f"Expiry Date: {expiry.strftime('%Y-%m-%d')}\n")
        
