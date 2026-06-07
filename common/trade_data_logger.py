"""
trade_data_logger.py
====================
Drop this in: /home/ec2-user/AlgoTrading/common/trade_data_logger.py

Logs all relevant data for Nifty/Sensex ATM straddle strategy.
CSV saved locally on EC2 — same folder as this file.

Call sequence from your trading scripts:
    1. logger = TradeDataLogger(instrument="NIFTY")   ← top of run_os_strategy()
    2. logger.log_pre_entry(spot)                     ← before wait_until_ist
    3. logger.log_entry(ce, pe, atm, sl30s, sl40s)   ← after execute_trade_block
    4. logger.log_first_candle(open, high, low)       ← inside loop at 9:25
    5. logger.log_eod(ce_hit, pe_hit, ...)            ← at each exit point
    6. logger.save()                                  ← in finally block
"""

import os
import csv
import requests
from datetime import datetime, date
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

# ── CSV saved in same folder as this file ──────────────────────────────────
_HERE     = os.path.dirname(os.path.abspath(__file__))
LOCAL_CSV = os.path.join(_HERE, "options_trade_log.csv")

CSV_HEADERS = [
    # Identity
    "date", "instrument", "day_of_week",
    # Pre-entry market context
    "vix_open", "spot_at_entry", "prev_close", "gap_pct",
    # Entry details
    "atm_strike",
    "ce_premium_entry", "pe_premium_entry", "straddle_price",
    "ce_sl_30_level", "pe_sl_30_level",
    "ce_sl_40_level", "pe_sl_40_level",
    # First 5-min candle (9:15 candle)
    "first_candle_open", "first_candle_high", "first_candle_low",
    "first_candle_size_pct",
    # EOD outcome — ML labels
    "ce_sl_hit", "pe_sl_hit", "double_sl_hit",
    "sl_upgrade_triggered_ce", "sl_upgrade_triggered_pe",
    "exit_time",
    # Risk signal computed at pre-entry
    "risk_signal", "risk_score", "risk_reasons",
    # Notes
    "notes",
]


