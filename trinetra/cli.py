"""Interactive command-line interface with the Human-in-the-Loop approval gate.

Run via `python main.py`. Shows a clear PAPER/LIVE banner, and in LIVE mode
requires an explicit confirmation before the session starts so real-money
trading is never entered by accident.
"""

from __future__ import annotations

import uuid

from langchain_core.messages import HumanMessage
from langgraph.errors import GraphRecursionError
from langgraph.types import Command

from trinetra.config import AuthMethod, settings
from trinetra.logging_setup import get_logger

log = get_logger(__name__)

# Headroom so the occasional extra supervisor->worker hop doesn't crash a turn.
RECURSION_LIMIT = 40


def _invoke(supervisor, payload, config):
    """Invoke the graph, recovering gracefully if the supervisor over-loops.

    The supervisor can occasionally route back to a worker one extra time before
    terminating. Those extra hops generate text only (the order/tool already ran
    exactly once and is HITL-gated), so on a recursion limit we simply read the
    latest state and return it rather than failing the turn."""
    try:
        return supervisor.invoke(payload, config=config)
    except GraphRecursionError:
        log.warning("Supervisor hit the step limit; recovering the latest result.")
        snapshot = supervisor.get_state(config)
        return {"messages": snapshot.values.get("messages", []), "__interrupt__": []}


def _show_final(result) -> None:
    """Print the agent's answer.

    The supervisor sometimes hands back an EMPTY final message (the specialist
    already produced the answer), so we show the last message that actually has
    text content — which is the specialist's clean, pre-rendered output.
    """
    messages = result.get("messages", [])
    for m in reversed(messages):
        content = m.content if isinstance(m.content, str) else ""
        if content.strip():
            print("\n" + content.strip() + "\n")
            return
    if messages:  # nothing had text; fall back so the user isn't left blank
        messages[-1].pretty_print()


def _banner() -> None:
    mode = settings.trading_mode.value.upper()
    line = "=" * 64
    print(line)
    print("  🔱  TRINETRA CAPITAL AI  —  Multi-Agent Trading (Groww)")
    print(line)
    if settings.is_live:
        print(f"  MODE: \033[91mLIVE\033[0m  — orders hit your REAL Groww account.")
    else:
        print(f"  MODE: \033[92mPAPER\033[0m — orders are simulated (no real money).")

    if settings.groww_configured:
        method = "TOTP" if settings.auth_method is AuthMethod.TOTP else "API key + secret"
        print(f"  Groww: configured ({method}). Market data & portfolio are live.")
    else:
        print("  Groww: NOT connected — using yfinance data + paper portfolio.")
        print("         Run `python connect_groww.py` to connect your account.")
    print(f"  Safety cap: ₹{settings.max_order_value:,.0f} per order"
          f"  |  Default product: {settings.default_product}")
    print(line)


def _confirm_live() -> bool:
    print("\n\033[91m⚠️  LIVE TRADING MODE\033[0m")
    print("Approved orders will be sent to your real Groww account with real money.")
    answer = input("Type 'I UNDERSTAND' to continue (anything else aborts): ").strip()
    return answer == "I UNDERSTAND"


