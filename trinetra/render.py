"""Deterministic, human-readable renderers.

Formatting the portfolio in Python (not in the LLM) guarantees a clean, stable
table every time and removes a slow, unreliable formatting round-trip. The
agent is instructed to relay the `display` string verbatim.
"""

from __future__ import annotations

from typing import Any


def _money(x: Any) -> str:
    if x is None:
        return "—"
    try:
        return f"₹{float(x):,.2f}"
    except (TypeError, ValueError):
        return "—"


def _num(x: Any) -> str:
    if x is None:
        return "—"
    try:
        return f"{float(x):,.2f}"
    except (TypeError, ValueError):
        return "—"


def _signed_money(x: Any) -> str:
    if x is None:
        return "—"
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "—"
    return f"{'+' if v >= 0 else '−'}₹{abs(v):,.2f}"


def _signed_pct(x: Any) -> str:
    if x is None:
        return "—"
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "—"
    return f"{'+' if v >= 0 else '−'}{abs(v):,.2f}%"


def render_portfolio(data: dict[str, Any]) -> str:
    """Render the structured view_portfolio payload into a markdown report."""
    mode = data.get("mode", "paper")
    holdings = data.get("holdings", [])
    summary = data.get("summary", {})

    mode_label = "PAPER (simulated)" if mode == "paper" else "LIVE (real Groww account)"
    lines = [f"**Portfolio — {mode_label}**", ""]

    if not holdings:
        lines.append("_No holdings yet._")
        funds = data.get("funds")
        if funds:
            lines.append(f"\nAvailable cash: {_money(funds.get('available_cash'))}")
        return "\n".join(lines)

    lines.append("| # | Symbol | Qty | Avg | LTP | Invested | Value | P&L | P&L % |")
    lines.append("|--:|:-------|----:|----:|----:|---------:|------:|----:|------:|")
    for i, h in enumerate(holdings, 1):
        lines.append(
            f"| {i} | **{h.get('trading_symbol','?')}** "
            f"| {h.get('quantity','—')} "
            f"| {_num(h.get('average_price'))} "
            f"| {_num(h.get('last_price'))} "
            f"| {_money(h.get('invested'))} "
            f"| {_money(h.get('current_value'))} "
            f"| {_signed_money(h.get('pnl'))} "
            f"| {_signed_pct(h.get('pnl_pct'))} |"
        )

    total_pnl = summary.get("total_pnl")
    arrow = "▲" if (total_pnl or 0) >= 0 else "▼"
    lines += [
        "",
        f"**Invested:** {_money(summary.get('total_invested'))}  •  "
        f"**Value:** {_money(summary.get('current_value'))}  •  "
        f"**Total P&L:** {arrow} {_signed_money(total_pnl)}  •  "
        f"**Holdings:** {summary.get('holdings_count', len(holdings))}",
    ]

    unpriced = [h.get("trading_symbol") for h in holdings if h.get("last_price") is None]
    if unpriced:
        lines.append(
            f"\n_Note: live price unavailable for {', '.join(unpriced)} "
            f"(symbol may be delisted/non-NSE); its P&L is excluded._"
        )
    return "\n".join(lines)


def render_orders(orders: list[dict[str, Any]], mode: str = "paper") -> str:
    """Render an order history / book list into a markdown table."""
    if not orders:
        return "_No orders found._"

    lines = ["| When | Symbol | Side | Qty | Price | Type | Status |",
             "|:-----|:-------|:----:|----:|------:|:-----|:-------|"]
    for o in orders:
        when = (o.get("timestamp") or o.get("created_at") or o.get("order_time") or "—")
        if isinstance(when, str) and "T" in when:
            when = when.split(".")[0].replace("T", " ")
        sym = o.get("symbol") or o.get("trading_symbol") or "—"
        side = (o.get("action") or o.get("transaction_type") or "—")
        qty = o.get("shares") or o.get("quantity") or "—"
        price = o.get("price") or o.get("average_price") or "—"
        otype = o.get("order_type") or o.get("type") or "—"
        status = o.get("status") or o.get("order_status") or "filled"
        lines.append(
            f"| {when} | **{sym}** | {str(side).upper()} | {qty} "
            f"| {_num(price)} | {otype} | {status} |"
        )
    return "\n".join(lines)
