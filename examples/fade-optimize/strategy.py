# Fade Trading Strategy Configuration
# Bet AGAINST known losing traders on Polymarket.
# When a loser buys outcome X, we buy the opposite (fade).

# Filters — which signals to act on

# Minimum signal strength (number of times loser traded this market)
MIN_SIGNAL_STRENGTH = 1  # Reduced - allow more signals in sweet spot range

# Minimum herding count (how many different losers bet the same side)
MIN_HERDING = 3  # Moderate herding - more signals than >=10, better than <3

# Minimum tilt count (consecutive losing trades by same wallet in session)
MIN_TILT = 0

# Loser score threshold (more negative = worse trader = stronger signal)
MAX_LOSER_SCORE = 0  # only fade traders with score <= this

# Entry price range — our fade buy price
# Narrowing to 0.60-0.70 for higher WR in the profitable sweet spot
# Data shows 0.50-0.70 at 61.9% WR - upper portion likely even better
MIN_FADE_PRICE = 0.60
MAX_FADE_PRICE = 0.70

# Minimum loser trade size (USD) — bigger = more conviction = stronger signal
MIN_LOSER_SIZE = 1.0  # Keep small to capture more signals in profitable range

# Category filters — which categories to fade in
# None = all categories, or list like ["sports", "politics"]
ALLOWED_CATEGORIES = None

# Excluded categories — skip these
EXCLUDED_CATEGORIES = None

# Position sizing
POSITION_USD = 50.0          # MAX - confirmed edge in sweet spot
MAX_DAILY_TRADES = 200      # max trades per day
MAX_DAILY_SPEND = 1000.0    # max USD per day
