import pyotp
from SmartApi import SmartConnect
from datetime import datetime, timedelta
import os

# Credentials & Configurations
API_KEY = 'I39xpH90'
PASSWORD = '1611'
CLIENT_CODE = 'AAAI570791'
TOTP_SECRET = 'ZXI5JF7SKHJND6W2XCBHYPLEJU'
LOT_SIZE = 75  # Quantity per lot

# Initialize SmartConnect
smart_api = SmartConnect(api_key=API_KEY)

def login():
    """Logs in and generates authentication tokens."""
    global smart_api
    totp = pyotp.TOTP(TOTP_SECRET).now()
    session = smart_api.generateSession(CLIENT_CODE, PASSWORD, totp)
    if session.get("status") is True:
        print("✅ Login successful!")
    else:
        raise Exception(f"❌ Login failed: {session.get('message', 'Unknown error')}")

def get_nifty_atm():
    """Fetches the nearest ATM strike price for NIFTY."""
    spot_data = smart_api.ltpData("NSE", "NIFTY", "26000")
    if spot_data.get("status") is True:
        return round(float(spot_data["data"]["ltp"]) / 50) * 50  # Round to nearest 50
    raise Exception("❌ Failed to get NIFTY ATM price!")

def get_symbol_for_atm(strike_price, expiry_date):
    """Generate the symbol for NIFTY options based on the strike price and expiry date."""
    expiry_str = expiry_date.strftime("%d%b%y").upper()
    strike_str = str(strike_price).zfill(5)
    return f"NIFTY{expiry_str}{strike_str}CE", f"NIFTY{expiry_str}{strike_str}PE"

def get_symbol_token(symbol):
    """Fetches the symbol token for a given symbol."""
    search_response = smart_api.searchScrip("NFO", symbol)
    if search_response.get("status") is True:
        return search_response["data"][0]["symboltoken"]
    raise Exception(f"❌ Failed to get symbol token for {symbol}")

def get_ltp(symbol, symbol_token):
    """Fetches the LTP (Last Traded Price) for the given symbol using symbol token."""
    ltp_data = smart_api.ltpData("NFO", symbol, symbol_token)
    if ltp_data.get("status") is True:
        return float(ltp_data["data"]["ltp"])
    return None

def place_order(symbol, action, quantity, price):
    """Places a market order for the given symbol."""
    try:
        order_params = {
            "exchange": "NFO",
            "symboltoken": symbol,
            "tradingsymbol": symbol,
            "transactiontype": action,  # 'BUY' or 'SELL'
            "quantity": quantity,
            "price": price,
            "ordertype": "LIMIT",
            "producttype": "INTRADAY",
            "duration": "DAY"
        }
        order_response = smart_api.placeOrder(order_params)
        return order_response
    except Exception as e:
        print(f"❌ Failed to place order: {e}")
        return None

def get_expiry_day():
    """Get the correct expiry day based on holidays and weekends."""
    today = datetime.today()
    holiday_file = "nifty_expiry_holidays.txt"
    holidays = []
    
    if os.path.exists(holiday_file):
        with open(holiday_file, "r") as file:
            holidays = [line.strip() for line in file.readlines()]

    expiry_day = today + timedelta(days=(3 - today.weekday()))  # Thursday

    while expiry_day.strftime("%d%b%y") in holidays or expiry_day.weekday() in [5, 6]:  # Weekend check
        expiry_day -= timedelta(days=1)

    return expiry_day

def run_strategy():
    """Runs the trading strategy."""
    print("🔄 Running strategy...")
    login()
    
    # Step 1: Wait until 9:55 AM to get ATM Strike Price
    while datetime.now().strftime("%H:%M") < "09:55":
        pass  # Wait until 9:55 AM

    atm_strike = get_nifty_atm()
    print(f"🎯 9:55 AM ATM Strike Price: {atm_strike}")

    # Step 2: Get Expiry Date
    expiry_day = get_expiry_day()

    # Step 3: Generate CE & PE Symbols
    ce_symbol, pe_symbol = get_symbol_for_atm(atm_strike, expiry_day)

    # Step 4: Get Symbol Tokens
    ce_symbol_token = get_symbol_token(ce_symbol)
    pe_symbol_token = get_symbol_token(pe_symbol)

    # Step 5: Monitor High from 9:15 to 10:00 AM
    print("🕒 Tracking day high from 9:15 to 10:00 AM...")
    high_ce = None
    high_pe = None

    while datetime.now().strftime("%H:%M") < "10:00":
        ce_ltp = get_ltp(ce_symbol, ce_symbol_token)
        pe_ltp = get_ltp(pe_symbol, pe_symbol_token)

        if ce_ltp:
            high_ce = ce_ltp if high_ce is None else max(high_ce, ce_ltp)
        if pe_ltp:
            high_pe = pe_ltp if high_pe is None else max(high_pe, pe_ltp)

    print(f"✅ 10:00 AM Highs Locked - CE: {high_ce}, PE: {high_pe}")

    # Step 6: Monitor Breakout from 10:01 AM
    print("📈 Monitoring breakout after 10:01 AM...")

    while True:
        ce_ltp = get_ltp(ce_symbol, ce_symbol_token)
        pe_ltp = get_ltp(pe_symbol, pe_symbol_token)

        if ce_ltp and ce_ltp > high_ce:
            print("🚀 CE breakout detected, executing trade...")
            place_order(ce_symbol, "BUY", LOT_SIZE, ce_ltp)
            stop_loss = ce_ltp * 0.90
            target = ce_ltp * 1.15
            print(f"📊 Target: {target}, Stop-Loss: {stop_loss}")
            break  # Exit loop after trade

        elif pe_ltp and pe_ltp > high_pe:
            print("🚀 PE breakout detected, executing trade...")
            place_order(pe_symbol, "BUY", LOT_SIZE, pe_ltp)
            stop_loss = pe_ltp * 0.90
            target = pe_ltp * 1.15
            print(f"📊 Target: {target}, Stop-Loss: {stop_loss}")
            break  # Exit loop after trade

# Main execution
if __name__ == "__main__":
    run_strategy()

