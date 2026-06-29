"""Simulated broker (paper trading).

Fills are instant and logged to portfolio.json (backward compatible with the
original flat trade-log format). Holdings, positions and a virtual cash balance
are derived by aggregating that log, and enriched with live LTP from the market
data layer so paper P&L still tracks the real market.

This is the default broker so users can exercise the full agent system safely
before flipping GROWW_TRADING_MODE=live.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from typing import Any

from trinetra.config import settings
from trinetra.broker.base import (
    Broker,
    BrokerError,
    Funds,
    Holding,
    OrderRequest,
    OrderResult,
    Position,
)
from trinetra.logging_setup import get_logger
from trinetra.symbols import normalize

log = get_logger(__name__)


class PaperBroker(Broker):
    name = "paper"
    mode = "paper"

    # ------------------------------------------------------------------ #
    # trade-log persistence
    # ------------------------------------------------------------------ #
    def _load(self) -> list[dict[str, Any]]:
        path = settings.portfolio_file
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text())
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("Could not read %s: %s", path, exc)
            return []

    def _save(self, trades: list[dict[str, Any]]) -> None:
        settings.portfolio_file.write_text(json.dumps(trades, indent=2))

    # ------------------------------------------------------------------ #
    # orders
    # ------------------------------------------------------------------ #
    def place_order(self, req: OrderRequest, reference_price: float | None = None) -> OrderResult:
        req = req.normalised()

        # Paper mode has no live feed to watch a stop trigger, so be honest.
        if req.order_type in ("SL", "SL_M"):
            raise BrokerError(
                "Stop-loss (SL/SL_M) orders aren't simulated in paper mode (there is no "
                "live trigger monitoring). Switch to live mode, or use a market/limit order."
            )

        # A market order needs a fill price; a limit order fills at its limit.
        fill_price = req.price if (req.order_type == "LIMIT" and req.price) else reference_price
        if not fill_price or fill_price <= 0:
            raise BrokerError(
                "Paper market order needs a reference price. Have the research agent "
                "fetch a live quote first, or place a LIMIT order with an explicit price."
            )

        self.guard_order(req, fill_price)

        total = round(req.quantity * fill_price, 2)
        order_id = f"PAPER-{req.reference_id}"
        trades = self._load()
        trades.append(
            {
                "timestamp": datetime.now().isoformat(),
                "symbol": req.trading_symbol,
                "exchange": req.exchange,
                "action": req.transaction_type.lower(),
                "product": req.product,
                "currency": "INR",
                "shares": req.quantity,
                "price": round(fill_price, 2),
                "total": total,
                "order_id": order_id,
                "reference_id": req.reference_id,
                "mode": "paper",
            }
        )
        self._save(trades)
        log.info(
            "PAPER fill → %s %s x%d @ ₹%.2f (₹%.2f)",
            req.transaction_type, req.trading_symbol, req.quantity, fill_price, total,
        )

        return OrderResult(
            status="filled",
            transaction_type=req.transaction_type,
            trading_symbol=req.trading_symbol,
            quantity=req.quantity,
            order_type=req.order_type,
            product=req.product,
            mode=self.mode,
            order_id=order_id,
            price=round(fill_price, 2),
            average_price=round(fill_price, 2),
            estimated_value=total,
            reference_id=req.reference_id,
            exchange=req.exchange,
            message="Simulated fill (paper trading).",
        )

    def cancel_order(self, order_id: str, segment: str = "CASH") -> dict[str, Any]:
        # Paper orders fill instantly, so there is nothing pending to cancel.
        return {
            "order_id": order_id,
            "status": "not_cancellable",
            "message": "Paper orders fill immediately; nothing to cancel.",
        }

    def modify_order(
        self,
        order_id: str,
        quantity: int | None = None,
        price: float | None = None,
        trigger_price: float | None = None,
        order_type: str | None = None,
        segment: str = "CASH",
    ) -> dict[str, Any]:
        return {
            "order_id": order_id,
            "status": "not_modifiable",
            "message": "Paper orders fill immediately; nothing to modify. "
                       "Place a new order instead.",
        }

    def get_order_status(self, order_id: str, segment: str = "CASH") -> dict[str, Any]:
        for t in self._load():
            if t.get("order_id") == order_id:
                return {"order_id": order_id, "status": "filled", **t}
        return {"order_id": order_id, "status": "unknown"}

    def get_order_history(self, limit: int = 20, segment: str = "CASH") -> list[dict[str, Any]]:
        # Most-recent first.
        trades = self._load()
        return list(reversed(trades))[:limit]

    # ------------------------------------------------------------------ #
    # portfolio (derived from the trade log)
    # ------------------------------------------------------------------ #
    def _aggregate(self) -> dict[str, dict[str, float]]:
        """symbol -> {qty, buy_qty, buy_cost} aggregation across all trades."""
        agg: dict[str, dict[str, float]] = defaultdict(
            lambda: {"qty": 0.0, "buy_qty": 0.0, "buy_cost": 0.0}
        )
        for t in self._load():
            sym = t.get("symbol")
            if not sym:
                continue
            key = normalize(sym).trading_symbol
            shares = float(t.get("shares", 0) or 0)
            price = float(t.get("price", 0) or 0)
            action = str(t.get("action", "")).lower()
            row = agg[key]
            if action == "buy":
                row["qty"] += shares
                row["buy_qty"] += shares
                row["buy_cost"] += shares * price
            elif action == "sell":
                row["qty"] -= shares
        return agg

    def get_holdings(self) -> list[Holding]:
        from trinetra import market_data  # lazy to avoid import cycle

        agg = self._aggregate()
        held = [sym for sym, row in agg.items() if int(row["qty"]) > 0]
        prices = market_data.ltp_many(held) if held else {}

        holdings: list[Holding] = []
        for sym, row in agg.items():
            qty = int(row["qty"])
            if qty <= 0:
                continue
            avg = round(row["buy_cost"] / row["buy_qty"], 2) if row["buy_qty"] else 0.0
            last = prices.get(sym)
            invested = round(qty * avg, 2)
            cur = round(qty * last, 2) if last else None
            pnl = round(cur - invested, 2) if cur is not None else None
            pnl_pct = round((pnl / invested) * 100, 2) if (pnl is not None and invested) else None
            holdings.append(
                Holding(
                    trading_symbol=sym,
                    quantity=qty,
                    average_price=avg,
                    last_price=last,
                    invested=invested,
                    current_value=cur,
                    pnl=pnl,
                    pnl_pct=pnl_pct,
                )
            )
        return holdings

    def get_positions(self, segment: str | None = None) -> list[Position]:
        # Paper trading models everything as holdings; no intraday position book.
        return [
            Position(
                trading_symbol=h.trading_symbol,
                quantity=h.quantity,
                product="CNC",
                segment="CASH",
                average_price=h.average_price,
                last_price=h.last_price,
                unrealised_pnl=h.pnl,
            )
            for h in self.get_holdings()
        ]

    def get_funds(self) -> Funds:
        agg = self._aggregate()
        net_invested = 0.0
        for t in self._load():
            action = str(t.get("action", "")).lower()
            total = float(t.get("total", 0) or 0)
            if action == "buy":
                net_invested += total
            elif action == "sell":
                net_invested -= total
        available = settings.paper_starting_cash - net_invested
        return Funds(
            available_cash=round(available, 2),
            margin_used=round(net_invested, 2),
            net=round(settings.paper_starting_cash, 2),
            mode=self.mode,
            detail={"starting_cash": settings.paper_starting_cash},
        )
