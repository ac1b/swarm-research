#!/usr/bin/env python3
"""Ablation experiment runner for SwarmResearch.

Runs controlled experiments across examples and configurations to measure
the contribution of key features (backtracking, multi-agent, shared board).

Usage:
    python3 experiments/ablation.py                          # full 27-run experiment
    python3 experiments/ablation.py --dry-run                # print plan, don't run
    python3 experiments/ablation.py --example bio-opt --config full --runs 1  # single test
"""

import argparse
import json
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from statistics import mean, stdev

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import SwarmEngine, AgentConfig, DEFAULT_AGENTS

# ── Experiment definitions ──────────────────────────────────────────────────

EXAMPLES = {
    "tsp-opt":  {"baseline": 592.71, "direction": "minimize"},
    "game-ai":  {"baseline": 25.62,  "direction": "maximize"},
    "bio-opt":  {"baseline": 39.58,  "direction": "maximize"},
}

CONFIGS = {
    "full": {
        "agents": DEFAULT_AGENTS,
        "backtrack": 3,
        "description": "Full system (3 agents + backtracking)",
    },
    "no_backtrack": {
        "agents": DEFAULT_AGENTS,
        "backtrack": 0,
        "description": "No tree search (3 agents, no backtracking)",
    },
    "single_agent": {
        "agents": [DEFAULT_AGENTS[0]],  # Explorer only
        "backtrack": 3,
        "description": "Single agent (Explorer only + backtracking)",
    },
}

ROUNDS = 6
RUNS_PER_CONFIG = 3

# ── Result dataclass ────────────────────────────────────────────────────────

@dataclass
class RunResult:
    example: str
    config: str
    run: int
    baseline: float = 0.0
    final_score: float = 0.0
    delta_pct: float = 0.0
    backtracks: int = 0
    elapsed: float = 0.0
    status: str = "ok"
    error: str = ""

# ── Core runner ─────────────────────────────────────────────────────────────

