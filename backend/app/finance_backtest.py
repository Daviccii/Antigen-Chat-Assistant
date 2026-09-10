"""Backtesting: simulates a strategy against historical price data and
reports how it would have performed. This is retrospective analysis,
not prediction — a strategy that backtested well has no guarantee of
future performance, and every result here should be read that way.

Only two starter strategies for now (moving-average crossover and RSI
mean-reversion) — enough to be genuinely useful, not an attempt to
cover every strategy family in one pass.
"""
import logging
from typing import Optional

import pandas as pd

from . import finance_indicators as indicators

logger = logging.getLogger(__name__)


class BacktestError(Exception):
    pass


def _compute_trade_stats(df: pd.DataFrame, position_col: str = "position") -> dict:
    """Shared trade/return/drawdown accounting once a strategy has
    populated a `position` column (1 = long, 0 = flat) on df.
    """
    df = df.copy()
    df["daily_return"] = df["Close"].pct_change()
    # Position is decided on day N's close, applied to day N+1's return —
    # avoids lookahead bias (can't trade on information not yet known).
    df["strategy_return"] = df[position_col].shift(1).fillna(0) * df["daily_return"]

    df["cumulative_return"] = (1 + df["strategy_return"]).cumprod() - 1
    df["buy_hold_return"] = (1 + df["daily_return"]).cumprod() - 1

    running_max = (1 + df["strategy_return"]).cumprod().cummax()
    drawdown = (1 + df["strategy_return"]).cumprod() / running_max - 1
    max_drawdown = float(drawdown.min()) if not drawdown.empty else 0.0

    position_changes = df[position_col].diff().fillna(0)
    num_trades = int((position_changes != 0).sum())

    winning_days = int((df["strategy_return"] > 0).sum())
    losing_days = int((df["strategy_return"] < 0).sum())
    total_active_days = winning_days + losing_days
    win_rate = round(winning_days / total_active_days * 100, 2) if total_active_days else None

    return {
        "total_return_pct": round(float(df["cumulative_return"].iloc[-1]) * 100, 2) if len(df) else 0.0,
        "buy_hold_return_pct": round(float(df["buy_hold_return"].iloc[-1]) * 100, 2) if len(df) else 0.0,
        "max_drawdown_pct": round(max_drawdown * 100, 2),
        "num_trades": num_trades,
        "win_rate_pct": win_rate,
        "days_simulated": len(df),
    }


def sma_crossover(df: pd.DataFrame, fast_window: int = 20, slow_window: int = 50) -> dict:
    """Long when the fast SMA is above the slow SMA, flat otherwise."""
    if len(df) < slow_window + 1:
        raise BacktestError(f"Not enough historical data ({len(df)} rows) for a {slow_window}-period slow SMA.")

    work = df.copy()
    work["fast"] = indicators.sma(work["Close"], fast_window)
    work["slow"] = indicators.sma(work["Close"], slow_window)
    work["position"] = (work["fast"] > work["slow"]).astype(int)
    work = work.dropna(subset=["fast", "slow"])

    stats = _compute_trade_stats(work)
    stats["strategy"] = "sma_crossover"
    stats["params"] = {"fast_window": fast_window, "slow_window": slow_window}
    return stats


def rsi_mean_reversion(df: pd.DataFrame, rsi_window: int = 14, oversold: float = 30, overbought: float = 70) -> dict:
    """Long when RSI drops below `oversold` (bet on a bounce), flat once
    it climbs back above `overbought`, flat by default otherwise.
    """
    if len(df) < rsi_window + 1:
        raise BacktestError(f"Not enough historical data ({len(df)} rows) for a {rsi_window}-period RSI.")

    work = df.copy()
    work["rsi"] = indicators.rsi(work["Close"], rsi_window)

    position = []
    holding = False
    for value in work["rsi"]:
        if not holding and value < oversold:
            holding = True
        elif holding and value > overbought:
            holding = False
        position.append(1 if holding else 0)
    work["position"] = position
    work = work.dropna(subset=["rsi"])

    stats = _compute_trade_stats(work)
    stats["strategy"] = "rsi_mean_reversion"
    stats["params"] = {"rsi_window": rsi_window, "oversold": oversold, "overbought": overbought}
    return stats


STRATEGY_REGISTRY = {
    "sma_crossover": sma_crossover,
    "rsi_mean_reversion": rsi_mean_reversion,
}


def run_backtest(strategy: str, df: pd.DataFrame, **params) -> dict:
    fn = STRATEGY_REGISTRY.get(strategy)
    if not fn:
        raise BacktestError(f"Unknown strategy '{strategy}'. Available: {', '.join(STRATEGY_REGISTRY)}")
    result = fn(df, **params)
    result["disclaimer"] = (
        "Historical simulation only. Past performance does not predict future results. "
        "Not financial advice."
    )
    return result