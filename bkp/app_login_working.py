import pyotp
import time
from SmartApi import SmartConnect  # Corrected case for SmartApi

# Your credentials and configurations
API_KEY = 'I39xpH90'  # Your API key
PASSWORD = '1611'  # Your password
CLIENT_CODE = 'AAAI570791'  # Your client code
TOTP_SECRET = 'ZXI5JF7SKHJND6W2XCBHYPLEJU'  # Your TOTP secret

# Initialize SmartConnect
smart_api = SmartConnect(api_key=API_KEY)

def login():
    """Logs in and generates authentication tokens."""
    global smart_api
    totp = pyotp.TOTP(TOTP_SECRET).now()
    
    print("🔄 Attempting login...")  # Debugging
    session = smart_api.generateSession(CLIENT_CODE, PASSWORD, totp)

    print("📢 Raw session response:", session)  # Debugging

    if session.get("status") is True:
        auth_token = session["data"].get("jwtToken") if session.get("data") else None
        refresh_token = session["data"].get("refreshToken") if session.get("data") else None
        feed_token = session["data"].get("feedToken") if session.get("data") else None  # ✅ Add feed token

        if not auth_token:
            raise Exception("❌ Login failed: JWT Token not received!")

        #smart_api.setAccessToken(auth_token)  # ✅ Set access token
        #smart_api.setRefreshToken(refresh_token)
        #smart_api.feedToken = feed_token  # ✅ Fix: Set feed token

        print("✅ Login successful!")
    else:
        raise Exception(f"❌ Login failed: {session.get('message', 'Unknown error')}")


def get_nifty_atm():
    """Fetches the nearest ATM strike price for NIFTY."""
    retries = 3
    for attempt in range(retries):
        try:
            spot_data = smart_api.ltpData("NSE", "NIFTY", "26000")
            print("📢 Spot price response:", spot_data)  # Debugging

            if spot_data.get("status") is True:
                spot_price = round(float(spot_data["data"]["ltp"]) / 50) * 50  # Round to nearest 50
                print(f"✅ ATM Strike Price: {spot_price}")
                return spot_price
            else:
                print(f"⚠️ Attempt {attempt + 1}: Invalid response, retrying...")
        except Exception as e:
            print(f"⚠️ Attempt {attempt + 1}: Error fetching ATM - {e}, retrying...")
        time.sleep(2)

    raise Exception("❌ Failed to get NIFTY ATM after retries!")


def run_strategy():
    """Runs the trading strategy."""
    print("🔄 Running strategy...")

    # Login to get the tokens
    login()

    # Get the ATM strike price for NIFTY
    atm_strike = get_nifty_atm()

    # Simulate the rest of the trading logic...
    # The part for fetching LTP, checking breakout, etc. will go here.

    print("📊 Strategy executed successfully!")


# Main execution
if __name__ == "__main__":
    run_strategy()

