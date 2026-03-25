"""Scheduler configuration parameters."""

# Local search iterations
MAX_ITERATIONS = 0

# Simulated annealing
INITIAL_TEMPERATURE = 100.0
COOLING_RATE = 0.995
MIN_TEMPERATURE = 0.01

# Tabu search
TABU_TENURE = 10

# Dispatching rule: "fifo", "edd", "wspt", "atc", "covert"
DISPATCH_RULE = "fifo"

# ATC parameter (if using ATC rule)
ATC_K = 2.0
