import requests
from twilio.rest import Client

account_sid = 'AC6ef902b81d63731c13b746613aadb2aa'
auth_token = '06c408e1a82a20ae2b839f2cceac4705'
client = Client(account_sid, auth_token)

def send_whatsapp_message(message_body):
    recipients = [
        'whatsapp:+919042528367',
        'whatsapp:+918012991200'
    ]
    
    for recipient in recipients:
        try:
            message = client.messages.create(
                from_='whatsapp:+14155238886',
                to=recipient,
                body=message_body
            )
            print(f"Sent to {recipient}: {message.sid}")
        except Exception as e:
            print(f"Failed to send to {recipient}: {e}")

def get_ngrok_url():
    try:
        r = requests.get("http://127.0.0.1:4040/api/tunnels")
        tunnels = r.json().get("tunnels", [])
        for tunnel in tunnels:
            if "https" in tunnel["public_url"]:
                return tunnel["public_url"]
    except Exception as e:
        print(f"Error fetching ngrok URL: {e}")
    return None

if __name__ == "__main__":
    url = get_ngrok_url()
    if url:
        message = f"Log server is live now! 📡\n\n🔗 {url}"
        send_whatsapp_message(message)
    else:
        send_whatsapp_message("⚠️ Failed to fetch ngrok URL. Please check manually.")
