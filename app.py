import os
from datetime import datetime, timedelta
import pyotp
from SmartApi import SmartConnect
import pytz
import time
from collections import deque
import logging
import boto3
import json
import platform
import getpass
from twilio.rest import Client
import sys
# 🔹 Credentials & Configurations
API_KEY = 'I39xpH90'
PASSWORD = '1611'
CLIENT_CODE = 'AAAI570791'
TOTP_SECRET = 'ZXI5JF7SKHJND6W2XCBHYPLEJU'
account_sid = 'AC6ef902b81d63731c13b746613aadb2aa'
auth_token = '06c408e1a82a20ae2b839f2cceac4705'  # Replace with actual token
current_date = datetime.now().strftime("%Y-%m-%d")
refresh_token = None

#For EC2 False by Default
should_stop_ec2_on_exit = False
# Define Timezones
finland_tz = pytz.timezone("Europe/Helsinki")  # Laptop time
india_tz = pytz.timezone("Asia/Kolkata")  # IST timezone

# Initialize SmartConnect
smart_api = SmartConnect(api_key=API_KEY)

def trigger_ec2_shutdown_lambda():
    FUNCTION_NAME = "stopEC2Instance"
    INSTANCE_ID = "i-0bc461a1bc178f190"
    
    payload = {
        "instance_id": INSTANCE_ID
    }

    try:
        lambda_client = boto3.client("lambda", region_name="us-east-1")  # Adjust your region
        response = lambda_client.invoke(
            FunctionName=FUNCTION_NAME,
            InvocationType="Event",  # Async execution
            Payload=json.dumps(payload).encode('utf-8')
        )
        log_and_print("🛑 EC2 shutdown Lambda triggered successfully.")
    except Exception as e:
        log_and_print(f"⚠️ Failed to trigger Lambda: {e}")


def on_session_expiry():
    log_and_print("⚠️ Session expired! Re-authenticating via hook...")
    login()

smart_api.setSessionExpiryHook(on_session_expiry)
#For twilio
client = Client(account_sid, auth_token)
#For Trade
LOT_SIZE=75
risk_min=2000
risk_max=2700
def_buy_qty=75
system_platform = platform.system()
current_user = getpass.getuser()

if system_platform == "Windows":
    holiday_location = "C:\\Kani_Personal\\Automate_Trading\\AlgoTrading\\"
    log_path = f"C:/Kani_Personal/Automate_Trading/AlgoTrading/job_logs/job_{datetime.now().strftime('%Y-%m-%d')}.txt"

elif system_platform == "Darwin":  # Mac
    holiday_location = "/Users/kanisgar/Documents/AlgoTrading/"
    log_path = f"/Users/kanisgar/Documents/AlgoTrading/job_logs/job_{datetime.now().strftime('%Y-%m-%d')}.txt"

elif system_platform == "Linux":
    if current_user == "ec2-user":
        holiday_location = "/home/ec2-user/AlgoTrading/"
        log_path = f"/home/ec2-user/AlgoTrading/job_logs/job_{datetime.now().strftime('%Y-%m-%d')}.txt"
        should_stop_ec2_on_exit = False
os.makedirs(os.path.dirname(log_path), exist_ok=True)

# 🔁 Use the holiday_location to build shared path
shared_utils_path = os.path.join(holiday_location, "common")
sys.path.append(shared_utils_path)
from get_cached_order_book import get_order_book
CACHE_FILE = os.path.join(shared_utils_path, "orderbook_cache.json")
LOCK_FILE = os.path.join(shared_utils_path, "orderbook_cache.lock")

# Configure logging
logging.basicConfig(
    filename=log_path,
    filemode='a',
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    level=logging.INFO
)
last_logged_time = 0
ltp_call_timestamps = deque()
def log_and_print(message, level="info"):
    print(message)
    if level == "info":
        logging.info(message)
    elif level == "error":
        logging.error(message)
    elif level == "warning":
        logging.warning(message)
    elif level == "debug":
        logging.debug(message)