class TradeDataLogger:

    def __init__(self, instrument: str):
        self.instrument  = instrument.upper()   # "NIFTY" or "SENSEX"
        self.today       = date.today().isoformat()
        self.day_of_week = date.today().strftime("%A")

        # Build empty row
        self._row = {h: "" for h in CSV_HEADERS}
        self._row["date"]        = self.today
        self._row["instrument"]  = self.instrument
        self._row["day_of_week"] = self.day_of_week

        self._first_candle_logged = False
        self._saved               = False

        print(f"[TradeDataLogger] Initialized for {self.instrument} on {self.today}")
        print(f"[TradeDataLogger] CSV will be saved to: {LOCAL_CSV}")

    # ──────────────────────────────────────────────────────────────────────
    # 1. PRE-ENTRY
    #    Call just before wait_until_ist("09:18:56")
    #    Pass spot LTP — VIX and prev_close auto-fetched from NSE
    #    Returns (risk_signal, risk_reasons) so you can send via Telegram
    # ──────────────────────────────────────────────────────────────────────
    def log_pre_entry(self, spot: float):
        self._row["spot_at_entry"] = spot

        # Fetch VIX + prev_close from NSE in one call
        vix, prev_close = self._fetch_nse_data()

        self._row["vix_open"]   = vix        if vix        else ""
        self._row["prev_close"] = prev_close if prev_close else ""

        if prev_close and spot:
            self._row["gap_pct"] = round((spot - prev_close) / prev_close * 100, 3)

        # Compute risk signal
        score, reasons, signal = self._compute_risk(
            self._row["vix_open"],
            self._row["gap_pct"]
        )
        self._row["risk_score"]   = score
        self._row["risk_signal"]  = signal
        self._row["risk_reasons"] = " | ".join(reasons)

        print(f"[TradeDataLogger] Pre-entry → VIX={vix}, Spot={spot}, "
              f"PrevClose={prev_close}, Gap={self._row['gap_pct']}%, Risk={signal}")

        return signal, reasons  # caller sends this via Telegram

    # ──────────────────────────────────────────────────────────────────────
    # 2. ENTRY
    #    Call immediately after execute_trade_block() returns
    # ──────────────────────────────────────────────────────────────────────
    def log_entry(self, ce_entry: float, pe_entry: float, atm_strike: int,
                  ce_sl_30: float, pe_sl_30: float,
                  ce_sl_40: float, pe_sl_40: float):
        self._row["atm_strike"]       = atm_strike
        self._row["ce_premium_entry"] = ce_entry
        self._row["pe_premium_entry"] = pe_entry
        self._row["straddle_price"]   = round(ce_entry + pe_entry, 2)
        self._row["ce_sl_30_level"]   = ce_sl_30
        self._row["pe_sl_30_level"]   = pe_sl_30
        self._row["ce_sl_40_level"]   = ce_sl_40
        self._row["pe_sl_40_level"]   = pe_sl_40

        print(f"[TradeDataLogger] Entry → CE={ce_entry}, PE={pe_entry}, "
              f"Straddle={self._row['straddle_price']}, ATM={atm_strike}")

    # ──────────────────────────────────────────────────────────────────────
    # 3. FIRST CANDLE
    #    Call once inside loop when tim >= "09:25"
    #    Pass real OHLC from getCandleData (open/high/low of 9:15 candle)
    # ──────────────────────────────────────────────────────────────────────
    def log_first_candle(self, open_: float, high: float, low: float):
        if self._first_candle_logged:
            return
        self._row["first_candle_open"] = open_
        self._row["first_candle_high"] = high
        self._row["first_candle_low"]  = low
        if open_ and open_ != 0:
            self._row["first_candle_size_pct"] = round((high - low) / open_ * 100, 3)
        self._first_candle_logged = True
        print(f"[TradeDataLogger] First candle → O={open_}, H={high}, "
              f"L={low}, Size={self._row['first_candle_size_pct']}%")

    # ──────────────────────────────────────────────────────────────────────
    # 4. EOD / EARLY EXIT
    #    Call at every exit point:
    #      - Double SL early exit
    #      - 4-side SL after re-entry
    #      - Normal 14:59 exit
    # ──────────────────────────────────────────────────────────────────────
    def log_eod(self, ce_sl_hit: bool, pe_sl_hit: bool,
                ce_upgraded: bool = False, pe_upgraded: bool = False,
                notes: str = ""):
        self._row["ce_sl_hit"]               = "Y" if ce_sl_hit  else "N"
        self._row["pe_sl_hit"]               = "Y" if pe_sl_hit  else "N"
        self._row["double_sl_hit"]           = "Y" if (ce_sl_hit and pe_sl_hit) else "N"
        self._row["sl_upgrade_triggered_ce"] = "Y" if ce_upgraded else "N"
        self._row["sl_upgrade_triggered_pe"] = "Y" if pe_upgraded else "N"
        self._row["exit_time"]               = datetime.now(IST).strftime("%H:%M")
        self._row["notes"]                   = notes

        print(f"[TradeDataLogger] EOD → CE_SL={self._row['ce_sl_hit']}, "
              f"PE_SL={self._row['pe_sl_hit']}, "
              f"Double={self._row['double_sl_hit']}, "
              f"Exit={self._row['exit_time']}")

    # ──────────────────────────────────────────────────────────────────────
    # 5. SAVE
    #    Call in your finally block — runs even on crash
    # ──────────────────────────────────────────────────────────────────────
    def save(self):
        if self._saved:
            return
        try:
            self._write_csv()
            print(f"[TradeDataLogger] ✅ Saved to: {LOCAL_CSV}")
        except Exception as e:
            print(f"[TradeDataLogger] ❌ Save failed: {e}")
        self._saved = True

    # ──────────────────────────────────────────────────────────────────────
    # INTERNAL HELPERS
    # ──────────────────────────────────────────────────────────────────────

    def _fetch_nse_data(self):
        """Single NSE allIndices call → returns (vix, prev_close)."""
        try:
            session = requests.Session()
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept":     "application/json",
                "Referer":    "https://www.nseindia.com"
            }
            session.get("https://www.nseindia.com", headers=headers, timeout=8)
            resp = session.get(
                "https://www.nseindia.com/api/allIndices",
                headers=headers, timeout=8
            )
            resp.raise_for_status()

            vix        = None
            prev_close = None

            for item in resp.json().get("data", []):
                idx = item.get("index", "")
                if idx == "INDIA VIX":
                    vix = float(item["last"])
                if idx == "NIFTY 50":
                    # Works for both NIFTY and SENSEX as market benchmark
                    prev_close = float(item["previousClose"])

            return vix, prev_close

        except Exception as e:
            print(f"[TradeDataLogger] NSE fetch failed: {e}")
            return None, None

    def _compute_risk(self, vix, gap_pct):
        """Returns (score, reasons_list, signal_string)."""
        score   = 0
        reasons = []

        try:
            v = float(vix)
            if v > 17:
                score += 3
                reasons.append(f"🔴 VIX very high: {v}")
            elif v > 13:
                score += 1
                reasons.append(f"🟡 VIX elevated: {v}")
            else:
                reasons.append(f"🟢 VIX normal: {v}")
        except:
            reasons.append("⚪ VIX unavailable")

        try:
            g = abs(float(gap_pct))
            if g > 0.8:
                score += 3
                reasons.append(f"🔴 Large gap: {gap_pct}%")
            elif g > 0.3:
                score += 1
                reasons.append(f"🟡 Moderate gap: {gap_pct}%")
            else:
                reasons.append(f"🟢 Small gap: {gap_pct}%")
        except:
            reasons.append("⚪ Gap unavailable")

        signal = "HIGH" if score >= 5 else "MEDIUM" if score >= 2 else "LOW"
        return score, reasons, signal

    def _write_csv(self):
        """
        Append today's row to the CSV.
        If same date+instrument already exists (re-run on same day),
        replace it instead of duplicating.
        """
        rows     = []
        existed  = False

        # Read existing rows if file exists
        if os.path.exists(LOCAL_CSV):
            with open(LOCAL_CSV, "r", newline="") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    if r.get("date") == self.today and r.get("instrument") == self.instrument:
                        existed = True
                        rows.append(self._row)   # replace with latest
                    else:
                        rows.append(r)

        if not existed:
            rows.append(self._row)

        # Write all rows back
        with open(LOCAL_CSV, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
            writer.writeheader()
            writer.writerows(rows)

        action = "Updated" if existed else "Appended"
        print(f"[TradeDataLogger] {action} row for {self.instrument} on {self.today}")
