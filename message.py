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


# Define Timezones
finland_tz = pytz.timezone("Europe/Helsinki")  # Laptop time
india_tz = pytz.timezone("Asia/Kolkata")  # IST timezone

# Initialize SmartConnect
smart_api = SmartConnect(api_key=API_KEY)
#For twilio
client = Client(account_sid, auth_token)

def send_whatsapp_message(message_body):
    """
    Sends a WhatsApp message using Twilio API.
    :param message_body: The message content to send.
    """
    try:
        message = client.messages.create(
            from_='whatsapp:+14155238886',  # Twilio sandbox number
            to='whatsapp:+919042528367',  # Your verified number
            body=message_body
        )
        print(f"WhatsApp Message Sent: {message_body}")
    except Exception as e:
        print(f"Failed to send message: {e}")

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

def get_order_status_from_book(order_id):
    """
    Fetch order status from Angel One order book.
    Returns the order status as a string or "UNKNOWN" if not found.
    """
    order_book = smart_api.orderBook()  # Fetch all orders
    
    if order_book and order_book.get("data"):  # Ensure we have valid data
        for order in order_book["data"]:  # Loop through orders
            if order.get("orderid") == order_id:
                return order.get("status", "UNKNOWN")  # Return status if found
    
    return "UNKNOWN"  # Default if order is not found

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
            "transactiontype": action,  # 'BUY' or 'EXIT'
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

    # Get current IST time
    current_time = get_current_ist_time().strftime("%H:%M")
    print(f"Current IST time is {current_time}")

    if "08:00" <= current_time < "10:00":
        # Execute automated flow before 10:00 AM
        wait_until_ist("09:55")  # Wait until 9:55 AM
        atm_strike = get_nifty_atm()
        print(f"🎯 9:55 AM ATM Strike Price: {atm_strike}")

        expiry_day = get_expiry_day()
        print(f"The expiry day is {expiry_day}")
        ce_symbol, pe_symbol = get_symbol_for_atm(atm_strike, expiry_day)

        ce_symbol_token = get_symbol_token(ce_symbol)
        time.sleep(1)
        pe_symbol_token = get_symbol_token(pe_symbol)

        print("🕒 Tracking day high from 9:55 to 10:00 AM IST...")
        high_ce, high_pe = track_highs_until_1000(ce_symbol, ce_symbol_token, pe_symbol, pe_symbol_token)


    else:
        # Manual input if script runs after 10:00 AM
        print("⏳ Script started after 10:00 AM. Manual input required.")
        atm_strike = int(input("Enter ATM Strike Price: "))
        high_ce = float(input("Enter 10:00 AM High for CE: "))
        high_pe = float(input("Enter 10:00 AM High for PE: "))

        expiry_day = get_expiry_day()
        ce_symbol, pe_symbol = get_symbol_for_atm(atm_strike, expiry_day)

        ce_symbol_token = get_symbol_token(ce_symbol)
        time.sleep(1)
        pe_symbol_token = get_symbol_token(pe_symbol)

        already_passed = input("Has either CE or PE already crossed the 10:00 AM high? (yes/no): ").strip().lower()
        if already_passed == "yes":
            print("❌ Trade missed for today. Exiting...")
            return  # Exit script immediately

    print("📈 Monitoring breakout after 10:01 AM...")
    send_whatsapp_message(f"🔔{current_date}: 10:00 AM Highs Locked:\n📈 CE({ce_symbol}): {high_ce}\n📉 PE({pe_symbol}): {high_pe}.\nWaiting for Breakout after 10:01 AM")

    active_trade = None  # Track active CE or PE trade
    ce_order_id = None
    pe_order_id = None
    target_order_id = None
    stop_loss_order_id = None
    pending_order_logged = False

    while True:
        ce_ltp = get_ltp(ce_symbol, ce_symbol_token)
        pe_ltp = get_ltp(pe_symbol, pe_symbol_token)

        if active_trade is None:  # No active trade
            if ce_ltp and ce_ltp >= high_ce * 0.97:
                print(f"🚀 Placing CE Limit Order at {high_ce + 0.20}")
                ce_order_id = place_order(ce_symbol, "BUY", LOT_SIZE, high_ce + 0.20, ce_symbol_token)
                send_whatsapp_message(f"🚀{current_date}: Placing BUY CE({ce_symbol}) Limit Order at {high_ce + 0.20}")
                active_trade = "CE"
            elif pe_ltp and pe_ltp >= high_pe * 0.97:
                print(f"🚀 Placing PE Limit Order at {high_pe + 0.20}")
                pe_order_id = place_order(pe_symbol, "BUY", LOT_SIZE, high_pe + 0.20, pe_symbol_token)
                send_whatsapp_message(f"🚀{current_date}: Placing BUY PE({pe_symbol}) Limit Order at {high_pe + 0.20}")
                active_trade = "PE"

        else:  # Active trade exists, monitor SL & Target exit
            trade_order_id = ce_order_id if active_trade == "CE" else pe_order_id
            order_status = get_order_status_from_book(trade_order_id)

            if order_status not in ["COMPLETE", "EXECUTED"]:
                if not pending_order_logged:  # Print only once
                    print(f"🚨 Order {trade_order_id} is not EXECUTED yet. Skipping exit orders.")
                    send_whatsapp_message(f"🚨{current_date}: Order {trade_order_id} is not EXECUTED yet. Skipping exit orders.")
                    pending_order_logged = True
                continue

            pending_order_logged = False

            print(f"✅ Order {trade_order_id} is executed. Proceeding with exit orders.")
            send_whatsapp_message(f"✅{current_date}: Order {trade_order_id} is executed. Proceeding with exit orders.")

            trade_symbol = ce_symbol if active_trade == "CE" else pe_symbol

            trade_symbol_token = ce_symbol_token if active_trade == "CE" else pe_symbol_token
            trade_ltp = get_ltp(trade_symbol, trade_symbol_token)
            entry_price = high_ce + 0.20 if active_trade == "CE" else high_pe + 0.20
            target_price = entry_price * 1.15
            stop_loss_price = entry_price * 0.90

            # If price is near the target, place target order
            if trade_ltp >= target_price * 0.93 and target_order_id is None:
                if stop_loss_order_id:
                    print(f"❌ Cancelling Stop Loss Order as Target is Near")
                    cancel_order(stop_loss_order_id)
                    stop_loss_order_id = None
                print(f"🎯 Placing Target Order at {target_price}")
                target_order_id = place_order(trade_symbol, "EXIT", LOT_SIZE, target_price, trade_symbol_token)
                send_whatsapp_message(f"❌{current_date}: Cancelling Stop Loss Order and placing the Target order {trade_symbol} for price : {target_price} ")

            # If price reverses and nears the stop-loss, cancel target and place SL order
            elif trade_ltp <= stop_loss_price * 1.05 and stop_loss_order_id is None:
                if target_order_id:
                    print(f"❌ Cancelling Target Order and placing Stop Loss Order at {stop_loss_price}")
                    cancel_order(target_order_id)  # Cancel target order
                    target_order_id = None  # Reset target order ID
                stop_loss_order_id = place_order(trade_symbol, "EXIT", LOT_SIZE, stop_loss_price, trade_symbol_token)
                send_whatsapp_message(f"❌{current_date}:Cancelling Target Order and placing the SL order {trade_symbol} for price : {stop_loss_price} ")

            # Exit if target is hit
            if trade_ltp >= target_price:
                print(f"✅ Target reached, exiting at {trade_ltp}")
                send_whatsapp_message(f"✅{current_date}: Target reached, exiting at {trade_ltp} for {trade_symbol}")
                break

            # Exit if stop-loss is hit
            elif trade_ltp <= stop_loss_price:
                print(f"✅ Stop Loss triggered, exiting at {trade_ltp}")
                send_whatsapp_message(f"✅{current_date}: Stop Loss triggered, exiting at {trade_ltp} for {trade_symbol}")
                break


# Main execution
if __name__ == "__main__":
    run_strategy()
