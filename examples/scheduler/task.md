---
target: [target/scheduler.py, target/heuristics.py, target/config.py]
eval: python3 eval.py
direction: minimize
rounds: 10
timeout: 45
eval_runs: 1
mode: full
backtrack: 3
max_backtracks: 3
---

# Job Shop Scheduling Optimization

Minimize total weighted tardiness on 5 benchmark instances of the
flexible job shop scheduling problem.

## Problem
- N jobs, each with a sequence of operations (precedence within job)
- M machines, each operation has a set of eligible machines with different processing times
- Jobs have release times, due dates, and priority weights
- **Minimize**: sum of weight_i * max(0, completion_i - due_i) for all jobs

## Interface
`schedule(jobs, n_machines)` in `scheduler.py`:
- `jobs`: list of dicts with keys:
  - `id`: int
  - `release`: int (earliest start time)
  - `due`: int (deadline)
  - `weight`: float (priority weight)
  - `ops`: list of dicts, each with:
    - `eligible`: list of machine indices
    - `duration`: dict {machine_idx: processing_time}
- `n_machines`: number of machines
- Returns: list of `(job_id, op_index, machine, start_time)` tuples

## Scoring
5 instances of increasing difficulty (10-50 jobs, 3-8 machines).
Score = sum of weighted tardiness across all instances.
Invalid schedules (constraint violations) get penalty = 100000 per instance.

## Files
- `target/scheduler.py` — main scheduling algorithm
- `target/heuristics.py` — dispatching rules, local search operators
- `target/config.py` — algorithm parameters (iterations, temperatures, etc.)

## Optimization Space
- Dispatching rules (EDD, WSPT, ATC, COVERT)
- Local search (swap, insert, critical path moves)
- Simulated annealing / tabu search
- Machine assignment optimization
- Bottleneck-based scheduling

Baseline (FIFO): ~214,000. Good heuristics: <70,000.
