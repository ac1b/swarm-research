#!/usr/bin/env python3
"""CLI entry point for SwarmResearch."""

import argparse
import sys
from pathlib import Path

# Load .env if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

from engine import SwarmEngine


def main():
    parser = argparse.ArgumentParser(description="SwarmResearch — multi-agent optimization engine")
    parser.add_argument("task", help="Path to task.md")
    parser.add_argument("--rounds", type=int, help="Override number of rounds")
    parser.add_argument("--backtrack", type=int, help="Backtrack after N stale rounds (0=disabled)")
    parser.add_argument("--max-backtracks", type=int, help="Max number of backtracks (default 5)")
    parser.add_argument("--parallel", action="store_true", help="Run agents in parallel")
    parser.add_argument("--early-stop", type=int, help="Stop after N rounds without improvement (0=disabled)")
    parser.add_argument("--mode", choices=["full", "diff", "auto"], help="Code edit mode")
    parser.add_argument("--eval-runs", type=int, help="Number of eval runs to average")
    parser.add_argument("--timeout", type=int, help="Eval timeout in seconds")
    parser.add_argument("--no-report", action="store_true", help="Skip LLM report generation")

    args = parser.parse_args()

    if not Path(args.task).exists():
        print(f"Task file not found: {args.task}")
        sys.exit(1)

    engine = SwarmEngine(args.task)
    if args.rounds is not None:
        engine.rounds = args.rounds
    if args.backtrack is not None:
        engine.backtrack = args.backtrack
    if args.max_backtracks is not None:
        engine.max_backtracks = args.max_backtracks
    if args.parallel:
        engine.parallel = True
    if args.early_stop is not None:
        engine.early_stop = args.early_stop
    if args.mode:
        engine.use_diff = args.mode == "diff" or (
            args.mode == "auto" and engine.use_diff)
    if args.eval_runs is not None:
        engine.eval_runs = args.eval_runs
    if args.timeout is not None:
        engine.timeout = args.timeout
    if args.no_report:
        engine.no_report = True
    engine.run()


if __name__ == "__main__":
    main()