def _order_summary(args: dict) -> str | None:
    """Build a human-readable order line with the resolved symbol, live price and
    estimated total so the user sees exactly what they're approving."""
    from trinetra import instruments, market_data

    raw_symbol = args.get("symbol")
    if not raw_symbol:
        return None
    side = str(args.get("action", "")).upper()
    qty = args.get("quantity")
    otype = str(args.get("order_type", "market")).lower()
    product = (args.get("product") or settings.default_product).upper()

    # Resolve to the real Groww symbol so the price lookup (and the displayed
    # ticker) are correct — this is where "INFOSYS" → "INFY" surfaces.
    rec = instruments.resolve(raw_symbol, args.get("exchange") or None)
    symbol = rec.trading_symbol if rec else raw_symbol
    resolved_note = ""
    if rec and rec.trading_symbol != str(raw_symbol).upper().replace(".NS", "").replace(".BO", ""):
        resolved_note = f"  (resolved '{raw_symbol}' → {rec.trading_symbol}, {rec.name})"

    # Determine the price the order is expected to execute around.
    if otype in ("limit", "sl") and args.get("price"):
        px, px_label = float(args["price"]), "limit"
    elif otype == "sl_m" and args.get("trigger_price"):
        px, px_label = float(args["trigger_price"]), "trigger"
    else:
        px, px_label = (market_data.try_ltp(symbol), "≈ market")

    lines = [f"  → {side} {qty} × {symbol}  ({otype.upper()}, {product}){resolved_note}"]
    if px:
        total = qty * px if isinstance(qty, (int, float)) else None
        lines.append(f"  → Price: ₹{px:,.2f} ({px_label})"
                     + (f"   Estimated total: ₹{total:,.2f}" if total else ""))
        if total and total > settings.max_order_value:
            lines.append(f"  ⚠️ Exceeds safety cap ₹{settings.max_order_value:,.0f} — will be blocked.")
    else:
        lines.append("  → Price: unavailable right now (could not fetch a live quote)")
    return "\n".join(lines)


def _print_approval(interrupts) -> None:
    for intr in interrupts:
        print("\n--- ⚠️  Approval needed ---")
        for action in intr.value.get("action_requests", []):
            name = action["name"]
            print(f"Tool: {name}")
            args = action.get("args", {})
            if name == "place_order":
                summary = _order_summary(args)
                if summary:
                    print(summary)
            if args:
                print("Parameters:")
                for k, v in args.items():
                    print(f"  - {k}: {v}")
        if settings.is_live:
            print("\033[91m>>> THIS IS A REAL ORDER ON YOUR LIVE GROWW ACCOUNT <<<\033[0m")


def run() -> None:
    _banner()
    if settings.is_live and not _confirm_live():
        print("Aborted. Set GROWW_TRADING_MODE=paper for simulated trading.")
        return

    # Warm the Groww instrument master up front so symbol resolution is instant
    # (and the one-time download doesn't stall the first query).
    from trinetra import instruments

    print("  Loading Groww instrument master (symbol resolution)…")
    if instruments.ensure_loaded():
        print("  ✓ Instruments ready.\n")
    else:
        print("  ⚠️ Instrument master unavailable — using fallback symbol matching.\n")

    # Build the agent graph lazily so import errors surface with a clear message.
    from trinetra.agents import build_supervisor

    try:
        supervisor = build_supervisor()
    except Exception as exc:  # noqa: BLE001
        print(f"\n❌ Failed to start agents: {exc}")
        return

    print("\n🤖 Ready. Ask me to research, analyse, trade, or show your portfolio.")
    print("   Type 'exit' to quit.\n")

    while True:
        try:
            command = input("yes sir! what's on your mind: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nJai Mahakal! 🔱")
            break

        if command.lower() in ("exit", "quit"):
            print("Jai Mahakal! 🔱")
            break
        if not command:
            continue

        config = {
            "configurable": {"thread_id": str(uuid.uuid4())},
            "recursion_limit": RECURSION_LIMIT,
        }

        try:
            result = _invoke(supervisor, {"messages": [HumanMessage(content=command)]}, config)
        except Exception as exc:  # noqa: BLE001
            print(f"❌ Error: {exc}")
            continue

        interrupts = result.get("__interrupt__", [])
        _print_approval(interrupts)

        if interrupts:
            choice = input("\n⚠️ Approve this action? (yes/no): ").strip().lower()
            if choice in ("yes", "y"):
                decision = {"type": "approve"}
                print("✅ Approved. Executing…")
            else:
                decision = {"type": "reject"}
                print("❌ Rejected.")
            try:
                response = _invoke(supervisor, Command(resume={"decisions": [decision]}), config)
                _show_final(response)
            except Exception as exc:  # noqa: BLE001
                print(f"❌ Error completing action: {exc}")
        else:
            _show_final(result)


if __name__ == "__main__":
    run()
