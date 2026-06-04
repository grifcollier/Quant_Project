"""Google Sheets trade journal for daily paper trading runs."""

import json
import os
from datetime import datetime

HEADERS = [
    "Date", "Time (ET)", "ETF", "Z-Score", "Signal",
    "Orders Placed", "Mode", "Error",
]


def _get_sheet():
    import gspread
    from google.oauth2.service_account import Credentials

    creds_json = os.environ.get("GOOGLE_SHEETS_CREDS")
    sheet_id   = os.environ.get("GOOGLE_SHEET_ID")

    if not creds_json:
        raise ValueError("GOOGLE_SHEETS_CREDS env var not set.")
    if not sheet_id:
        raise ValueError("GOOGLE_SHEET_ID env var not set.")

    creds_dict = json.loads(creds_json)
    scopes     = ["https://www.googleapis.com/auth/spreadsheets"]
    creds      = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    gc         = gspread.authorize(creds)
    return gc.open_by_key(sheet_id).sheet1


def _ensure_header(sheet) -> None:
    existing = sheet.get_all_values()
    if not existing or existing[0] != HEADERS:
        sheet.insert_row(HEADERS, index=1, value_input_option="RAW")


def log_trade(result: dict, mode: str) -> None:
    """
    Append one row to the Google Sheet for a single basket run.

    Parameters
    ----------
    result : dict returned by run_basket() in daily_trade.py
             Keys: etf, signal, z_score, n_orders, error
    mode   : "EXECUTE" or "DRY-RUN"
    """
    sheet = _get_sheet()
    _ensure_header(sheet)

    now = datetime.now()
    row = [
        now.strftime("%Y-%m-%d"),
        now.strftime("%H:%M"),
        result["etf"],
        round(result["z_score"], 4) if result["z_score"] is not None else "",
        result["signal"],
        result["n_orders"] if mode == "EXECUTE" else "",
        mode,
        "YES" if result["error"] else "",
    ]
    sheet.append_row(row, value_input_option="USER_ENTERED")
