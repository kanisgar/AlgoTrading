from filelock import FileLock
import time
import json
import os

def get_order_book(smart_api, cache_file, lock_file, ttl_seconds=1):
    current_time = time.time()

    # Check cached file first
    if os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            try:
                cache = json.load(f)
                if current_time - cache["timestamp"] < ttl_seconds:
                    return {"data": cache["data"]}
            except Exception:
                pass

    # Acquire lock and check again
    with FileLock(lock_file, timeout=5):
        if os.path.exists(cache_file):
            with open(cache_file, "r") as f:
                try:
                    cache = json.load(f)
                    if current_time - cache["timestamp"] < ttl_seconds:
                        return {"data": cache["data"]}
                except Exception:
                    pass

        print("[INFO] Fetching order book from SmartAPI...")
        data = smart_api.orderBook()
        if data and data.get("data"):
            with open(cache_file, "w") as f:
                json.dump({
                    "timestamp": time.time(),
                    "data": data["data"]
                }, f)
        return data