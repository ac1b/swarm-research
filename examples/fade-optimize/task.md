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

# Optimize Fade Trading Strategy

You are optimizing a "fade the losers" strategy on Polymarket prediction markets.
The strategy bets AGAINST known losing traders — when a loser buys outcome X, we buy the opposite.

## IMPORTANT: Current state

With default config, fade is MASSIVELY unprofitable: 53K signals, 45.8% WR, -$30K PnL.
Your job is to find filters that extract the profitable subset.

## Cost model
- **Slippage: 1%** (less than copy trading — we're not chasing a whale's price impact)
- **Taker fee: 1.5%** per trade
- Combined ~2.5% cost. Need >52% WR to break even at mid-range prices.

## Key data from analysis (USE THIS!)

### By entry price range (CRITICAL):
| Range | Signals | WR | PnL |
|-------|---------|-----|-----|
| <0.30 | 11026 | 9.5% | **-$27,184** ← CATASTROPHIC |
| 0.30-0.50 | 10794 | 39.0% | -$3,688 |
| **0.50-0.70** | **10540** | **61.9%** | **+$2,046** ← ONLY PROFITABLE |
| 0.70-0.90 | 9124 | 78.6% | -$1,159 |
| >=0.90 | 12008 | 46.1% | -$285 |

The 0.50-0.70 range is the sweet spot. Entry <0.30 is DEATH.
At 0.70-0.90, WR is 78% but upside is tiny (pay 0.80 to win 0.20).

### By herding count:
| Herding | Signals | WR | PnL |
|---------|---------|-----|-----|
| 1 | 21419 | 39.3% | -$14,553 ← single loser = noise |
| 2 | 8609 | 43.4% | -$5,537 |
| 3 | 4192 | 48.0% | -$1,323 |
| 5 | 2268 | 52.9% | -$1,015 |
| **10** | **709** | **57.5%** | **+$115** ← multiple losers = signal |

### By signal strength:
All strengths are losing. Strength 1 is worst (-$5K). Higher strength slightly better but still negative.

### By loser score:
All buckets are losing. Surprisingly, worse losers (score <=-100) aren't much better than mild losers.

### By tilt:
Higher tilt slightly better WR but still negative across all levels.

## What to optimize

1. **Entry price range** — THIS IS KEY. Only 0.50-0.70 is profitable
2. **Herding minimum** — require multiple losers for signal confirmation
3. **Loser score threshold** — how bad must the trader be
4. **Signal strength minimum** — minimum times loser traded this market
5. **Tilt minimum** — loser on a losing streak = tilted = worse decisions?
6. **Loser size minimum** — bigger loser bets = more conviction
7. **Category filters** — some categories work, some don't
8. **Position sizing** — scale up if edge is confirmed
9. **Daily limits** — cap risk per day

## Strategy

The key insight: fade only works when:
1. Entry price is in the 0.50-0.70 range (good risk/reward + real signal)
2. Multiple losers bet the same side (herding — confirms the signal)
3. Price is NOT at extremes (<0.30 or >0.90 — these are noise)

Focus on finding the precise filter combination that maximizes net PnL.

## Constraints

- Keep it a valid Python file with the same variable names
- POSITION_USD: max 50
- MAX_DAILY_SPEND: max 1000
- MAX_DAILY_TRADES: max 200
- All numeric params must be positive (or 0 for minimums)
- ALLOWED_CATEGORIES / EXCLUDED_CATEGORIES: None or list of strings
