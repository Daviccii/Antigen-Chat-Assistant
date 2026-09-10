"""Market data access. yfinance pulls from Yahoo Finance's public
endpoints — free, no API key, but not a licensed real-time feed: quotes
can lag by up to ~15 minutes and it's meant for research/personal use,
not production trading infrastructure. Fine for analysis and
backtesting; say so if the user asks about latency-sensitive use.
"""
import logging
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

VALID_PERIODS = {"1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"}
VALID_INTERVALS = {"1m", "5m", "15m", "30m", "1h", "1d", "1wk", "1mo"}


class MarketDataError(Exception):
    pass


def get_quote(symbol: str) -> dict:
    """Current/most recent price snapshot for a symbol."""
    import yfinance as yf

    ticker = yf.Ticker(symbol.upper())
    info = ticker.fast_info  # lighter-weight than .info, no full company profile fetch

    try:
        price = info.last_price
    except Exception:
        raise MarketDataError(f"Could not fetch a quote for '{symbol}' — check the symbol is valid.")

    return {
        "symbol": symbol.upper(),
        "price": round(float(price), 4) if price is not None else None,
        "previous_close": round(float(info.previous_close), 4) if getattr(info, "previous_close", None) else None,
        "day_high": round(float(info.day_high), 4) if getattr(info, "day_high", None) else None,
        "day_low": round(float(info.day_low), 4) if getattr(info, "day_low", None) else None,
        "currency": getattr(info, "currency", None),
        "note": "Data from Yahoo Finance — may lag real-time by up to ~15 minutes. Not a licensed trading feed.",
    }


def get_historical(symbol: str, period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
    """OHLCV history for a symbol. Raises MarketDataError on a bad
    symbol/empty result rather than returning an empty DataFrame silently.
    """
    if period not in VALID_PERIODS:
        raise MarketDataError(f"Invalid period '{period}'. Valid: {', '.join(sorted(VALID_PERIODS))}")
    if interval not in VALID_INTERVALS:
        raise MarketDataError(f"Invalid interval '{interval}'. Valid: {', '.join(sorted(VALID_INTERVALS))}")

    import yfinance as yf

    df = yf.Ticker(symbol.upper()).history(period=period, interval=interval)
    if df.empty:
        raise MarketDataError(f"No historical data found for '{symbol}' — check the symbol is valid.")

    return df


def historical_to_summary(symbol: str, df: pd.DataFrame, max_rows: int = 30) -> dict:
    """Condenses an OHLCV DataFrame into something safe to hand an LLM —
    full-resolution intraday history for a year would blow the context
    window, so this gives shape (start/end/high/low/change) plus a
    tail preview, not the whole series.
    """
    close = df["Close"]
    return {
        "symbol": symbol.upper(),
        "rows": len(df),
        "start_date": str(df.index[0].date()),
        "end_date": str(df.index[-1].date()),
        "start_price": round(float(close.iloc[0]), 4),
        "end_price": round(float(close.iloc[-1]), 4),
        "period_change_pct": round(((close.iloc[-1] / close.iloc[0]) - 1) * 100, 2),
        "period_high": round(float(df["High"].max()), 4),
        "period_low": round(float(df["Low"].min()), 4),
        "recent_rows": df.tail(max_rows).reset_index().to_dict(orient="records"),
    }