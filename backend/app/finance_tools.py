"""Finance domain tools: market data, indicators, backtesting. All
READ_ONLY — nothing here touches real money or places any order. Follows
the same registration pattern as capability_tools.py's existing tools
(module-level Tool() + tool_registry.register() at import time).

Price alerts are deliberately NOT tools here — creating one needs a db
session and the current user, and Tool.execution_handler's signature
(input_data dict -> dict, nothing else) has no way to receive either.
Rather than bolt on a mismatched pattern, alerts are plain REST endpoints
in finance_routes.py that call security_gateway.check_permission()
directly — same gate, just not through the generic tool path.
"""
import logging
from typing import Dict, Any

from .capability_system import Tool, ToolInputSchema, ToolOutputSchema, PermissionLevel, tool_registry
from . import finance_data
from . import finance_indicators
from . import finance_backtest

logger = logging.getLogger(__name__)


def get_stock_quote_handler(input_data: Dict[str, Any]) -> Dict[str, Any]:
    symbol = input_data.get("symbol")
    if not symbol:
        return {"error": "symbol is required"}
    try:
        return finance_data.get_quote(symbol)
    except finance_data.MarketDataError as e:
        return {"error": str(e)}
    except Exception as e:
        logger.exception(f"Error fetching quote for {symbol}")
        return {"error": f"Could not fetch quote: {e}"}


def get_historical_prices_handler(input_data: Dict[str, Any]) -> Dict[str, Any]:
    symbol = input_data.get("symbol")
    if not symbol:
        return {"error": "symbol is required"}
    period = input_data.get("period", "6mo")
    interval = input_data.get("interval", "1d")
    try:
        df = finance_data.get_historical(symbol, period, interval)
        return finance_data.historical_to_summary(symbol, df)
    except finance_data.MarketDataError as e:
        return {"error": str(e)}
    except Exception as e:
        logger.exception(f"Error fetching history for {symbol}")
        return {"error": f"Could not fetch historical data: {e}"}


def calculate_indicator_handler(input_data: Dict[str, Any]) -> Dict[str, Any]:
    symbol = input_data.get("symbol")
    indicator_name = input_data.get("indicator")
    if not symbol or not indicator_name:
        return {"error": "symbol and indicator are required"}

    period = input_data.get("period", "6mo")
    interval = input_data.get("interval", "1d")
    extra = {k: v for k, v in input_data.items() if k not in ("symbol", "indicator", "period", "interval")}

    try:
        df = finance_data.get_historical(symbol, period, interval)
        result = finance_indicators.calculate(indicator_name, df, **extra)
        tail = result.tail(30)
        values = tail.reset_index().to_dict(orient="records")
        return {"symbol": symbol.upper(), "indicator": indicator_name, "params": extra, "recent_values": values}
    except (finance_data.MarketDataError, ValueError) as e:
        return {"error": str(e)}
    except Exception as e:
        logger.exception(f"Error calculating {indicator_name} for {symbol}")
        return {"error": f"Could not calculate indicator: {e}"}


def run_backtest_handler(input_data: Dict[str, Any]) -> Dict[str, Any]:
    symbol = input_data.get("symbol")
    strategy = input_data.get("strategy")
    if not symbol or not strategy:
        return {"error": "symbol and strategy are required"}

    period = input_data.get("period", "2y")
    interval = input_data.get("interval", "1d")
    extra = {k: v for k, v in input_data.items() if k not in ("symbol", "strategy", "period", "interval")}

    try:
        df = finance_data.get_historical(symbol, period, interval)
        result = finance_backtest.run_backtest(strategy, df, **extra)
        result["symbol"] = symbol.upper()
        return result
    except (finance_data.MarketDataError, finance_backtest.BacktestError) as e:
        return {"error": str(e)}
    except Exception as e:
        logger.exception(f"Error backtesting {strategy} on {symbol}")
        return {"error": f"Backtest failed: {e}"}


get_stock_quote_tool = Tool(
    name="get_stock_quote",
    description="Get the current/most recent price for a stock or ETF symbol (data may lag real-time by up to ~15 min)",
    input_schema={
        "symbol": ToolInputSchema(type="string", description="Ticker symbol, e.g. 'AAPL'", required=True),
    },
    output_schema=ToolOutputSchema(type="object", description="Current price, previous close, day high/low"),
    permission_level=PermissionLevel.READ_ONLY,
    domain="finance",
    category="market_data",
    execution_handler=get_stock_quote_handler,
)

get_historical_prices_tool = Tool(
    name="get_historical_prices",
    description="Get historical OHLCV price data and summary stats for a symbol over a period",
    input_schema={
        "symbol": ToolInputSchema(type="string", description="Ticker symbol", required=True),
        "period": ToolInputSchema(type="string", description="1d/5d/1mo/3mo/6mo/1y/2y/5y/10y/ytd/max", required=False, default="6mo"),
        "interval": ToolInputSchema(type="string", description="1m/5m/15m/30m/1h/1d/1wk/1mo", required=False, default="1d"),
    },
    output_schema=ToolOutputSchema(type="object", description="Summary stats plus a recent-rows preview, not the full series"),
    permission_level=PermissionLevel.READ_ONLY,
    domain="finance",
    category="market_data",
    execution_handler=get_historical_prices_handler,
)

calculate_indicator_tool = Tool(
    name="calculate_indicator",
    description="Calculate a technical indicator (sma, ema, rsi, macd, bollinger_bands) for a symbol",
    input_schema={
        "symbol": ToolInputSchema(type="string", description="Ticker symbol", required=True),
        "indicator": ToolInputSchema(type="string", description="sma | ema | rsi | macd | bollinger_bands", required=True),
        "period": ToolInputSchema(type="string", description="Historical period to compute over", required=False, default="6mo"),
        "window": ToolInputSchema(type="integer", description="Indicator window/lookback, where applicable", required=False),
    },
    output_schema=ToolOutputSchema(type="object", description="Recent indicator values"),
    permission_level=PermissionLevel.READ_ONLY,
    domain="finance",
    category="analysis",
    execution_handler=calculate_indicator_handler,
)

run_backtest_tool = Tool(
    name="run_backtest",
    description=(
        "Simulate a trading strategy (sma_crossover, rsi_mean_reversion) against historical data. "
        "This is retrospective analysis, not a prediction — a good backtest does not guarantee future results."
    ),
    input_schema={
        "symbol": ToolInputSchema(type="string", description="Ticker symbol", required=True),
        "strategy": ToolInputSchema(type="string", description="sma_crossover | rsi_mean_reversion", required=True),
        "period": ToolInputSchema(type="string", description="Historical period to backtest over", required=False, default="2y"),
    },
    output_schema=ToolOutputSchema(type="object", description="Return, drawdown, trade count, win rate vs. buy-and-hold"),
    permission_level=PermissionLevel.READ_ONLY,
    domain="finance",
    category="analysis",
    execution_handler=run_backtest_handler,
)

tool_registry.register(get_stock_quote_tool)
tool_registry.register(get_historical_prices_tool)
tool_registry.register(calculate_indicator_tool)
tool_registry.register(run_backtest_tool)