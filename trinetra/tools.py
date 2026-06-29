"""LangChain tools exposed to the agents.

These are the only surface the LLMs touch. Each tool is a thin, well-documented
wrapper over the broker + market-data layers and always returns a JSON string so
the model gets structured, unambiguous results.

Risky tools (`place_order`, `cancel_order`) are listed in RISKY_TOOLS and gated
by the Human-in-the-Loop middleware in agents.py.
"""

from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import tool

from trinetra.broker import get_broker
from trinetra.broker.base import BrokerError, OrderRequest
from trinetra.config import settings
from trinetra.logging_setup import get_logger
from trinetra import instruments, market_data, render

log = get_logger(__name__)


def _json(obj: Any) -> str:
    return json.dumps(obj, indent=2, default=str)


# --------------------------------------------------------------------------- #
# Research tools
# --------------------------------------------------------------------------- #
@tool("lookup_stocks")
def lookup_stocks(company_name: str) -> str:
    """Resolve a company name to its tradable stock symbol on NSE/BSE.

    Use this first whenever the user names a company (e.g. "Reliance", "TCS NSE",
    "Infosys BSE") so later tools get a precise Groww trading symbol. Returns the
    trading_symbol, exchange and resolved company name.
    """
    return _json(market_data.lookup_symbol(company_name))


@tool("get_live_quote")
def get_live_quote(symbol: str) -> str:
    """Get the real-time market quote for a stock (Groww live feed when connected,
    else yfinance). Returns last price, day change, day high/low, open, previous
    close, volume and 52-week range. Use this to know the current price before
    advising on or placing an order. `symbol` may be "RELIANCE", "RELIANCE.NS" or
    "TCS".
    """
    return _json(market_data.get_live_quote(symbol))


@tool("fetch_stock_data")
def fetch_stock_data(symbol: str) -> str:
    """Fetch a combined snapshot for a stock: live price/day-change plus
    fundamentals (company name, sector, market cap, P/E, 52-week high/low).
    Use for "tell me about X" / research questions. Merges the Groww live quote
    with yfinance fundamentals.
    """
    quote = market_data.get_live_quote(symbol)
    fundamentals = market_data.fetch_fundamentals(symbol)
    return _json({**fundamentals, **{k: v for k, v in quote.items() if v is not None}})


@tool("analyze_stock_sentiment")
def analyze_stock_sentiment(symbol: str) -> str:
    """Run technical + news-sentiment analysis on a stock and return a BUY/SELL/HOLD
    signal. Computes RSI-14, MACD, Bollinger %B and ATR from 90 days of history,
    scores recent headlines, and derives a composite score with ATR-based
    stop-loss and targets. Use when the user asks "should I buy X?" or "what's the
    outlook for X?".
    """
    return _json(market_data.technical_snapshot(symbol))


# --------------------------------------------------------------------------- #
# Trading tools
# --------------------------------------------------------------------------- #
@tool("place_order")
def place_order(
    symbol: str,
    action: str,
    quantity: int,
    order_type: str = "market",
    price: float = 0.0,
    trigger_price: float = 0.0,
    product: str = "",
    exchange: str = "",
) -> str:
    """Place a buy or sell equity order through the connected broker.

    Parameters:
    - symbol: stock trading symbol (e.g. "RELIANCE", "TCS"). ".NS"/".BO" suffixes are accepted.
    - action: "buy" or "sell".
    - quantity: number of shares (whole number, > 0). For budget-based orders,
      compute floor(budget / price) yourself and pass that here.
    - order_type: "market" (fill at current price), "limit" (needs price),
      "sl" (stop-loss limit: needs price + trigger_price), or
      "sl_m" (stop-loss market: needs trigger_price).
    - price: limit price per share — required for limit and sl orders.
    - trigger_price: trigger price — required for sl and sl_m (stop-loss) orders.
    - product: "CNC" (delivery) or "MIS" (intraday). Defaults to the configured product.
    - exchange: "NSE" or "BSE". Defaults to the configured exchange.

    In PAPER mode the fill is simulated and logged; in LIVE mode it is sent to the
    real Groww account (and gated by human approval first). Stop-loss orders are
    LIVE-only. Returns the order result as JSON.
    """
    try:
        # Resolve the symbol against the Groww instrument master FIRST so a wrong
        # guess (e.g. "INFOSYS") can never reach the broker — it becomes "INFY".
        rec = instruments.resolve(symbol, exchange or None)
        if rec is None:
            suggestions = [m.to_dict() for m in instruments.search(symbol, limit=3)]
            return _json({
                "status": "rejected",
                "error": f"Could not find a tradable Groww symbol for {symbol!r}. "
                         f"Use lookup_stocks to find the correct symbol.",
                "suggestions": suggestions,
            })
        if not rec.buy_allowed and action.strip().lower() == "buy":
            return _json({"status": "rejected",
                          "error": f"{rec.trading_symbol} is not buy-enabled on Groww."})

        broker = get_broker()
        req = OrderRequest(
            trading_symbol=rec.trading_symbol,
            transaction_type=action,
            quantity=quantity,
            order_type=order_type or "market",
            price=price or 0.0,
            trigger_price=(trigger_price or None),
            product=(product or settings.default_product),
            exchange=rec.exchange,
        )
        # Market/SL-market orders need a live reference price for the value cap
        # + paper fill.
        reference_price = None
        if (order_type or "market").lower() in ("market", "sl_m"):
            reference_price = market_data.try_ltp(rec.trading_symbol)
        result = broker.place_order(req, reference_price=reference_price)
        payload = result.to_dict()
        payload["trading_mode"] = settings.trading_mode.value
        payload["resolved_name"] = rec.name
        if rec.trading_symbol != symbol.strip().upper().replace(".NS", "").replace(".BO", ""):
            payload["note"] = f"Resolved '{symbol}' → {rec.trading_symbol} ({rec.name})."
        return _json(payload)
    except BrokerError as exc:
        return _json({"status": "rejected", "error": str(exc)})
    except Exception as exc:  # noqa: BLE001
        log.exception("place_order failed")
        return _json({"status": "failed", "error": str(exc)})


