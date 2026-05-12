"""Strategy-agnostic backtest engine: trade log → equity curve."""

import pandas as pd


def run_backtest(trades: pd.DataFrame, starting_capital: float) -> pd.DataFrame:
    """
    Build a daily equity curve from a completed trade log.

    Parameters
    ----------
    trades : DataFrame with at minimum columns ['entry_date', 'exit_date', 'pnl'].
    starting_capital : Portfolio value at the start of the backtest.

    Returns
    -------
    DataFrame with columns ['equity'], indexed by date (daily, trading days only).
    Equity is flat between trades and steps on each exit date.
    """
    if trades.empty:
        return pd.DataFrame({"equity": [starting_capital]},
                            index=pd.DatetimeIndex([pd.Timestamp.today().normalize()],
                                                   name="date"))

    # Sum P&L on each exit date (multiple trades can close on the same day)
    pnl_by_date = trades.groupby("exit_date")["pnl"].sum()

    # Build a date range spanning entry to exit
    all_dates = pd.date_range(
        start=trades["entry_date"].min(),
        end=trades["exit_date"].max(),
        freq="B",  # business days
    )

    pnl_series = pnl_by_date.reindex(all_dates, fill_value=0.0)
    equity = starting_capital + pnl_series.cumsum()
    equity.index.name = "date"

    return equity.to_frame("equity")
