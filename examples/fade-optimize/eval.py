#!/usr/bin/env python3
"""
Backtest evaluator for fade trading strategy.

Replays resolved fade signals, applies filters from strategy.py,
simulates trades with realistic costs, and calculates PnL.

Output: SCORE: <total_pnl>
"""
import importlib.util
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "fade_trades.db"

SLIPPAGE_BPS = 100       # 1% slippage (less than copy — we're not chasing a whale)
TAKER_FEE_BPS = 150      # 1.5% taker fee


def load_strategy():
    spec = importlib.util.spec_from_file_location("strategy", Path(__file__).parent / "strategy.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    s = load_strategy()
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row

    # Load all resolved signals ordered by time
    signals = db.execute("""
        SELECT ts, condition_id, category, fade_side, fade_mid_at_signal,
               loser_score, loser_size, signal_strength, herding_count,
               tilt_count, resolved_winner
        FROM fade_signals
        WHERE resolved_winner IS NOT NULL
          AND fade_mid_at_signal IS NOT NULL
          AND fade_mid_at_signal > 0
          AND fade_mid_at_signal < 1
        ORDER BY ts
    """).fetchall()

    # Strategy params
    min_strength = getattr(s, "MIN_SIGNAL_STRENGTH", 1)
    min_herding = getattr(s, "MIN_HERDING", 1)
    min_tilt = getattr(s, "MIN_TILT", 0)
    max_loser_score = getattr(s, "MAX_LOSER_SCORE", 0)
    min_fade_price = getattr(s, "MIN_FADE_PRICE", 0.01)
    max_fade_price = getattr(s, "MAX_FADE_PRICE", 0.99)
    min_loser_size = getattr(s, "MIN_LOSER_SIZE", 0.0)
    allowed_cats = getattr(s, "ALLOWED_CATEGORIES", None)
    excluded_cats = getattr(s, "EXCLUDED_CATEGORIES", None)
    position_usd = min(getattr(s, "POSITION_USD", 5.0), 50.0)
    max_daily_trades = min(getattr(s, "MAX_DAILY_TRADES", 100), 200)
    max_daily_spend = min(getattr(s, "MAX_DAILY_SPEND", 500.0), 1000.0)
    slippage_bps = getattr(s, "SLIPPAGE_BPS", SLIPPAGE_BPS)
    taker_fee_bps = getattr(s, "TAKER_FEE_BPS", TAKER_FEE_BPS)

    # Simulation
    total_pnl = 0.0
    total_fees = 0.0
    total_trades = 0
    wins = 0
    losses = 0
    daily_trades = defaultdict(int)
    daily_spend = defaultdict(float)
    seen_markets = set()  # dedup: one trade per condition_id

    for sig in signals:
        fade_price = sig["fade_mid_at_signal"]
        strength = sig["signal_strength"]
        herding = sig["herding_count"]
        tilt = sig["tilt_count"]
        score = sig["loser_score"]
        loser_size = sig["loser_size"] or 0
        category = (sig["category"] or "").strip().lower()
        fade_side = sig["fade_side"]
        winner = sig["resolved_winner"]
        cid = sig["condition_id"]
        ts = sig["ts"]

        # Filters
        if strength < min_strength:
            continue
        if herding < min_herding:
            continue
        if tilt < min_tilt:
            continue
        if score > max_loser_score:
            continue
        if loser_size < min_loser_size:
            continue

        # Price filter
        if fade_price < min_fade_price or fade_price > max_fade_price:
            continue

        # Category filter
        if allowed_cats is not None and category not in [c.lower() for c in allowed_cats]:
            continue
        if excluded_cats is not None and category in [c.lower() for c in excluded_cats]:
            continue

        # Dedup — one trade per market
        if cid in seen_markets:
            continue

        # Daily limits
        day = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
        if daily_trades[day] >= max_daily_trades:
            continue
        if daily_spend[day] >= max_daily_spend:
            continue

        # Apply slippage
        slippage = fade_price * (slippage_bps / 10000)
        entry_price = min(fade_price + slippage, 0.99)

        if entry_price > max_fade_price:
            continue

        # Execute trade
        fee = position_usd * (taker_fee_bps / 10000)
        cost_after_fee = position_usd - fee
        shares = cost_after_fee / entry_price

        won = fade_side.strip().lower() == winner.strip().lower()
        if won:
            pnl = (1.0 - entry_price) * shares - fee
            wins += 1
        else:
            pnl = -position_usd  # lose entire stake + fee already deducted
            losses += 1

        total_pnl += pnl
        total_fees += fee
        total_trades += 1
        daily_trades[day] += 1
        daily_spend[day] += position_usd
        seen_markets.add(cid)

    # Report
    wr = wins / total_trades * 100 if total_trades else 0
    print(f"Trades: {total_trades} | Wins: {wins} | Losses: {losses} | WR: {wr:.1f}%", file=sys.stderr)
    print(f"Net PnL: ${total_pnl:+.2f} | Fees: ${total_fees:.2f}", file=sys.stderr)
    print(f"SCORE: {total_pnl:.4f}")


if __name__ == "__main__":
    main()
