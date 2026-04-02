import os
import pyotp
import platform
import getpass
import requests
from datetime import datetime
from SmartApi import SmartConnect
import time

# ------------------ Config (edit only if needed) ------------------ #
# Telegram
BOT_TOKEN = "8313800040:AAFbD8M5e6g8OF2SlGJzgfM9c9oyfZyah6c"
CHAT_IDS = ["632084234"]

# Accounts (two)
accounts = [
    {
        "label": "Account 1",
        "API_KEY": "xgMtWyMS",
        "PASSWORD": "1611",
        "CLIENT_CODE": "AAAI570791",
        "TOTP_SECRET": "ZXI5JF7SKHJND6W2XCBHYPLEJU"
    }
    #,
    #{
    #    "label": "Account 2",
    #    "API_KEY": "hF0cGbte",
    #    "PASSWORD": "1611",
    #    "CLIENT_CODE": "AAAO459213",
    #    "TOTP_SECRET": "5NKNRIWMHTN47ZWH5GK2WKTYKM"
    #}
]

# Platform paths
system_platform = platform.system()
current_user = getpass.getuser()

if system_platform == "Windows":
    holiday_location = "C:\\Kani_Personal\\Automate_Trading\\AlgoTrading\\"
    log_path = f"C:/Kani_Personal/Automate_Trading/Option_Selling_Vikas/job_logs/job_balance_check_{datetime.now().strftime('%Y-%m-%d')}.txt"
elif system_platform == "Darwin":
    holiday_location = "/Users/kanisgar/Documents/AlgoTrading/"
    log_path = f"/Users/kanisgar/Documents/Option_Selling_Vikas/job_logs/job_balance_check_{datetime.now().strftime('%Y-%m-%d')}.txt"
else:
    holiday_location = f"/home/{current_user}/AlgoTrading/"
    log_path = f"{holiday_location}Option_Selling_Vikas/job_logs/job_balance_check_{datetime.now().strftime('%Y-%m-%d')}.txt"

shared_utils_path = os.path.join(holiday_location, "common")
os.makedirs(os.path.dirname(log_path), exist_ok=True)

# ------------------ Simple logging ------------------ #
def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} - {msg}"
    print(line)
    try:
        with open(log_path, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass

# ------------------ File removal helper ------------------ #
def remove_file_if_exists(path):
    try:
        if os.path.exists(path):
            os.remove(path)
            log(f"Removed file: {path}")
        else:
            log(f"File not found (skip): {path}")
    except Exception as e:
        log(f"Error removing {path}: {e}")

# ------------------ Telegram ------------------ #
def send_telegram(msg):
    for chat_id in CHAT_IDS:
        try:
            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                data={"chat_id": chat_id, "text": msg}
            )
        except Exception as e:
            log(f"Telegram send error: {e}")

# ------------------ Core: login, fetch, logout ------------------ #
def fetch_profile_and_balance(acct):
    smart_api = None
    session = None
    try:
        log(f"Starting login for {acct['CLIENT_CODE']}")
        smart_api = SmartConnect(api_key=acct["API_KEY"])
        totp = pyotp.TOTP(acct["TOTP_SECRET"]).now()
        session = smart_api.generateSession(acct["CLIENT_CODE"], acct["PASSWORD"], totp)

        if not session.get("status"):
            raise Exception(f"Login failed: {session.get('message', 'No message')}")

        refresh_token = session["data"].get("refreshToken")
        profile = smart_api.getProfile(refresh_token)
        profile_name_full = profile.get("data", {}).get("name", "Unknown")
        profile_name = profile_name_full.strip().split()[0] if profile_name_full.strip() else "Unknown"
        funds = smart_api.rmsLimit()
        available_cash = funds.get("data", {}).get("availablecash", None)
        if available_cash is None:
            raise Exception("rmsLimit returned no availablecash")

        try:
            balance = int(float(available_cash))
        except Exception:
            balance = available_cash

        log(f"Fetched for {acct['CLIENT_CODE']}: {profile_name} - {balance}")
        return {"client": acct["CLIENT_CODE"], "name": profile_name, "balance": balance, "error": None}
    except Exception as e:
        log(f"Error for {acct['CLIENT_CODE']}: {e}")
        return {"client": acct["CLIENT_CODE"], "name": None, "balance": None, "error": str(e)}
    finally:
        try:
            if smart_api is not None:
                smart_api.terminateSession(acct["CLIENT_CODE"])
                log(f"Terminated session for {acct['CLIENT_CODE']}")
        except Exception as e:
            log(f"Error terminating session for {acct['CLIENT_CODE']}: {e}")

# ------------------ MAIN ------------------ #
if __name__ == "__main__":
    log("Job started: cleaning cache and checking balances")

    # ------------------ Cache Cleanup ------------------ #
    # Prepare list of cache files (shared + per-user)
    cache_files = [
        os.path.join(shared_utils_path, "orderbook_cache.json"),
        os.path.join(shared_utils_path, "orderbook_cache.lock"),
        os.path.join(shared_utils_path, "orderbook_cache_kulo.json"),
        os.path.join(shared_utils_path, "orderbook_cache_kulo.lock")
    ]

    """  # Add per-user cache files dynamically
    for acct in accounts:
        suffix = acct["CLIENT_CODE"].lower()
        cache_files.append(os.path.join(shared_utils_path, f"orderbook_cache_{suffix}.json"))
        cache_files.append(os.path.join(shared_utils_path, f"orderbook_cache_{suffix}.lock"))"""

    # Remove all
    for f in cache_files:
        remove_file_if_exists(f)

    # ------------------ Fetch Balances ------------------ #
    results = []
    for acct in accounts:
        res = fetch_profile_and_balance(acct)
        results.append(res)
        time.sleep(1)  # avoid rate limit

    # ------------------ Summary ------------------ #
    lines = ["Angel One Balances:"]
    for r in results:
        if r["error"]:
            lines.append(f"{r['client']}: ERROR - {r['error']}")
        else:
            try:
                bal_str = f"₹{int(r['balance']):,}"
            except Exception:
                bal_str = str(r['balance'])
            lines.append(f"{r['client']} ({r['name']}): {bal_str}")

    message = "\n".join(lines)
    log("Summary:\n" + message)
    send_telegram(message)
    log("Job finished.")
