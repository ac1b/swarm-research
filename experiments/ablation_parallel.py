#!/usr/bin/env python3
"""Parallel vs sequential ablation on game-ai.

Tests whether agents benefit from seeing each other's results within a round.
Sequential: agent 2 sees agent 1's result before acting.
Parallel: all agents act on same snapshot, no intra-round communication.
"""

import json
import shutil
import sys
import tempfile
import time
from dataclasses import asdict
from pathlib import Path
from statistics import mean, stdev

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import SwarmEngine, DEFAULT_AGENTS
from experiments.ablation import ROUNDS, RunResult

EXAMPLE = "game-ai"
DIRECTION = "maximize"
RUNS = 3

CONFIGS = {
    "sequential": {"parallel": False},
    "parallel": {"parallel": True},
}


def run_single(config_name, run_idx):
    cfg = CONFIGS[config_name]
    example_dir = ROOT / "examples" / EXAMPLE
    result = RunResult(example=EXAMPLE, config=config_name, run=run_idx)

    tmpdir = Path(tempfile.mkdtemp(prefix=f"ablation_{EXAMPLE}_{config_name}_"))
    try:
        work_dir = tmpdir / EXAMPLE
        shutil.copytree(example_dir, work_dir)
        for stale in ["board.json", "tree.json"]:
            (work_dir / stale).unlink(missing_ok=True)
        mem_dir = work_dir / "agent_memory"
        if mem_dir.exists():
            shutil.rmtree(mem_dir)

        engine = SwarmEngine(str(work_dir / "task.md"))
        engine.rounds = ROUNDS
        engine.backtrack = 3
        engine.max_backtracks = 5
        engine.agents = DEFAULT_AGENTS
        engine.no_report = True
        engine.parallel = cfg["parallel"]
        engine.early_stop = 0

        t0 = time.time()
        engine.run()
        result.elapsed = time.time() - t0
        result.baseline = engine.baseline_score or 0.0
        result.final_score = engine.global_best_score or engine.best_score or result.baseline
        result.backtracks = engine.backtrack_count
        if result.baseline != 0:
            result.delta_pct = (result.final_score - result.baseline) / result.baseline * 100
        result.status = "ok"
    except Exception as e:
        if "429" in str(e) or "rate" in str(e).lower():
            print(f"    Rate limited, sleeping 60s and retrying...")
            time.sleep(60)
            try:
                engine = SwarmEngine(str(work_dir / "task.md"))
                engine.rounds = ROUNDS
                engine.backtrack = 3
                engine.max_backtracks = 5
                engine.agents = DEFAULT_AGENTS
                engine.no_report = True
                engine.parallel = cfg["parallel"]
                engine.early_stop = 0
                t0 = time.time()
                engine.run()
                result.elapsed = time.time() - t0
                result.baseline = engine.baseline_score or 0.0
                result.final_score = engine.global_best_score or engine.best_score or result.baseline
                result.backtracks = engine.backtrack_count
                if result.baseline != 0:
                    result.delta_pct = (result.final_score - result.baseline) / result.baseline * 100
                result.status = "ok"
            except Exception as e2:
                result.status = "failed"
                result.error = str(e2)
                print(f"    FAILED (retry): {e2}")
        else:
            result.status = "failed"
            result.error = str(e)
            print(f"    FAILED: {e}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    return result


def main():
    total = len(CONFIGS) * RUNS
    print(f"Parallel vs sequential: {EXAMPLE} | {RUNS} runs each = {total} total")
    print(f"  Rounds: {ROUNDS} | Agents: {', '.join(a.name for a in DEFAULT_AGENTS)}\n")

    results = []
    idx = 0
    t_start = time.time()

    for cfg_name in CONFIGS:
        for r in range(1, RUNS + 1):
            idx += 1
            print(f"[{idx}/{total}] {EXAMPLE} | {cfg_name} | run {r} ...", end=" ", flush=True)
            result = run_single(cfg_name, r)
            results.append(result)
            if result.status == "ok":
                print(f"-> score={result.final_score:.2f} ({result.elapsed:.1f}s)")
            else:
                print(f"-> FAILED")

    print(f"\nDone. {total} runs in {time.time() - t_start:.0f}s")

    results_dir = ROOT / "experiments" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    raw_path = results_dir / "ablation_parallel_raw.json"
    raw_path.write_text(json.dumps([asdict(r) for r in results], indent=2))
    print(f"Raw results: {raw_path}")

    lines = [
        f"# Parallel vs Sequential — {EXAMPLE}",
        f"",
        f"Rounds: {ROUNDS} | Runs: {RUNS} | Config: full (3 agents + backtrack=3)",
        f"",
        f"| Mode | Final (mean +/- std) | Delta % | Time (mean) |",
        f"|------|----------------------|---------|-------------|",
    ]
    for cfg_name in CONFIGS:
        runs = [r for r in results if r.config == cfg_name and r.status == "ok"]
        if not runs:
            lines.append(f"| {cfg_name} | FAILED | - | - |")
            continue
        scores = [r.final_score for r in runs]
        deltas = [r.delta_pct for r in runs]
        elapsed = [r.elapsed for r in runs]
        s_mean = mean(scores)
        s_std = stdev(scores) if len(scores) > 1 else 0.0
        d_mean = mean(deltas)
        d_std = stdev(deltas) if len(deltas) > 1 else 0.0
        lines.append(
            f"| {cfg_name} | {s_mean:.2f} +/- {s_std:.2f} "
            f"| +{d_mean:.1f} +/- {d_std:.1f}% "
            f"| {mean(elapsed):.0f}s |"
        )
    lines.extend(["", "## Per-run details", ""])
    for r in results:
        status = f"score={r.final_score:.2f}" if r.status == "ok" else f"FAILED: {r.error}"
        lines.append(f"- {r.config} | run {r.run} -> {status} ({r.elapsed:.1f}s)")
    lines.append("")

    summary = "\n".join(lines)
    summary_path = results_dir / "ablation_parallel_summary.md"
    summary_path.write_text(summary)
    print(f"Summary:     {summary_path}\n")
    print(summary)


if __name__ == "__main__":
    main()
