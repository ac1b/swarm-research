#!/usr/bin/env python3
"""Backtrack depth scaling: how does backtrack threshold affect performance?

Tests backtrack=1,2,5 on game-ai (we already have backtrack=3 from main ablation
and backtrack=0 from no_backtrack). 3 runs each = 9 runs.
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
BACKTRACK_VALUES = [1, 2, 5]


def run_single(backtrack_val, run_idx):
    example_dir = ROOT / "examples" / EXAMPLE
    config_name = f"bt_{backtrack_val}"
    result = RunResult(example=EXAMPLE, config=config_name, run=run_idx)

    tmpdir = Path(tempfile.mkdtemp(prefix=f"ablation_{EXAMPLE}_bt{backtrack_val}_"))
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
        engine.backtrack = backtrack_val
        engine.max_backtracks = 5
        engine.agents = DEFAULT_AGENTS
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
            result.delta_pct = (result.final_score - result.baseline) / result.baseline * 100
        result.status = "ok"
    except Exception as e:
        if "429" in str(e) or "rate" in str(e).lower():
            print(f"    Rate limited, sleeping 60s and retrying...")
            time.sleep(60)
            try:
                engine = SwarmEngine(str(work_dir / "task.md"))
                engine.rounds = ROUNDS
                engine.backtrack = backtrack_val
                engine.max_backtracks = 5
                engine.agents = DEFAULT_AGENTS
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
    total = len(BACKTRACK_VALUES) * RUNS
    print(f"Backtrack depth scaling: {EXAMPLE} | bt={BACKTRACK_VALUES} | {RUNS} runs each = {total} total")
    print(f"  Rounds: {ROUNDS} | Agents: {', '.join(a.name for a in DEFAULT_AGENTS)}")
    print(f"  (bt=0 and bt=3 already in main ablation results)\n")

    results = []
    idx = 0
    t_start = time.time()

    for bt in BACKTRACK_VALUES:
        for r in range(1, RUNS + 1):
            idx += 1
            print(f"[{idx}/{total}] bt={bt} | run {r} ...", end=" ", flush=True)
            result = run_single(bt, r)
            results.append(result)
            if result.status == "ok":
                print(f"-> score={result.final_score:.2f} bt={result.backtracks} ({result.elapsed:.1f}s)")
            else:
                print(f"-> FAILED")

    print(f"\nDone. {total} runs in {time.time() - t_start:.0f}s")

    results_dir = ROOT / "experiments" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    raw_path = results_dir / "ablation_depth_raw.json"
    raw_path.write_text(json.dumps([asdict(r) for r in results], indent=2))
    print(f"Raw results: {raw_path}")

    # Combined table with existing bt=0 and bt=3 data
    print("\n## Combined backtrack depth table (game-ai):")
    print("  (bt=0 and bt=3 from main ablation, bt=1,2,5 from this run)")

    existing = results_dir / "ablation_raw.json"
    all_runs = {}
    if existing.exists():
        for r in json.loads(existing.read_text()):
            if r["example"] == "game-ai" and r["status"] == "ok":
                if r["config"] == "no_backtrack":
                    all_runs.setdefault(0, []).append(r["final_score"])
                elif r["config"] == "full":
                    all_runs.setdefault(3, []).append(r["final_score"])

    for r in results:
        if r.status == "ok":
            bt = int(r.config.split("_")[1])
            all_runs.setdefault(bt, []).append(r.final_score)

    print(f"\n  {'bt':>3s} | {'n':>2s} | {'mean':>7s} | {'std':>6s} | backtracks")
    print(f"  {'---':>3s} | {'--':>2s} | {'-------':>7s} | {'------':>6s} | ----------")
    for bt in sorted(all_runs.keys()):
        scores = all_runs[bt]
        s_mean = mean(scores)
        s_std = stdev(scores) if len(scores) > 1 else 0.0
        bt_label = "N/A" if bt == 0 else f"up to {5}"
        print(f"  {bt:3d} | {len(scores):2d} | {s_mean:7.2f} | {s_std:6.2f} | {bt_label}")

    lines = [
        f"# Backtrack Depth Scaling — {EXAMPLE}",
        f"",
        f"Rounds: {ROUNDS} | Runs: {RUNS}",
        f"",
        f"| Backtrack | Final (mean +/- std) | Delta % | Backtracks (mean) |",
        f"|-----------|----------------------|---------|-------------------|",
    ]
    for bt in BACKTRACK_VALUES:
        cfg = f"bt_{bt}"
        runs = [r for r in results if r.config == cfg and r.status == "ok"]
        if not runs:
            lines.append(f"| {bt} | FAILED | - | - |")
            continue
        scores = [r.final_score for r in runs]
        deltas = [r.delta_pct for r in runs]
        bts = [r.backtracks for r in runs]
        s_mean = mean(scores)
        s_std = stdev(scores) if len(scores) > 1 else 0.0
        d_mean = mean(deltas)
        d_std = stdev(deltas) if len(deltas) > 1 else 0.0
        lines.append(
            f"| {bt} | {s_mean:.2f} +/- {s_std:.2f} "
            f"| +{d_mean:.1f} +/- {d_std:.1f}% "
            f"| {mean(bts):.1f} |"
        )
    lines.extend(["", "## Per-run details", ""])
    for r in results:
        status = f"score={r.final_score:.2f} bt={r.backtracks}" if r.status == "ok" else f"FAILED: {r.error}"
        lines.append(f"- bt={r.config} | run {r.run} -> {status} ({r.elapsed:.1f}s)")
    lines.append("")

    summary = "\n".join(lines)
    summary_path = results_dir / "ablation_depth_summary.md"
    summary_path.write_text(summary)
    print(f"\nSummary:     {summary_path}")


if __name__ == "__main__":
    main()
