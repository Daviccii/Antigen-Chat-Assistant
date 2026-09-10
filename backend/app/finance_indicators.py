"""Technical indicators computed over a pandas OHLCV DataFrame. Pure
functions, no I/O — finance_data.py fetches the data, these just do
math on it. Implemented directly in pandas rather than pulling in
TA-Lib, which needs a compiled system library and is overkill for a
handful of standard indicators.
"""
import pandas as pd


def sma(close: pd.Series, window: int = 20) -> pd.Series:
    """Simple moving average."""
    return close.rolling(window=window).mean()


def ema(close: pd.Series, window: int = 20) -> pd.Series:
    """Exponential moving average."""
    return close.ewm(span=window, adjust=False).mean()


def rsi(close: pd.Series, window: int = 14) -> pd.Series:
    """Relative Strength Index, Wilder's smoothing method."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, float("nan"))
    result = 100 - (100 / (1 + rs))
    return result.fillna(100)  # avg_loss of 0 means pure gains -> RSI 100


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """MACD line, signal line, and histogram."""
    ema_fast = ema(close, fast)
    ema_slow = ema(close, slow)
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return pd.DataFrame({"macd": macd_line, "signal": signal_line, "histogram": histogram})


def bollinger_bands(close: pd.Series, window: int = 20, num_std: float = 2.0) -> pd.DataFrame:
    """Middle (SMA), upper, and lower bands."""
    middle = sma(close, window)
    std = close.rolling(window=window).std()
    upper = middle + num_std * std
    lower = middle - num_std * std
    return pd.DataFrame({"middle": middle, "upper": upper, "lower": lower})


INDICATOR_REGISTRY = {
    "sma": lambda df, **kw: sma(df["Close"], **kw),
    "ema": lambda df, **kw: ema(df["Close"], **kw),
    "rsi": lambda df, **kw: rsi(df["Close"], **kw),
    "macd": lambda df, **kw: macd(df["Close"], **kw),
    "bollinger_bands": lambda df, **kw: bollinger_bands(df["Close"], **kw),
}


def calculate(name: str, df: pd.DataFrame, **kwargs):
    """Dispatch by indicator name. Raises ValueError for an unknown name
    rather than silently returning nothing.
    """
    fn = INDICATOR_REGISTRY.get(name.lower())
    if not fn:
        raise ValueError(f"Unknown indicator '{name}'. Available: {', '.join(INDICATOR_REGISTRY)}")
    return fn(df, **kwargs)