@tool("modify_order")
def modify_order(
    order_id: str,
    quantity: int = 0,
    price: float = 0.0,
    trigger_price: float = 0.0,
    segment: str = "CASH",
) -> str:
    """Modify a pending (not-yet-filled) LIVE order: change its quantity, limit
    price, or trigger price. Pass only the fields you want to change (leave others
    at 0). Returns the result as JSON. Not applicable in paper mode (orders fill
    instantly).
    """
    try:
        return _json(
            get_broker().modify_order(
                order_id,
                quantity=quantity or None,
                price=price or None,
                trigger_price=trigger_price or None,
                segment=segment,
            )
        )
    except BrokerError as exc:
        return _json({"status": "error", "error": str(exc)})


@tool("get_order_history")
def get_order_history(limit: int = 20) -> str:
    """Show recent orders (the order book): symbol, side, quantity, price, type and
    status. Use when the user asks "what did I trade today?", "show my orders", or
    "order history". Returns a ready-to-display markdown table.
    """
    try:
        broker = get_broker()
        orders = broker.get_order_history(limit=limit)
        return _json({"mode": broker.mode, "count": len(orders),
                      "display": render.render_orders(orders, broker.mode),
                      "orders": orders})
    except BrokerError as exc:
        return _json({"error": str(exc)})


@tool("cancel_order")
def cancel_order(order_id: str, segment: str = "CASH") -> str:
    """Cancel a previously placed (pending) order by its broker order id.
    Only meaningful in LIVE mode for orders that have not yet filled. Returns the
    cancellation result as JSON.
    """
    try:
        return _json(get_broker().cancel_order(order_id, segment=segment))
    except BrokerError as exc:
        return _json({"status": "error", "error": str(exc)})


@tool("get_order_status")
def get_order_status(order_id: str, segment: str = "CASH") -> str:
    """Look up the current status of an order by its broker order id (e.g. to check
    if a live order filled). Returns the status payload as JSON.
    """
    try:
        return _json(get_broker().get_order_status(order_id, segment=segment))
    except BrokerError as exc:
        return _json({"status": "error", "error": str(exc)})


@tool("view_portfolio")
def view_portfolio() -> str:
    """View the current portfolio: holdings (symbol, quantity, average price, live
    price, P&L) and open positions. Reads real data from Groww in LIVE mode, or the
    simulated portfolio in PAPER mode. Call this whenever the user asks to see their
    portfolio, holdings, or P&L — do not rely on conversation history.
    """
    try:
        broker = get_broker()
        holdings = [h.to_dict() for h in broker.get_holdings()]
        positions = [p.to_dict() for p in broker.get_positions()]
        funds = broker.get_funds().to_dict()
        total_pnl = round(sum(h.get("pnl", 0) or 0 for h in holdings), 2)
        total_value = round(sum(h.get("current_value", 0) or 0 for h in holdings), 2)
        total_invested = round(sum(h.get("invested", 0) or 0 for h in holdings), 2)
        payload = {
            "mode": broker.mode,
            "holdings": holdings,
            "positions": positions,
            "funds": funds,
            "summary": {
                "total_invested": total_invested,
                "current_value": total_value,
                "total_pnl": total_pnl,
                "holdings_count": len(holdings),
            },
        }
        # Pre-rendered table — the agent is told to show this verbatim.
        payload["display"] = render.render_portfolio(payload)
        return _json(payload)
    except BrokerError as exc:
        return _json({"error": str(exc)})


@tool("get_funds")
def get_funds() -> str:
    """Get available trading funds / buying power. In LIVE mode this returns the
    real Groww margin (available cash, margin used); in PAPER mode it returns the
    simulated cash balance. Use before placing an order to confirm affordability.
    """
    try:
        return _json(get_broker().get_funds().to_dict())
    except BrokerError as exc:
        return _json({"error": str(exc)})


# Tools whose execution must be approved by a human before running.
RISKY_TOOLS = {"place_order", "cancel_order", "modify_order"}

RESEARCH_TOOLS = [lookup_stocks, get_live_quote, fetch_stock_data]
SENTIMENT_TOOLS = [analyze_stock_sentiment]
TRADING_TOOLS = [
    place_order,
    cancel_order,
    modify_order,
    get_order_status,
    get_order_history,
    view_portfolio,
    get_funds,
]
