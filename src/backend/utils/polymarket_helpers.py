"""
Shared Polymarket calculation helpers.

Extracted from routes/markets.py and routes/debate.py to eliminate code
duplication. Both endpoints previously maintained their own copies of these
functions, which drifted out of sync.

All functions are pure (no I/O) and safe to unit-test in isolation.
"""

from __future__ import annotations


def parse_float(value: object) -> float:
    """Safe float coercion — returns 0.0 on any failure."""
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


def extract_position_value(position: dict) -> float:
    """
    Extract the current USD value from a Polymarket position dict.

    The Data API returns this field under several different key names
    depending on whether the position is open or closed and which
    endpoint returned it.
    """
    for key in (
        "currentValue",
        "current_value",
        "value",
        "positionValue",
        "position_value",
        "markValue",
        "mark_value",
        "notionalValue",
        "notional_value",
        "totalValue",
        "total_value",
    ):
        raw = position.get(key)
        if raw is None:
            continue
        parsed = parse_float(raw)
        if parsed > 0:
            return parsed

    # Last-resort: initialValue + cashPnl
    initial_val = parse_float(position.get("initialValue") or 0)
    cash_pnl = parse_float(position.get("cashPnl") or 0)
    fallback = initial_val + cash_pnl
    return fallback if fallback > 0 else 0.0


def extract_position_pnl(position: dict) -> float:
    """Extract realised + unrealised PnL from an open position dict."""
    for key in (
        "totalPnl",
        "total_pnl",
        "profitLoss",
        "profit_loss",
        "pnl",
        "profit",
        "cashPnl",
    ):
        raw = position.get(key)
        if raw is None:
            continue
        return parse_float(raw)

    realized = parse_float(position.get("realizedPnl") or position.get("realized_pnl") or 0)
    unrealized = parse_float(position.get("unrealizedPnl") or position.get("unrealized_pnl") or 0)
    if realized or unrealized:
        return realized + unrealized

    return 0.0


def extract_closed_position_pnl(position: dict) -> float:
    """Extract realised PnL from a closed position dict."""
    for key in ("realizedPnl", "realized_pnl", "cashPnl", "cash_pnl", "pnl"):
        raw = position.get(key)
        if raw is None:
            continue
        return parse_float(raw)
    return 0.0


def compute_global_stats(
    positions: list[dict],
    closed_positions: list[dict] | None = None,
) -> tuple[float, float, float]:
    """
    Compute (global_pnl, global_roi_pct, total_balance) across open + closed positions.

    Returns a 3-tuple of floats. All values default to 0.0 on empty inputs.
    """
    global_pnl = 0.0
    total_cost_basis = 0.0
    total_balance = 0.0

    for position in positions:
        if not isinstance(position, dict):
            continue
        global_pnl += extract_position_pnl(position)

        initial_val = parse_float(position.get("initialValue") or 0)
        if initial_val > 0:
            total_cost_basis += initial_val

        total_balance += extract_position_value(position)

    if closed_positions:
        for position in closed_positions:
            if not isinstance(position, dict):
                continue
            global_pnl += extract_closed_position_pnl(position)

            total_bought = parse_float(position.get("totalBought") or 0)
            if total_bought > 0:
                total_cost_basis += total_bought

    if total_balance <= 0 and total_cost_basis > 0:
        total_balance = max(0.0, total_cost_basis + global_pnl)

    global_roi = (global_pnl / total_cost_basis * 100) if total_cost_basis > 0 else 0.0
    return global_pnl, global_roi, total_balance


def parse_trade_value(trade: dict, size: float, price: float) -> float:
    """
    Extract USD notional from a trade dict, falling back to size × price.

    Tries several field names used across Polymarket's Data API before
    computing a fallback.
    """
    for key in (
        "value",
        "tradeValue",
        "totalValue",
        "total_value",
        "usdValue",
        "usd_value",
        "notional",
    ):
        raw = trade.get(key)
        if raw is None:
            continue
        try:
            return float(raw)
        except (TypeError, ValueError):
            continue
    return size * price
