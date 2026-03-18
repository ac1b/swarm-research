#!/usr/bin/env python3
"""
Backtest evaluator for copy trading strategy.

Uses whale_deep.db — full historical fills from orderFilled.csv (37GB dump).
175K fills across 5 whales, 2810 markets, 2739 resolved.

Simulates: we see a whale BUY, we copy at whale_price + slippage, pay fee, hold to resolution.
Only counts buy fills (copy = follow their buys).

Output: SCORE: <total_pnl>
"""
import importlib.util
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "whale_deep.db"

SLIPPAGE_BPS = 200       # 2% slippage — whale moved price, we buy after
TAKER_FEE_BPS = 150      # 1.5% taker fee on CLOB


def load_strategy():
    spec = importlib.util.spec_from_file_location("strategy", Path(__file__).parent / "strategy.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def guess_category(question):
    q = (question or "").lower()
    sports = ["win", "nba", "nfl", "nhl", "mlb", "epl", "ucl", "premier",
              "champions", "fifa", "match", "game", "score", "finals",
              "fc ", "united", "arsenal", "lakers", "celtic",
              "o/u ", "over/under", "spread"]
    crypto = ["bitcoin", "btc", "ethereum", "eth", "solana", "sol",
              "xrp", "up or down", "crypto", "token", "price"]
    politics = ["trump", "biden", "election", "president", "senate",
                "congress", "governor", "democrat", "republican", "vote",
                "minister", "party", "political"]
    weather = ["temperature", "weather", "rain", "snow", "degrees",
               "°f", "°c", "highest temp", "lowest temp"]
    for kw in sports:
        if kw in q:
            return "sports"
    for kw in crypto:
        if kw in q:
            return "crypto"
    for kw in politics:
        if kw in q:
            return "politics"
    for kw in weather:
        if kw in q:
            return "weather"
    return "other"


def main():
    s = load_strategy()
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row

    # Load market resolutions
    resolutions = {}
    questions = {}
    for r in db.execute("SELECT condition_id, question, winner FROM markets WHERE winner IS NOT NULL"):
        resolutions[r["condition_id"]] = r["winner"]
        questions[r["condition_id"]] = r["question"]

    # Strategy params
    enabled_whales = [w for w, on in s.WHALES.items() if on]
    if not enabled_whales:
        print("SCORE: 0.0")
        return

    min_price = getattr(s, "MIN_PRICE", 0.05)
    max_price = getattr(s, "MAX_PRICE", 0.95)
    position_usd = min(getattr(s, "POSITION_USD", 5.0), 50.0)
    max_open = min(getattr(s, "MAX_OPEN_POSITIONS", 10), 50)
    max_daily = min(getattr(s, "MAX_DAILY_SPEND", 25.0), 500.0)
    max_exposure = min(getattr(s, "MAX_EXPOSURE", 50.0), 1000.0)
    skip_dup = getattr(s, "SKIP_DUPLICATE_MARKET", True)
    min_whale_size = getattr(s, "MIN_WHALE_SIZE_USD", 50.0)
    max_copies_per_whale = getattr(s, "MAX_COPIES_PER_WHALE_PER_DAY", 20)
    whale_categories = getattr(s, "WHALE_CATEGORIES", {})
    slippage_bps = getattr(s, "SLIPPAGE_BPS", SLIPPAGE_BPS)
    taker_fee_bps = getattr(s, "TAKER_FEE_BPS", TAKER_FEE_BPS)

    # Load buy fills for enabled whales, sorted by time
    placeholders = ",".join("?" * len(enabled_whales))
    fills = db.execute(f"""
        SELECT whale, condition_id, question, outcome, role,
               amount_filled, counter_amount, price, timestamp
        FROM fills
        WHERE whale IN ({placeholders})
          AND role LIKE '%buy%'
          AND condition_id IS NOT NULL
          AND outcome IS NOT NULL
          AND price > 0 AND price < 1
        ORDER BY timestamp
    """, enabled_whales).fetchall()

    # Simulation state
    open_positions = {}
    daily_spend = defaultdict(float)
    daily_copies = defaultdict(lambda: defaultdict(int))
    total_pnl = 0.0
    total_trades = 0
    total_fees = 0.0
    wins = 0
    losses = 0

    for f in fills:
        whale = f["whale"]
        cid = f["condition_id"]
        outcome = f["outcome"]
        whale_price = f["price"]
        question = f["question"] or questions.get(cid, "")
        whale_usd = f["counter_amount"] or 0
        ts = f["timestamp"]

        # Skip unresolved
        if cid not in resolutions:
            continue

        # Category filter
        cat = guess_category(question)
        allowed_cats = whale_categories.get(whale)
        if allowed_cats is not None and cat not in allowed_cats:
            continue

        # Price filter
        if whale_price < min_price or whale_price > max_price:
            continue

        # Min whale size
        if whale_usd < min_whale_size:
            continue

        day = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")

        # Daily spend limit
        if daily_spend[day] >= max_daily:
            continue

        # Per-whale daily limit
        if daily_copies[day][whale] >= max_copies_per_whale:
            continue

        # Duplicate market
        if skip_dup and cid in open_positions:
            continue

        # Max open positions — close resolved ones first
        if len(open_positions) >= max_open:
            to_close = [k for k in open_positions if k in resolutions]
            for k in to_close:
                pos = open_positions.pop(k)
                winner = resolutions[k]
                won = pos["outcome"].strip().lower() == winner.strip().lower()
                exit_price = 1.0 if won else 0.0
                pnl = (exit_price - pos["entry_price"]) * pos["shares"] - pos["fee"]
                total_pnl += pnl
                total_fees += pos["fee"]
                total_trades += 1
                if won:
                    wins += 1
                else:
                    losses += 1
            if len(open_positions) >= max_open:
                continue

        # Max exposure
        current_exposure = sum(p["cost"] for p in open_positions.values())
        if current_exposure >= max_exposure:
            continue

        # Slippage
        slippage = whale_price * (slippage_bps / 10000)
        entry_price = min(whale_price + slippage, 0.99)

        if entry_price > max_price:
            continue

        # Fee and shares
        fee = position_usd * (taker_fee_bps / 10000)
        cost_after_fee = position_usd - fee
        shares = cost_after_fee / entry_price

        open_positions[cid] = {
            "outcome": outcome,
            "entry_price": entry_price,
            "shares": shares,
            "cost": position_usd,
            "fee": fee,
            "opened_ts": ts,
        }
        daily_spend[day] += position_usd
        daily_copies[day][whale] += 1

    # Close remaining
    for cid, pos in open_positions.items():
        if cid in resolutions:
            winner = resolutions[cid]
            won = pos["outcome"].strip().lower() == winner.strip().lower()
            exit_price = 1.0 if won else 0.0
            pnl = (exit_price - pos["entry_price"]) * pos["shares"] - pos["fee"]
            total_pnl += pnl
            total_fees += pos["fee"]
            total_trades += 1
            if won:
                wins += 1
            else:
                losses += 1

    # Report
    wr = wins / total_trades * 100 if total_trades else 0
    gross = total_pnl + total_fees
    print(f"Trades: {total_trades} | Wins: {wins} | Losses: {losses} | WR: {wr:.1f}%", file=sys.stderr)
    print(f"Gross PnL: ${gross:+.2f} | Fees: ${total_fees:.2f} | Net PnL: ${total_pnl:+.2f}", file=sys.stderr)
    print(f"Slippage: {slippage_bps}bps | Fee: {taker_fee_bps}bps", file=sys.stderr)
    print(f"SCORE: {total_pnl:.4f}")


if __name__ == "__main__":
    main()