def run_single(example: str, config_name: str, run_idx: int) -> RunResult:
    """Run one experiment in an isolated temp directory."""
    cfg = CONFIGS[config_name]
    example_dir = ROOT / "examples" / example
    result = RunResult(example=example, config=config_name, run=run_idx)

    tmpdir = Path(tempfile.mkdtemp(prefix=f"ablation_{example}_{config_name}_"))
    try:
        # Copy example to isolated temp dir
        work_dir = tmpdir / example
        shutil.copytree(example_dir, work_dir)

        # Clean any leftover state
        for stale in ["board.json", "tree.json"]:
            (work_dir / stale).unlink(missing_ok=True)
        mem_dir = work_dir / "agent_memory"
        if mem_dir.exists():
            shutil.rmtree(mem_dir)

        task_path = work_dir / "task.md"

        # Create engine and override settings
        engine = SwarmEngine(str(task_path))
        engine.rounds = ROUNDS
        engine.backtrack = cfg["backtrack"]
        engine.max_backtracks = 5
        engine.agents = cfg["agents"]
        engine.no_report = True
        engine.parallel = False
        engine.early_stop = 0

        t0 = time.time()
        engine.run()
        result.elapsed = time.time() - t0

        result.baseline = engine.baseline_score or 0.0
        result.final_score = engine.global_best_score or engine.best_score or result.baseline
        result.backtracks = engine.backtrack_count

        if result.baseline != 0:
            if EXAMPLES[example]["direction"] == "minimize":
                result.delta_pct = (result.baseline - result.final_score) / result.baseline * 100
            else:
                result.delta_pct = (result.final_score - result.baseline) / result.baseline * 100

        result.status = "ok"

    except Exception as e:
        err_msg = str(e)
        # Retry once on rate limit
        if "429" in err_msg or "rate" in err_msg.lower():
            print(f"    Rate limited, sleeping 60s and retrying...")
            time.sleep(60)
            try:
                engine = SwarmEngine(str(task_path))
                engine.rounds = ROUNDS
                engine.backtrack = cfg["backtrack"]
                engine.max_backtracks = 5
                engine.agents = cfg["agents"]
                engine.no_report = True
                engine.parallel = False
                engine.early_stop = 0

                t0 = time.time()
                engine.run()
                result.elapsed = time.time() - t0
                result.baseline = engine.baseline_score or 0.0
                result.final_score = engine.global_best_score or engine.best_score or result.baseline
                result.backtracks = engine.backtrack_count
                if result.baseline != 0:
                    if EXAMPLES[example]["direction"] == "minimize":
                        result.delta_pct = (result.baseline - result.final_score) / result.baseline * 100
                    else:
                        result.delta_pct = (result.final_score - result.baseline) / result.baseline * 100
                result.status = "ok"
            except Exception as e2:
                result.status = "failed"
                result.error = str(e2)
                print(f"    FAILED (retry): {e2}")
        else:
            result.status = "failed"
            result.error = err_msg
            print(f"    FAILED: {e}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    return result


# ── Summary generation ──────────────────────────────────────────────────────

def generate_summary(results: list[RunResult]) -> str:
    """Generate markdown summary table from results."""
    lines = [
        "# Ablation Experiment Results",
        "",
        f"Rounds per run: {ROUNDS} | Runs per config: {RUNS_PER_CONFIG}",
        "",
        "| Example | Config | Baseline | Final (mean +/- std) | Delta % (mean +/- std) | Backtracks |",
        "|---------|--------|----------|----------------------|------------------------|------------|",
    ]

    for ex_name in EXAMPLES:
        for cfg_name in CONFIGS:
            runs = [r for r in results if r.example == ex_name and r.config == cfg_name and r.status == "ok"]
            if not runs:
                lines.append(f"| {ex_name} | {cfg_name} | - | FAILED | - | - |")
                continue

            baseline = runs[0].baseline
            scores = [r.final_score for r in runs]
            deltas = [r.delta_pct for r in runs]
            bt = [r.backtracks for r in runs]

            s_mean = mean(scores)
            s_std = stdev(scores) if len(scores) > 1 else 0.0
            d_mean = mean(deltas)
            d_std = stdev(deltas) if len(deltas) > 1 else 0.0
            bt_mean = mean(bt)

            direction = EXAMPLES[ex_name]["direction"]
            sign = "-" if direction == "minimize" else "+"

            lines.append(
                f"| {ex_name} | {cfg_name} | {baseline:.2f} "
                f"| {s_mean:.2f} +/- {s_std:.2f} "
                f"| {sign}{d_mean:.1f} +/- {d_std:.1f}% "
                f"| {bt_mean:.1f} |"
            )

    # Per-run details
    lines.extend(["", "## Per-run details", ""])
    for r in results:
        status = f"score={r.final_score:.2f}" if r.status == "ok" else f"FAILED: {r.error}"
        lines.append(f"- {r.example} | {r.config} | run {r.run} -> {status} ({r.elapsed:.1f}s)")

    lines.append("")
    return "\n".join(lines)


# ── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="SwarmResearch ablation experiments")
    parser.add_argument("--dry-run", action="store_true", help="Print plan without running")
    parser.add_argument("--example", choices=list(EXAMPLES.keys()), help="Run single example")
    parser.add_argument("--config", choices=list(CONFIGS.keys()), help="Run single config")
    parser.add_argument("--runs", type=int, default=RUNS_PER_CONFIG, help="Runs per config")
    args = parser.parse_args()

    examples = [args.example] if args.example else list(EXAMPLES.keys())
    configs = [args.config] if args.config else list(CONFIGS.keys())
    runs = args.runs

    total = len(examples) * len(configs) * runs
    print(f"Ablation experiment: {len(examples)} examples x {len(configs)} configs x {runs} runs = {total} total")
    print(f"  Rounds per run: {ROUNDS}")
    print()

    for cfg_name in configs:
        cfg = CONFIGS[cfg_name]
        agents = ", ".join(a.name for a in cfg["agents"])
        print(f"  {cfg_name:16s} | agents: {agents:40s} | backtrack: {cfg['backtrack']}")
    print()

    if args.dry_run:
        print("DRY RUN — would execute:")
        idx = 0
        for ex in examples:
            for cfg_name in configs:
                for r in range(1, runs + 1):
                    idx += 1
                    agents = ", ".join(a.name for a in CONFIGS[cfg_name]["agents"])
                    print(f"  [{idx}/{total}] {ex} | {cfg_name} | run {r} "
                          f"(agents: {agents}, backtrack: {CONFIGS[cfg_name]['backtrack']})")
        return

    results = []
    idx = 0
    t_start = time.time()

    for ex in examples:
        for cfg_name in configs:
            for r in range(1, runs + 1):
                idx += 1
                print(f"[{idx}/{total}] {ex} | {cfg_name} | run {r} ...", end=" ", flush=True)
                result = run_single(ex, cfg_name, r)
                results.append(result)
                if result.status == "ok":
                    print(f"-> score={result.final_score:.2f} ({result.elapsed:.1f}s)")
                else:
                    print(f"-> FAILED")

    elapsed_total = time.time() - t_start
    print(f"\nDone. {total} runs in {elapsed_total:.0f}s")

    # Save raw results
    results_dir = ROOT / "experiments" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    raw_path = results_dir / "ablation_raw.json"
    raw_path.write_text(json.dumps([asdict(r) for r in results], indent=2))
    print(f"Raw results: {raw_path}")

    # Save summary
    summary = generate_summary(results)
    summary_path = results_dir / "ablation_summary.md"
    summary_path.write_text(summary)
    print(f"Summary:     {summary_path}")
    print()
    print(summary)


if __name__ == "__main__":
    main()
