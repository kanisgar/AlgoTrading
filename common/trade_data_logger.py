"""
trade_data_logger.py
====================
Drop this in: /home/ec2-user/AlgoTrading/common/trade_data_logger.py

- Saves to CSV immediately after every log_* call
- Has its own log file: common/trade_data_logger_YYYY-MM-DD.log
- No dependency on nifty/sensex scripts whatsoever

Call sequence:
    1. logger = TradeDataLogger(instrument="NIFTY")
    2. logger.log_pre_entry(spot)                    <- before wait_until_ist
    3. logger.log_entry(ce, pe, atm, sl30s, sl40s)  <- after execute_trade_block
    4. logger.log_first_candle(open, high, low)      <- inside loop at 9:25
    5. logger.log_sl_upgrade("CE" or "PE")           <- when ce_updated / pe_updated flips
    6. logger.log_sl_hit("CE" or "PE")               <- when SL order is actually executed
    7. logger.log_eod(ce_hit, pe_hit, notes)         <- at every exit point
    8. logger.save()                                 <- in finally block
"""

import os
import csv
import logging
import requests
from datetime import datetime, date
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

# All files live in the same folder as this module
_HERE     = os.path.dirname(os.path.abspath(__file__))
LOCAL_CSV = os.path.join(_HERE, "options_trade_log.csv")

CSV_HEADERS = [
    # Identity
    "date", "instrument", "day_of_week",

    # Pre-entry context — Phase 1 features
    "vix_open",
    "spot_at_entry",
    "prev_close",
    "gap_pct",
    "risk_signal",
    "risk_score",

    # Entry details — Phase 1 features
    "atm_strike",
    "ce_premium_entry",
    "pe_premium_entry",
    "straddle_price",
    "ce_sl_30_level",
    "pe_sl_30_level",
    "ce_sl_40_level",
    "pe_sl_40_level",

    # First 5-min candle — Phase 2 features
    "first_candle_open",
    "first_candle_high",
    "first_candle_low",
    "first_candle_size_pct",

    # CE SL upgrade: premium crossed +20% — Phase 3 features
    "ce_upgrade_time",
    "ce_upgrade_mins_from_entry",

    # PE SL upgrade: premium crossed +20% — Phase 3 features
    "pe_upgrade_time",
    "pe_upgrade_mins_from_entry",

    # Upgrade relationship — Phase 3 features
    "which_side_upgraded_first",
    "both_sides_upgraded",
    "gap_between_upgrades_mins",

    # CE SL actually hit — Phase 3 features
    "ce_sl_hit_time",
    "ce_sl_hit_mins_from_entry",

    # PE SL actually hit — Phase 3 features
    "pe_sl_hit_time",
    "pe_sl_hit_mins_from_entry",

    # SL hit relationship — Phase 3 features
    "which_side_sl_hit_first",
    "gap_between_sl_hits_mins",

    # EOD outcome — ML labels
    "ce_sl_hit",
    "pe_sl_hit",
    "double_sl_hit",

    # Exit
    "exit_time",

    # Notes
    "notes",
]

ENTRY_HOUR   = 9
ENTRY_MINUTE = 19


