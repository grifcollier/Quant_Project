"""SQLite trade journal for daily paper trading runs."""

import os
import sqlite3
from datetime import datetime
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DB_PATH   = Path(os.environ.get("DB_PATH") or _REPO_ROOT / "trades.db")

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS trade_signals (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    date          TEXT    NOT NULL,
    time_et       TEXT    NOT NULL,
    etf           TEXT    NOT NULL,
    z_score       REAL,
    signal        TEXT    NOT NULL,
    orders_placed INTEGER,
    mode          TEXT    NOT NULL,
    error         INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    created_at    TEXT    NOT NULL
)
"""


def log_trade(result: dict, mode: str) -> None:
    """
    Append one row to the local SQLite trade log.

    Parameters
    ----------
    result : dict returned by run_basket() in daily_trade.py
             Keys: etf, signal, z_score, n_orders, error
    mode   : "EXECUTE" or "DRY-RUN"
    """
    conn = sqlite3.connect(_DB_PATH)
    try:
        conn.execute(_CREATE_TABLE)
        now = datetime.now()
        conn.execute(
            """INSERT INTO trade_signals
               (date, time_et, etf, z_score, signal, orders_placed, mode, error, error_message, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                now.strftime("%Y-%m-%d"),
                now.strftime("%H:%M"),
                result["etf"],
                result["z_score"],
                result["signal"],
                result["n_orders"] if mode == "EXECUTE" else None,
                mode,
                1 if result["error"] else 0,
                str(result["error"]) if result["error"] else None,
                now.isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()
