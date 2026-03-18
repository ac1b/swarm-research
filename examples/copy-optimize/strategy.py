# Copy Trading Strategy Configuration
# Swarm agents will optimize these parameters to maximize backtest PnL.

# Which whales to copy (True = copy, False = skip)
# Full history data: 175K fills, 2810 markets, 2739 resolved
WHALES = {
    "ScottyNooo": True,      # 1131 resolved, 58.6% WR, +$155K
    "-JB-": False,            # 804 resolved, 94.8% WR, -$94K (wins small, loses big)
    "warlasfutpro": True,     # 39 resolved, 76.9% WR, +$126K
    "SpiritUMA": False,       # 1350 resolved, 86.5% WR, -$488K (wins small, loses big)
    "How.Dare.You": True,     # 1539 resolved, 74.4% WR, +$110K (97% maker - low impact)
}

# Category filters per whale (None = all categories allowed)
# Categories: "sports", "crypto", "politics", "weather", "other"
WHALE_CATEGORIES = {
    "ScottyNooo": None,
    "-JB-": None,
    "warlasfutpro": None,
    "SpiritUMA": None,
    "How.Dare.You": None,
}

# Price filters — only copy trades where whale's buy price is in this range
# Tightened from 0.10-0.90 to avoid noise at extremes (tip from strategy docs)
MIN_PRICE = 0.15
MAX_PRICE = 0.85

# Position sizing
POSITION_USD = 10.0           # Increased from $5 to $10 - more capital per trade
MAX_OPEN_POSITIONS = 20      # max simultaneous positions (max 50)
MAX_DAILY_SPEND = 100.0      # max USD per day (max 500)
MAX_EXPOSURE = 200.0         # max total open exposure (max 1000)

# Dedup: skip if we already have a position in this market
SKIP_DUPLICATE_MARKET = True

# Min whale trade size to trigger copy (in USD)
# Increased from 50 to 100 — larger whale bets = stronger signal
MIN_WHALE_SIZE_USD = 100.0

# Max trades to copy per whale per day
MAX_COPIES_PER_WHALE_PER_DAY = 10