def _build_logger() -> logging.Logger:
    """
    Creates a dedicated file logger for TradeDataLogger.
    Log file: /home/ec2-user/AlgoTrading/job_logs/trade_data_logger_YYYY-MM-DD.txt

    _HERE  = .../AlgoTrading/common/
    parent = .../AlgoTrading/
    log_dir= .../AlgoTrading/job_logs/
    """
    log_dir = os.path.join(os.path.dirname(_HERE), "job_logs")
    os.makedirs(log_dir, exist_ok=True)

    log_filename = os.path.join(
        log_dir,
        f"trade_data_logger_{date.today().isoformat()}.txt"
    )
    logger = logging.getLogger("TradeDataLogger")

    # Avoid adding duplicate handlers if module is re-imported
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.FileHandler(log_filename, mode="a", encoding="utf-8")
        handler.setFormatter(logging.Formatter(
            fmt="%(asctime)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))
        logger.addHandler(handler)

    return logger


# Module-level logger — one instance shared across all TradeDataLogger objects
_logger = _build_logger()


class TradeDataLogger:

    def __init__(self, instrument: str):
        self.instrument  = instrument.upper()
        self.today       = date.today().isoformat()
        self.day_of_week = date.today().strftime("%A")

        self._row = {h: "" for h in CSV_HEADERS}
        self._row["date"]                      = self.today
        self._row["instrument"]                = self.instrument
        self._row["day_of_week"]               = self.day_of_week
        self._row["which_side_upgraded_first"] = "None"
        self._row["both_sides_upgraded"]       = "N"
        self._row["which_side_sl_hit_first"]   = "None"

        # Internal timestamps for gap calculations
        self._ce_upgrade_dt = None
        self._pe_upgrade_dt = None
        self._ce_sl_hit_dt  = None
        self._pe_sl_hit_dt  = None

        self._first_candle_logged = False
        self._saved               = False

        _logger.info(f"Initialized → {self.instrument} | {self.today}")
        _logger.info(f"CSV path    → {LOCAL_CSV}")

    # ──────────────────────────────────────────────────────────────────────
    # 1. PRE-ENTRY
    #    Call just before wait_until_ist("09:18:56")
    #    Auto-fetches VIX + prev_close from NSE
    #    Returns risk_signal string — send via Telegram from calling script
    # ──────────────────────────────────────────────────────────────────────
    def log_pre_entry(self, spot: float):
        self._row["spot_at_entry"] = spot

        vix, prev_close = self._fetch_nse_data()
        self._row["vix_open"]   = vix        if vix        else ""
        self._row["prev_close"] = prev_close if prev_close else ""

        if prev_close and spot:
            self._row["gap_pct"] = round((spot - prev_close) / prev_close * 100, 3)

        score, signal = self._compute_risk(self._row["vix_open"], self._row["gap_pct"])
        self._row["risk_score"]  = score
        self._row["risk_signal"] = signal

        _logger.info(
            f"PRE-ENTRY | VIX={vix} | Spot={spot} | "
            f"PrevClose={prev_close} | Gap={self._row['gap_pct']}% | "
            f"Risk={signal} (score={score})"
        )
        self._write_csv()
        return signal

    # ──────────────────────────────────────────────────────────────────────
    # 2. ENTRY
    #    Call right after execute_trade_block() returns
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

        _logger.info(
            f"ENTRY | ATM={atm_strike} | "
            f"CE={ce_entry} SL30={ce_sl_30} SL40={ce_sl_40} | "
            f"PE={pe_entry} SL30={pe_sl_30} SL40={pe_sl_40} | "
            f"Straddle={self._row['straddle_price']}"
        )
        self._write_csv()

    # ──────────────────────────────────────────────────────────────────────
    # 3. FIRST CANDLE
    #    Call once inside loop when tim >= "09:25"
    #    Pass real OHLC from getCandleData
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

        _logger.info(
            f"FIRST CANDLE | O={open_} H={high} L={low} | "
            f"Size={self._row['first_candle_size_pct']}%"
        )
        self._write_csv()

    # ──────────────────────────────────────────────────────────────────────
    # 4. SL UPGRADE
    #    Call right after ce_updated = True / pe_updated = True in your loop
    #    Captures: exact time, mins from entry, which side first, gap between upgrades
    # ──────────────────────────────────────────────────────────────────────
    def log_sl_upgrade(self, side: str):
        side    = side.upper()
        now     = datetime.now(IST)
        now_str = now.strftime("%H:%M")
        mins    = self._mins_from_entry(now)

        if side == "CE":
            self._ce_upgrade_dt                     = now
            self._row["ce_upgrade_time"]            = now_str
            self._row["ce_upgrade_mins_from_entry"] = mins
            if self._pe_upgrade_dt is None:
                self._row["which_side_upgraded_first"] = "CE"

        elif side == "PE":
            self._pe_upgrade_dt                     = now
            self._row["pe_upgrade_time"]            = now_str
            self._row["pe_upgrade_mins_from_entry"] = mins
            if self._ce_upgrade_dt is None:
                self._row["which_side_upgraded_first"] = "PE"

        if self._ce_upgrade_dt and self._pe_upgrade_dt:
            self._row["both_sides_upgraded"]       = "Y"
            gap = abs(int(
                (self._ce_upgrade_dt - self._pe_upgrade_dt).total_seconds() / 60
            ))
            self._row["gap_between_upgrades_mins"] = gap

        _logger.info(
            f"SL UPGRADE | Side={side} | Time={now_str} | "
            f"MinsFromEntry={mins} | "
            f"WhichFirst={self._row['which_side_upgraded_first']} | "
            f"BothUpgraded={self._row['both_sides_upgraded']} | "
            f"GapBetween={self._row['gap_between_upgrades_mins']} mins"
        )
        self._write_csv()

    # ──────────────────────────────────────────────────────────────────────
    # 5. SL HIT
    #    Call when is_order_executed() returns True for CE or PE SL order
    #    Captures: exact time, mins from entry, which side hit first, gap between hits
    # ──────────────────────────────────────────────────────────────────────
    def log_sl_hit(self, side: str):
        side    = side.upper()
        now     = datetime.now(IST)
        now_str = now.strftime("%H:%M")
        mins    = self._mins_from_entry(now)

        if side == "CE":
            self._ce_sl_hit_dt                     = now
            self._row["ce_sl_hit_time"]            = now_str
            self._row["ce_sl_hit_mins_from_entry"] = mins
            if self._pe_sl_hit_dt is None:
                self._row["which_side_sl_hit_first"] = "CE"

        elif side == "PE":
            self._pe_sl_hit_dt                     = now
            self._row["pe_sl_hit_time"]            = now_str
            self._row["pe_sl_hit_mins_from_entry"] = mins
            if self._ce_sl_hit_dt is None:
                self._row["which_side_sl_hit_first"] = "PE"

        if self._ce_sl_hit_dt and self._pe_sl_hit_dt:
            gap = abs(int(
                (self._ce_sl_hit_dt - self._pe_sl_hit_dt).total_seconds() / 60
            ))
            self._row["gap_between_sl_hits_mins"] = gap

        _logger.info(
            f"SL HIT | Side={side} | Time={now_str} | "
            f"MinsFromEntry={mins} | "
            f"WhichFirst={self._row['which_side_sl_hit_first']} | "
            f"GapBetweenHits={self._row['gap_between_sl_hits_mins']} mins"
        )
        self._write_csv()

    # ──────────────────────────────────────────────────────────────────────
    # 6. EOD / EARLY EXIT
    #    Call at every exit point:
    #    double SL early exit / 4-side SL / normal 14:59
    # ──────────────────────────────────────────────────────────────────────
    def log_eod(self, ce_sl_hit: bool, pe_sl_hit: bool, notes: str = ""):
        self._row["ce_sl_hit"]     = "Y" if ce_sl_hit              else "N"
        self._row["pe_sl_hit"]     = "Y" if pe_sl_hit              else "N"
        self._row["double_sl_hit"] = "Y" if (ce_sl_hit and pe_sl_hit) else "N"
        self._row["exit_time"]     = datetime.now(IST).strftime("%H:%M")
        self._row["notes"]         = notes

        _logger.info(
            f"EOD | CE_SL={self._row['ce_sl_hit']} | "
            f"PE_SL={self._row['pe_sl_hit']} | "
            f"DoubleSL={self._row['double_sl_hit']} | "
            f"ExitTime={self._row['exit_time']} | "
            f"Notes={notes}"
        )
        self._write_csv()

    # ──────────────────────────────────────────────────────────────────────
    # 7. SAVE — call in finally block
    #    Safety net — by this point most data is already on disk
    #    from the incremental saves above
    # ──────────────────────────────────────────────────────────────────────
    def save(self):
        if self._saved:
            return
        self._write_csv()
        self._saved = True
        _logger.info(f"FINAL SAVE complete → {LOCAL_CSV}")

    # ──────────────────────────────────────────────────────────────────────
    # INTERNAL HELPERS
    # ──────────────────────────────────────────────────────────────────────

    def _mins_from_entry(self, now: datetime) -> int:
        """Minutes elapsed from 9:19 AM IST to now."""
        entry_dt = now.replace(
            hour=ENTRY_HOUR, minute=ENTRY_MINUTE,
            second=0, microsecond=0
        )
        return max(0, int((now - entry_dt).total_seconds() / 60))

    def _fetch_nse_data(self):
        """
        Fetches VIX from NSE allIndices (always works).
        For prev_close:
          NIFTY  → NSE allIndices (NIFTY 50) — always present
          SENSEX → NSE allIndices (S&P BSE SENSEX) during market hours
                   Falls back to Yahoo Finance (^BSESN) if NSE returns None
                   because NSE drops Sensex from allIndices after market close.
        """
        vix        = None
        prev_close = None

        # ── Step 1: NSE allIndices for VIX + prev_close ──────────────────
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
            target_index = "NIFTY 50" if self.instrument == "NIFTY" else "S&P BSE SENSEX"
            for item in resp.json().get("data", []):
                idx = item.get("index", "")
                if idx == "INDIA VIX":
                    vix = float(item["last"])
                if idx == target_index:
                    prev_close = float(item["previousClose"])
            _logger.info(
                f"NSE fetch OK | Instrument={self.instrument} | "
                f"TargetIndex={target_index} | "
                f"VIX={vix} | PrevClose={prev_close}"
            )
        except Exception as e:
            _logger.error(f"NSE fetch FAILED: {e}")

        # ── Step 2: Yahoo Finance fallback for Sensex prev_close ─────────
        # NSE drops S&P BSE SENSEX from allIndices after market close.
        # Yahoo Finance always has it via ^BSESN previousClose.
        if self.instrument == "SENSEX" and prev_close is None:
            try:
                resp_y = requests.get(
                    "https://query1.finance.yahoo.com/v8/finance/chart/%5EBSESN?interval=1d&range=5d",
                    headers={"User-Agent": "Mozilla/5.0"}, timeout=8
                )
                resp_y.raise_for_status()
                result = resp_y.json().get("chart", {}).get("result", [])
                if result:
                    meta       = result[0].get("meta", {})
                    prev_close = round(float(meta.get("previousClose", 0) or
                                             meta.get("chartPreviousClose", 0)), 2)
                    if prev_close:
                        _logger.info(f"Yahoo fallback OK | Sensex PrevClose={prev_close}")
                    else:
                        _logger.warning("Yahoo fallback: previousClose is 0 or missing")
            except Exception as e:
                _logger.error(f"Yahoo fallback FAILED: {e}")

        return vix, prev_close

    def _compute_risk(self, vix, gap_pct):
        """Returns (score, signal_string)."""
        score = 0
        try:
            v = float(vix)
            if v > 17:   score += 3
            elif v > 13: score += 1
        except: pass
        try:
            g = abs(float(gap_pct))
            if g > 0.8:   score += 3
            elif g > 0.3: score += 1
        except: pass
        signal = "HIGH" if score >= 5 else "MEDIUM" if score >= 2 else "LOW"
        return score, signal

    def _write_csv(self):
        """
        Write self._row to CSV.
        First call for today+instrument → appends new row.
        Subsequent calls → replaces existing row with latest state.
        Other days' rows are never touched.
        """
        rows    = []
        existed = False
        try:
            if os.path.exists(LOCAL_CSV):
                with open(LOCAL_CSV, "r", newline="") as f:
                    reader = csv.DictReader(f)
                    for r in reader:
                        if (r.get("date")       == self.today and
                            r.get("instrument") == self.instrument):
                            existed = True
                            rows.append(self._row)   # replace with latest
                        else:
                            rows.append(r)           # keep other rows untouched

            if not existed:
                rows.append(self._row)

            with open(LOCAL_CSV, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
                writer.writeheader()
                writer.writerows(rows)

            action = "UPDATED" if existed else "APPENDED"
            _logger.info(f"CSV {action} | {self.instrument} | {self.today} | {LOCAL_CSV}")

        except Exception as e:
            _logger.error(f"CSV write FAILED: {e}")