def calculate_quantity_with_risk(entry_price):
    try:
        investment_per_lot = entry_price * LOT_SIZE
        risk_per_lot = investment_per_lot * 0.10  # 10% risk of the investment
        max_lots = int(risk_max // risk_per_lot)  # We divide the max risk by the risk per lot to find max lots
        total_investment_x_lots = investment_per_lot * max_lots
        total_risk_x_lots = risk_per_lot * max_lots
        total_investment_x_plus_1_lots = investment_per_lot * (max_lots + 1)
        total_risk_x_plus_1_lots = risk_per_lot * (max_lots + 1)
        if total_risk_x_lots >= risk_min and total_risk_x_lots <= risk_max:
            return max_lots * LOT_SIZE
        elif total_risk_x_plus_1_lots > risk_max:
            return max_lots * LOT_SIZE  # Return lot * 75 as the quantity
        return def_buy_qty
    except Exception as e:
        log_and_print(f"Error in calculate_quantity_with_risk: {e}", "error")
        return def_buy_qty 
    
def is_market_holiday():
    holiday_file = holiday_location + "nifty_expiry_holidays.txt"  
    try:
        with open(holiday_file, "r") as f:
            holidays = [line.strip() for line in f.readlines()]
    except FileNotFoundError:
        log_and_print(f"Warning: {holiday_file} not found. Assuming no holidays.")
        return False
    today = datetime.today().strftime("%d%b%y")  # Format like 26Feb25
    return today in holidays

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
        log_and_print(f"WhatsApp Message Sent: {message_body}")
    except Exception as e:
        log_and_print(f"Failed to send message: {e}")

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
    try:
        global smart_api
        totp = pyotp.TOTP(TOTP_SECRET).now()
        session = smart_api.generateSession(CLIENT_CODE, PASSWORD, totp)
        if session.get("status") is True:
            refresh_token = session["data"]["refreshToken"]
            log_and_print("✅ Login successful!")
        else:
            send_whatsapp_message("❌ Login failed:")
            log_and_print(f"❌ Login failed: {session.get('message', 'Unknown error')}")
            raise Exception(f"❌ Login failed: {session.get('message', 'Unknown error')}")
    except Exception as e:
        log_and_print(f"🔒 Inside Login() and exception is {e}")

def is_logged_in(refresh_token):
    try:
        time.sleep(1)
        response = smart_api.getProfile(refresh_token)
        # If it returns data, assume logged in
        stat = response.get("status")
        #Disabling the below log and print to avoid multiple print statment in logs
        #log_and_print(f"Inside is_logged_in method and response is {stat}")
        return response.get("status") == True
    except Exception as e:
        log_and_print(f"🔒 Session not active or error occurred: {e}")
        return False

def get_order_status_from_book(order_id):
    """
    Fetch order status from Angel One order book.
    Returns the order status as a string or "UNKNOWN" if not found.
    """
    #time.sleep(1)
    order_book = get_order_book(smart_api,CACHE_FILE,LOCK_FILE)  # Fetch all orders
    
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
    try:
        search_response = smart_api.searchScrip("NFO", symbol)
        if search_response.get("status") is True:
            return search_response["data"][0]["symboltoken"]
        else:
         log_and_print(f"❌ Failed to get symbol token for {symbol} and exception is {e}")
         send_whatsapp_message(f"❌ Failed to get symbol token for {symbol} and exception is {e}")
         raise Exception(f"❌ Failed to get symbol token for {symbol} and exception is {e}")
    except Exception as e:
        log_and_print(f"❌ Failed to get symbol token for {symbol} and exception is {e}")
        send_whatsapp_message(f"❌ Failed to get symbol token for {symbol} and exception is {e}")
        raise Exception(f"❌ Failed to get symbol token for {symbol} and exception is {e}")
    

def get_ltp(symbol, symbol_token):
    """Fetches the LTP (Last Traded Price) for the given symbol using symbol token."""
    global last_logged_time
    
    try:
        #if not is_logged_in(refresh_token):
         #   log_and_print("Session expired, re-authenticating before square-off...")
         #   smart_api.terminateSession(CLIENT_CODE)
         #   login()
        current_time = time.time()
        ltp_call_timestamps.append(current_time)
        while ltp_call_timestamps and current_time - ltp_call_timestamps[0] > 60:
            ltp_call_timestamps.popleft()
        if current_time - last_logged_time >= 60:
            log_and_print(f"🕒 LTP calls in last 60 seconds: {len(ltp_call_timestamps)}")
            last_logged_time = current_time
        time.sleep(0.5)
        ltp_data = smart_api.ltpData("NFO", symbol, symbol_token)
        if ltp_data.get("status") is True:
            return float(ltp_data["data"]["ltp"])
        return None
    except Exception as e:
        log_and_print(f"❌ Failed to get LTP for Symbol:{symbol} and Symbol Token:{symbol_token} and exception is {e} ")

def place_order(symbol, action, quantity, price, symboltoken, ordertype):
    """Places a market order for the given symbol."""
    try:
        if ordertype in ["MARKET", "LIMIT"]:
           variety = "NORMAL"
        else:
           variety = "STOPLOSS"
        order_params = {
            "exchange": "NFO",
            "variety": variety,
            "symboltoken": symboltoken,
            "tradingsymbol": symbol,
            "transactiontype": action,  # 'BUY' or 'EXIT'
            "quantity": quantity,
            "price": price,
            "triggerprice":price,
            "ordertype":ordertype,
            "producttype": "INTRADAY",
            "duration": "DAY"
        }
        order_response = smart_api.placeOrder(order_params)
        return order_response
    except Exception as e:
        send_whatsapp_message(f"❌ Failed to place order : {e}")
        log_and_print(f"❌ Failed to place order : {e}")
        raise Exception(f"❌ Failed to place order: {e}")
        return None

def cancel_order(order_id):
    """Cancel the order by its order ID."""
    try:
        cancel_response = smart_api.cancelOrder(str(order_id), "STOPLOSS")
        return cancel_response
    except Exception as e:
        send_whatsapp_message(f"❌ DO MANUALLY; Failed to cancel order {order_id}: {e}")
        log_and_print(f"❌ Failed to cancel order {order_id}: {e}")
        return None

def get_expiry_day():
    today = datetime.today()
    holiday_file = holiday_location + "nifty_expiry_holidays.txt"
    holidays = []
    if os.path.exists(holiday_file):
        with open(holiday_file, "r") as file:
            holidays = [line.strip() for line in file.readlines()]
    if today.weekday() == 3 and today.strftime("%d%b%y") not in holidays:
        expiry_day = today
    else:
        # Find next Thursday (weekday = 3)
        days_ahead = (3 - today.weekday() + 7) % 7
        expiry_day = today + timedelta(days=days_ahead)
        # Adjust expiry_day if it's a holiday or falls on weekend
        while expiry_day.strftime("%d%b%y") in holidays or expiry_day.weekday() in [5, 6]:
            expiry_day -= timedelta(days=1)
    return expiry_day

def get_executed_price(order_id):
    """Fetch the exact executed price for a specific order ID."""
    try:
        time.sleep(1)
        all_orders = get_order_book(smart_api,CACHE_FILE,LOCK_FILE)  # Get the list of all today's orders
        if all_orders.get("status"):
            orders = all_orders["data"]
            for order in orders:
                if order.get("orderid") == order_id:
                    if order.get("orderstatus").lower() == "complete":
                        executed_price = float(order.get("averageprice"))
                        log_and_print(f" The order executed price is {executed_price}")
                        return executed_price
                    else:
                        log_and_print(f"⚠️ Order ID {order_id} is not fully complete yet. Status: {order.get('orderstatus')}")
                        return None
        else:
            log_and_print("⚠️ No order data received from orderBook()")
    except Exception as e:
        log_and_print(f"❌ Failed to fetch executed price for order ID {order_id}: {e}")
        send_whatsapp_message(f"❌ Failed to fetch executed price for order ID {order_id}: {e}")
    return None

def get_day_high(symbol, symbol_token):
    """Fetch the day high for the given symbol using the LTP response."""
    response = smart_api.ltpData("NFO",symbol, symbol_token)
#get_ltp(symbol, symbol_token)  # Assuming this function fetches the LTP response as shown
    if response['status'] and 'data' in response:
        day_high = response['data']['high']  # Extract day high from response
        return day_high
    else:
        send_whatsapp_message(f"Error fetching data for {symbol}")
        raise Exception(f"Error fetching data for {symbol}")
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

    log_and_print(f"✅ 10:00 AM Highs Locked - CE: {high_ce}, PE: {high_pe}")
    return high_ce, high_pe

def run_strategy():
    """Runs the trading strategy."""
    log_and_print("🔄 Running strategy...")
    login()

    # Get current IST time
    current_time = get_current_ist_time().strftime("%H:%M")
    log_and_print(f"Current IST time is {current_time}")

    if "08:00" <= current_time < "10:00":
        # Execute automated flow before 10:00 AM
        wait_until_ist("09:55")  # Wait until 9:55 AM
        if not is_logged_in(refresh_token):
            log_and_print("Session expired, re-authenticating before order placing...")
            login()
        atm_strike = get_nifty_atm()
        log_and_print(f"🎯 9:55 AM ATM Strike Price: {atm_strike}")

        expiry_day = get_expiry_day()
        log_and_print(f"The expiry day is {expiry_day}")
        ce_symbol, pe_symbol = get_symbol_for_atm(atm_strike, expiry_day)

        ce_symbol_token = get_symbol_token(ce_symbol)
        time.sleep(1)
        pe_symbol_token = get_symbol_token(pe_symbol)

        log_and_print("🕒 Tracking day high from 9:55 to 10:00 AM IST...")
        high_ce, high_pe = track_highs_until_1000(ce_symbol, ce_symbol_token, pe_symbol, pe_symbol_token)


    else:
        # Manual input if script runs after 10:00 AM
        log_and_print("⏳ Script started after 10:00 AM. Manual input required.")
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
            log_and_print("❌ Trade missed for today. Exiting...")
            return  # Exit script immediately

    log_and_print("📈 Monitoring breakout after 10:01 AM...")
    send_whatsapp_message(f"🔔{current_date}: 10:00 AM Highs Locked:\n📈 CE({ce_symbol}): {high_ce}\n📉 PE({pe_symbol}): {high_pe}.\nWaiting for Breakout after 10:01 AM")

    active_trade = None  # Track active CE or PE trade
    ce_order_id = None
    pe_order_id = None
    target_order_id = None
    stop_loss_order_id = None
    pending_order_logged = False
    exit_order_logged = False
    quantity_buy = 75
    start_time = datetime.now()
    order_type_placed = None
    entry_price = None
    trade_order_id = None
    while True:
        current_time = datetime.now()
        elapsed_time = current_time - start_time
        if elapsed_time >= timedelta(hours=5):
            log_and_print("🛑 5 hours completed. Exiting the loop.")
            send_whatsapp_message("🛑 5 hours completed. Exiting the loop.")
            if should_stop_ec2_on_exit:
                log_and_print("Closing the EC2 instance")
                trigger_ec2_shutdown_lambda()
            break
        ce_ltp = get_ltp(ce_symbol, ce_symbol_token)
        pe_ltp = get_ltp(pe_symbol, pe_symbol_token)

        if active_trade is None:  # No active trade
           if ce_ltp and ce_ltp >= high_ce * 0.95  and ce_order_id is None:
               quantity_buy = calculate_quantity_with_risk(high_ce + 0.20)
               if ce_ltp > high_ce:
                   log_and_print(f"🚀 CE breakout confirmed. Placing MARKET order.")
                   if pe_order_id:
                       cancel_order(pe_order_id)
                       pe_order_id = None
                       log_and_print(f"❌ PE order cancelled before CE execution")                   
                   ce_order_id = place_order(ce_symbol, "BUY", quantity_buy, None, ce_symbol_token, "MARKET")
                   order_type_placed = "MARKET"
                   log_and_print(f"🚀{current_date}: CE breakout confirmed. Placing MARKET order.")
                   send_whatsapp_message(f"🚀{current_date}: CE breakout confirmed. Placing MARKET order.")
               else:
                   log_and_print(f"🚀 Placing CE Limit Order at {high_ce + 0.20}")
                   if pe_order_id:
                       cancel_order(pe_order_id)
                       pe_order_id = None
                       log_and_print(f"❌ PE order cancelled before CE execution")                   
                   ce_order_id = place_order(ce_symbol, "BUY", quantity_buy, high_ce + 0.20, ce_symbol_token, "STOPLOSS_LIMIT")
                   order_type_placed = "STOPLOSS_LIMIT"
                   log_and_print(f"🚀{current_date}: Placing BUY CE({ce_symbol}) Limit Order at {high_ce + 0.20}. Order {ce_order_id} not yet executed")
                   send_whatsapp_message(f"🚀{current_date}: Placing BUY CE({ce_symbol}) Limit Order at {high_ce + 0.20}. Order {ce_order_id} not yet executed")
           
           if pe_ltp and pe_ltp >= high_pe * 0.95 and pe_order_id is None:
               quantity_buy = calculate_quantity_with_risk(high_pe + 0.20)
               if pe_ltp > high_pe:
                   log_and_print(f"🚀 PE breakout confirmed. Placing MARKET order.")
                   if ce_order_id:
                       cancel_order(ce_order_id)
                       ce_order_id = None
                       log_and_print(f"❌ CE order cancelled before PE execution")                   
                   pe_order_id = place_order(pe_symbol, "BUY", quantity_buy, None, pe_symbol_token, "MARKET")
                   order_type_placed = "MARKET"
                   log_and_print(f"🚀{current_date}: PE breakout confirmed. Placing MARKET order.")
                   send_whatsapp_message(f"🚀{current_date}: PE breakout confirmed. Placing MARKET order.")
               else:
                   log_and_print(f"🚀 Placing PE Limit Order at {high_pe + 0.20}")
                   if ce_order_id:
                       cancel_order(ce_order_id)
                       ce_order_id = None
                       log_and_print(f"❌ CE order cancelled before PE execution")                   
                   pe_order_id = place_order(pe_symbol, "BUY", quantity_buy, high_pe + 0.20, pe_symbol_token, "STOPLOSS_LIMIT")
                   order_type_placed = "STOPLOSS_LIMIT"
                   log_and_print(f"🚀{current_date}: Placing BUY PE({pe_symbol}) Limit Order at {high_pe + 0.20}. Order {pe_order_id} not yet executed")
                   send_whatsapp_message(f"🚀{current_date}: Placing BUY PE({pe_symbol}) Limit Order at {high_pe + 0.20}. Order {pe_order_id} not yet executed")
                   
           if ce_order_id:
               ce_status = get_order_status_from_book(ce_order_id)
               if ce_status in ["complete", "executed"]:
                   active_trade = "CE"
                   trade_order_id = ce_order_id
                   if order_type_placed == "MARKET" and entry_price is None:
                       entry_price = get_executed_price(ce_order_id)
                   else:
                       entry_price = high_ce + 0.20
                   stop_loss_price_trigger = round(round((entry_price * 0.90) / 0.05) * 0.05, 2)
                   stop_loss_price = "{:.2f}".format(stop_loss_price_trigger)
                   stop_loss_order_id  = place_order(ce_symbol, "SELL", quantity_buy, stop_loss_price, ce_symbol_token,"STOPLOSS_LIMIT")
                   if stop_loss_order_id:
                       log_and_print(f"✅ CE order {ce_order_id} executed. Setting active_trade to CE. Placed SL order {stop_loss_order_id} for safety at {stop_loss_price}. Proceeding with exit orders")
                       send_whatsapp_message(f"✅ CE order {ce_order_id} executed. Setting active_trade to CE. Proceeding with exit orders")
                    
           elif pe_order_id:
               pe_status = get_order_status_from_book(pe_order_id)
               if pe_status in ["complete", "executed"]:
                   active_trade = "PE"
                   trade_order_id = pe_order_id
                   if order_type_placed == "MARKET" and entry_price is None:
                       entry_price = get_executed_price(pe_order_id)
                   else:
                       entry_price = high_pe + 0.20
                   stop_loss_price_trigger = round(round((entry_price * 0.90) / 0.05) * 0.05, 2)
                   stop_loss_price = "{:.2f}".format(stop_loss_price_trigger)
                   stop_loss_order_id  = place_order(pe_symbol, "SELL", quantity_buy, stop_loss_price, pe_symbol_token,"STOPLOSS_LIMIT")
                   if stop_loss_order_id:
                       log_and_print(f"✅ PE order {pe_order_id} executed. Setting active_trade to PE. Placed SL order {stop_loss_order_id} for safety at {stop_loss_price}.Proceeding with exit orders")
                       send_whatsapp_message(f"✅ PE order {pe_order_id} executed. Setting active_trade to PE. Proceeding with exit orders")

        else:  # Active trade exists, monitor SL & Target exit
            trade_symbol = ce_symbol if active_trade == "CE" else pe_symbol
            trade_symbol_token = ce_symbol_token if active_trade == "CE" else pe_symbol_token
            trade_ltp = get_ltp(trade_symbol, trade_symbol_token)
            target_price_trigger = round(round((entry_price * 1.15) / 0.05) * 0.05, 2)
            target_price = "{:.2f}".format(target_price_trigger)
            stop_loss_price_trigger = round(round((entry_price * 0.90) / 0.05) * 0.05, 2)
            stop_loss_price = "{:.2f}".format(stop_loss_price_trigger)

            # If price is near the target, place target order
            if trade_ltp >= target_price_trigger * 0.93 and target_order_id is None:
                if stop_loss_order_id:
                    log_and_print(f"❌ Cancelling Stop Loss Order as Target is Near")
                    cancel_order(stop_loss_order_id)
                    stop_loss_order_id = None
                if trade_ltp >= target_price_trigger:
                    log_and_print(f"🎯 Target price {target_price_trigger} already breached. Placing immediate MARKET SELL.")
                    target_order_id = place_order(trade_symbol, "SELL", quantity_buy, None, trade_symbol_token, "MARKET")
                    if target_order_id:
                        send_whatsapp_message(f"🎯{current_date}: Target breached. Exiting immediately at Market for {trade_symbol}.")
                else:
                    log_and_print(f"🎯 Placing Target Order at {target_price}")
                    target_order_id = place_order(trade_symbol, "SELL", quantity_buy, target_price, trade_symbol_token,"STOPLOSS_LIMIT")
                    send_whatsapp_message(f"❌{current_date}: Cancelling Stop Loss Order and placing the Target order {trade_symbol} for price : {target_price} ")

            # If price reverses and nears the stop-loss, cancel target and place SL order
            elif trade_ltp <= stop_loss_price_trigger * 1.05 and stop_loss_order_id is None:
                if target_order_id:
                    log_and_print(f"❌ Cancelling Target Order and placing Stop Loss Order at {stop_loss_price}")
                    cancel_order(target_order_id)  # Cancel target order
                    target_order_id = None  # Reset target order ID
                if trade_ltp <= stop_loss_price_trigger:
                    log_and_print(f"🛑 Stop Loss price {stop_loss_price_trigger} breached. Placing immediate MARKET SELL.")
                    stop_loss_order_id = place_order(trade_symbol, "SELL", quantity_buy, None, trade_symbol_token, "MARKET")
                    if stop_loss_order_id:
                        send_whatsapp_message(f"🛑{current_date}: Stop Loss breached. Exiting immediately at Market for {trade_symbol}.")
                else:
                    log_and_print(f"🛑 Placing Stop Loss STOPLOSS_LIMIT Order at {stop_loss_price}")
                    stop_loss_order_id = place_order(trade_symbol, "SELL", quantity_buy, stop_loss_price, trade_symbol_token,"STOPLOSS_LIMIT")
                    send_whatsapp_message(f"❌{current_date}:Cancelling Target Order and placing the SL order {trade_symbol} for price : {stop_loss_price} ")

            # Exit if target is hit
            if target_order_id:
                target_status = get_order_status_from_book(target_order_id)
                if target_status in ["complete", "executed"]:
                    log_and_print(f"✅ Target reached, exiting at {trade_ltp}")
                    send_whatsapp_message(f"✅{current_date}: Target reached, exiting at {trade_ltp} for {trade_symbol}")
                    if should_stop_ec2_on_exit:
                        log_and_print("Shutting down EC2 instance")
                        trigger_ec2_shutdown_lambda()
                    break
                elif trade_ltp >= target_price_trigger:
                    send_whatsapp_message(f"✅ !!!!!1Target reached at {trade_ltp}. But the order is not yet executed. Check FAASSTTTT")
                    break

            # Exit if stop-loss is hit
            elif stop_loss_order_id:
                sl_status = get_order_status_from_book(stop_loss_order_id)
                if sl_status in ["complete", "executed"]:
                    log_and_print(f"✅ Stop Loss triggered, exiting at {trade_ltp}")
                    send_whatsapp_message(f"✅{current_date}: Stop Loss triggered, exiting at {trade_ltp} for {trade_symbol}")
                    if should_stop_ec2_on_exit:
                        log_and_print("Shutting down EC2 instance")
                        trigger_ec2_shutdown_lambda()
                    break
                elif trade_ltp <= stop_loss_price_trigger:
                    send_whatsapp_message(f"✅ !!!!!SL reached at {trade_ltp}. But the order is not yet executed. Check FAASSTTTT")
                    break

# Main execution
if __name__ == "__main__":
    try:
        log_and_print(f"job is running on {system_platform}")
        if is_market_holiday():
            send_whatsapp_message(f"🔔:Market holiday on {current_date}. Exiting script.")
            log_and_print(f"Market holiday on {current_date}. Exiting script.")
            if should_stop_ec2_on_exit:
                log_and_print("Shutting down EC2 instance due to market holiday")
                trigger_ec2_shutdown_lambda()
        else:
            run_strategy()
    except Exception as e:
        log_and_print(f"❌ Exception in trading script: {str(e)}")
        send_whatsapp_message(f"❌ Exception in trading script: {str(e)}")
    finally:
        log_and_print("Logging out inside finally")
        smart_api.terminateSession(CLIENT_CODE)
        send_whatsapp_message(f"❌ Executing Finally Block")
