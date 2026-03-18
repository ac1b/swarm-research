---
target: strategy.py
eval: python3 eval.py
direction: maximize
rounds: 30
eval_runs: 1
mode: full
parallel: true
early_stop: 10
---

# Optimize Copy Trading Strategy

You are optimizing a Polymarket copy trading bot configuration.
The bot copies whale traders' buy signals on prediction markets.

## Data source

Full historical data from Polymarket's orderFilled.csv (37GB dump):
- **175,266 fills** across 5 whales
- **2,810 unique markets**, 2,739 resolved via Gamma API
- Period: Dec 2022 — Oct 2025

## Cost model

- **Slippage: 2%** — whale already moved the price, we buy AFTER them at worse price
- **Taker fee: 1.5%** — Polymarket CLOB fee on every entry
- Combined ~3.5% cost per trade. Need >55% WR to be profitable.
- **Baseline: 1364 trades, 71.8% WR, +$639 net PnL at $5/trade**

## Whale data (FULL HISTORY — use this!)

| Whale | Resolved | WR | Total PnL | ROI | Volume | Period |
|-------|----------|-----|-----------|-----|--------|--------|
| ScottyNooo | 1131 | 58.6% | +$155K | +2.0% | $8.9M | May-Oct 2025 |
| warlasfutpro | 39 | 76.9% | +$126K | +339% | $154K | Jul-Oct 2025 |
| How.Dare.You | 1539 | 74.4% | +$110K | +4.2% | $10.3M | Jan-Oct 2025 |
| -JB- | 804 | 94.8% | **-$94K** | -3.3% | $4.4M | Mar 2024-Oct 2025 |
| SpiritUMA | 1350 | 86.5% | **-$488K** | -3.1% | $23.7M | Dec 2022-Oct 2025 |

### Key insight: HIGH WR ≠ PROFITABLE
- **-JB-** has 94.8% WR but LOSES money — wins often but small, rare losses are catastrophic
- **SpiritUMA** has 86.5% WR but lost **$488K** — same pattern at larger scale
- Only ScottyNooo, warlasfutpro, How.Dare.You are genuinely profitable

### Monthly patterns (notable):
- ScottyNooo: Aug 2025 was best (+$175K), Sept/Oct negative
- How.Dare.You: Jan-Mar great (+$136K), Apr bad (-$32K), very sparse after June
- warlasfutpro: Aug was best (+$148K), only 39 total positions
- -JB-: consistently losing on big bets (Mar-Apr 2024: -$22K)
- SpiritUMA: massive swings, Feb 2023 -$204K, Jan 2024 -$283K

### Maker vs Taker:
- How.Dare.You: 97% maker (limit orders — price NOT impacted, slippage may be lower)
- -JB-: 88% maker
- ScottyNooo: 81% maker, 19% taker
- warlasfutpro: 29% maker, 71% taker (market orders — higher impact)

### Avg trade size (USD):
- SpiritUMA: $1,588 avg
- -JB-: $963 avg
- warlasfutpro: $465 avg
- How.Dare.You: $246 avg
- ScottyNooo: $230 avg

## What to optimize

1. **Whale selection** — which whales to enable (True/False)
2. **Category filters** — per-whale: None (all) or list like ["politics", "other"]
3. **Price range** — MIN_PRICE, MAX_PRICE for whale's entry price
4. **MIN_WHALE_SIZE_USD** — minimum whale trade size to copy (higher = stronger signal but fewer)
5. **Position sizing** — POSITION_USD (max 50), MAX_OPEN_POSITIONS (max 50)
6. **Daily limits** — MAX_DAILY_SPEND (max 500), MAX_EXPOSURE (max 1000)
7. **MAX_COPIES_PER_WHALE_PER_DAY** — rate limiting

## Strategy tips

- The 3 profitable whales are the starting point but maybe -JB- or SpiritUMA can work with the right filters (category, price range, min size)
- Category filters can rescue a losing whale — try restricting to their best categories
- MIN_WHALE_SIZE_USD is important: larger whale bets = more conviction = potentially better signal
- Price range 0.15-0.85 avoids noise at extremes
- How.Dare.You is 97% maker — 2% slippage may be too conservative for their trades
- POSITION_USD interacts with trade count — $50 * 1000 trades = $50K at risk vs $5 * 1000 = $5K

## Constraints

- Keep it a valid Python file with the same variable names
- WHALES must be a dict of {str: bool} — only the 5 whales listed
- WHALE_CATEGORIES values: None (all) or a list like ["sports", "politics", "other"]
- **POSITION_USD: max 50** (clamped by eval)
- **MAX_DAILY_SPEND: max 500** (clamped)
- **MAX_EXPOSURE: max 1000** (clamped)
- **MAX_OPEN_POSITIONS: max 50** (clamped)
