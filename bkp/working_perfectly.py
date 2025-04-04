import pyotp
import time
import pytz
from SmartApi import SmartConnect
from datetime import datetime, timedelta
import os

# 🔹 Credentials & Configurations
API_KEY = 'I39xpH90'
PASSWORD = '1611'
CLIENT_CODE = 'AAAI570791'
TOTP_SECRET = 'ZXI5JF7SKHJND6W2XCBHYPLEJU'
LOT_SIZE = 75  # Quantity per lot

# Define Timezones
finland_tz = pytz.timezone("Europe/Helsinki")  # Laptop time
india_tz = pytz.timezone("Asia/Kolkata")  # IST timezone

# Initialize SmartConnect
smart_api = SmartConnect(api_key=API_KEY)

def get_current_ist_time():
    """Returns the current time in IST."""
    finland_time = datetime.now(finland_tz)  # Get Finland time
    ist_time = finland_time.astimezone(india_tz)  # Convert to IST
    return ist_time

def wait_until_ist(target_time):
    """Waits until the given target time in IST."""
    while True:
        ist_now = get_current_ist_time()
        if ist_now.strftime("%H:%M") >= target_time:
            break
        time.sleep(1)

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

def place_order(symbol, action, quantity, price, symboltoken):
    """Places a market order for the given symbol."""
    try:
        order_params = {
            "exchange": "NFO",
            "variety": "NORMAL",
            "symboltoken": symboltoken,
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

def cancel_order(order_id):
    """Cancel the order by its order ID."""
    try:
        cancel_response = smart_api.cancelOrder(str(order_id), "NORMAL")
        return cancel_response
    except Exception as e:
        print(f"❌ Failed to cancel order {order_id}: {e}")
        return None

def get_expiry_day():
    """Get the correct expiry day based on holidays and weekends."""
    today = datetime.today()
    print(f"THE CURRENT DATE IS {today}")
    holiday_file = "nifty_expiry_holidays.txt"
    holidays = []
    
    if os.path.exists(holiday_file):
        with open(holiday_file, "r") as file:
            holidays = [line.strip() for line in file.readlines()]

    expiry_day = today + timedelta(days=(3 - today.weekday()))  # Thursday

    while expiry_day.strftime("%d%b%y") in holidays or expiry_day.weekday() in [5, 6]:  # Weekend check
        expiry_day -= timedelta(days=1)

    return expiry_day

def get_day_high(symbol, symbol_token):
    """Fetch the day high for the given symbol using the LTP response."""
    response = smart_api.ltpData("NFO",symbol, symbol_token)
#get_ltp(symbol, symbol_token)  # Assuming this function fetches the LTP response as shown
    if response['status'] and 'data' in response:
        day_high = response['data']['high']  # Extract day high from response
        return day_high
    else:
        print(f"Error fetching data for {symbol}")
        return None

def track_highs_until_1000(ce_symbol, ce_symbol_token, pe_symbol, pe_symbol_token):
    """Track the highest price between 9:55 AM and 10:00 AM IST."""
    high_ce, high_pe = None, None

    # Get the initial day high at 9:55 AM
    high_ce = get_day_high(ce_symbol, ce_symbol_token)
    high_pe = get_day_high(pe_symbol, pe_symbol_token)

    # Monitor the LTP from 9:55 AM to 10:00 AM, update if new high is found
    while get_current_ist_time().strftime("%H:%M") < "10:00":
        ce_ltp = get_ltp(ce_symbol, ce_symbol_token)
        pe_ltp = get_ltp(pe_symbol, pe_symbol_token)

        if ce_ltp:
            high_ce = max(high_ce, ce_ltp) if ce_ltp > high_ce else high_ce
        if pe_ltp:
            high_pe = max(high_pe, pe_ltp) if pe_ltp > high_pe else high_pe

    print(f"✅ 10:00 AM Highs Locked - CE: {high_ce}, PE: {high_pe}")
    return high_ce, high_pe

def run_strategy():
    """Runs the trading strategy."""
    print("🔄 Running strategy...")
    login()

    # Wait until 9:55 AM IST
    wait_until_ist("09:55")
    
    atm_strike = get_nifty_atm()
    print(f"🎯 9:55 AM ATM Strike Price: {atm_strike}")

    expiry_day = get_expiry_day()
    ce_symbol, pe_symbol = get_symbol_for_atm(atm_strike, expiry_day)

    ce_symbol_token = get_symbol_token(ce_symbol)
    pe_symbol_token = get_symbol_token(pe_symbol)

    print("🕒 Tracking day high from 9:15 to 10:00 AM IST...")
    high_ce, high_pe = track_highs_until_1000(ce_symbol, ce_symbol_token, pe_symbol, pe_symbol_token)

    print("📈 Monitoring breakout after 10:01 AM...")

    active_trade = None  # Track active CE or PE trade
    ce_order_id = None
    pe_order_id = None
    target_order_id = None
    stop_loss_order_id = None

    while True:
        ce_ltp = get_ltp(ce_symbol, ce_symbol_token)
        pe_ltp = get_ltp(pe_symbol, pe_symbol_token)

        if active_trade is None:  # No active trade
            if ce_ltp and ce_ltp >= high_ce * 0.97:
                print(f"🚀 Placing CE Limit Order at {high_ce + 0.20}")
                ce_order_id = place_order(ce_symbol, "BUY", LOT_SIZE, high_ce + 0.20, ce_symbol_token)
                active_trade = "CE"
            elif pe_ltp and pe_ltp >= high_pe * 0.97:
                print(f"🚀 Placing PE Limit Order at {high_pe + 0.20}")
                pe_order_id = place_order(pe_symbol, "BUY", LOT_SIZE, high_pe + 0.20, pe_symbol_token)
                active_trade = "PE"

        else:  # Active trade exists, monitor SL & Target exit
            trade_symbol = ce_symbol if active_trade == "CE" else pe_symbol
            trade_symbol_token = ce_symbol_token if active_trade == "CE" else pe_symbol_token
            trade_ltp = get_ltp(trade_symbol, trade_symbol_token)
            entry_price = high_ce + 0.20 if active_trade == "CE" else high_pe + 0.20
            target_price = entry_price * 1.15
            stop_loss_price = entry_price * 0.90

            # If the price is near the target, place target order
            if trade_ltp >= target_price * 0.93 and target_order_id is None:
                print(f"🎯 Placing Target Order at {target_price}")
                target_order_id = place_order(trade_symbol, "SELL", LOT_SIZE, target_price, trade_symbol_token)
                if stop_loss_order_id:
                    print(f"❌ Cancelling Stop Loss Order as Target is Near")
                    cancel_order(stop_loss_order_id)
                    stop_loss_order_id = None

            # If the price reverses and nears the stop-loss, cancel target and place SL order
            elif trade_ltp <= stop_loss_price * 1.05 and stop_loss_order_id is None:
                if target_order_id:
                    print(f"❌ Cancelling Target Order and placing Stop Loss Order at {stop_loss_price}")
                    cancel_order(target_order_id)  # Cancel the target order
                    target_order_id = None  # Reset target order ID
                stop_loss_order_id = place_order(trade_symbol, "SELL", LOT_SIZE, stop_loss_price, trade_symbol_token)

            # If LTP is near the target, place a target order
            if trade_ltp >= target_price:
                print(f"✅ Target reached, exiting at {trade_ltp}")
                break

            # If LTP is near the stop-loss, place a stop-loss order
            elif trade_ltp <= stop_loss_price:
                print(f"✅ Stop Loss triggered, exiting at {trade_ltp}")
                break


# Main execution
if __name__ == "__main__":
    run_strategy()

