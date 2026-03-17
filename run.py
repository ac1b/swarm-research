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

    args = parser.parse_args()

    if not Path(args.task).exists():
        print(f"Task file not found: {args.task}")
        sys.exit(1)

    engine = SwarmEngine(args.task)
    if args.rounds:
        engine.rounds = args.rounds
    engine.run()


if __name__ == "__main__":
    main()
