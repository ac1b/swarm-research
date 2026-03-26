#!/usr/bin/env python3
"""Round scaling experiment: how does score improve with more rounds?

Runs game-ai (best signal) with full config at rounds=2,4,8,12.
3 runs each = 12 runs total. Shows convergence curve for paper.
"""

import json
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from statistics import mean, stdev

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import SwarmEngine, DEFAULT_AGENTS

EXAMPLE = "game-ai"
BASELINE = 25.62
DIRECTION = "maximize"
ROUND_COUNTS = [2, 4, 8, 12]
RUNS = 3


@dataclass
class RoundResult:
    rounds: int
    run: int
    baseline: float = 0.0
    final_score: float = 0.0
    delta_pct: float = 0.0
    backtracks: int = 0
    elapsed: float = 0.0
    status: str = "ok"
    error: str = ""


def run_single(rounds, run_idx):
    example_dir = ROOT / "examples" / EXAMPLE
    result = RoundResult(rounds=rounds, run=run_idx)

    tmpdir = Path(tempfile.mkdtemp(prefix=f"ablation_{EXAMPLE}_r{rounds}_"))
    try:
        work_dir = tmpdir / EXAMPLE
        shutil.copytree(example_dir, work_dir)
        for stale in ["board.json", "tree.json"]:
            (work_dir / stale).unlink(missing_ok=True)
        mem_dir = work_dir / "agent_memory"
        if mem_dir.exists():
            shutil.rmtree(mem_dir)

        engine = SwarmEngine(str(work_dir / "task.md"))
        engine.rounds = rounds
        engine.backtrack = 3
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
                engine.rounds = rounds
                engine.backtrack = 3
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


def generate_summary(results):
    lines = [
        f"# Round Scaling Experiment — {EXAMPLE}",
        "",
        f"Config: full (3 agents + backtrack=3) | {RUNS} runs per round count",
        "",
        "| Rounds | Final (mean +/- std) | Delta % (mean +/- std) | Backtracks | Time (mean) |",
        "|--------|----------------------|------------------------|------------|-------------|",
    ]

    for rc in ROUND_COUNTS:
        runs = [r for r in results if r.rounds == rc and r.status == "ok"]
        if not runs:
            lines.append(f"| {rc} | FAILED | - | - | - |")
            continue
        scores = [r.final_score for r in runs]
        deltas = [r.delta_pct for r in runs]
        bt = [r.backtracks for r in runs]
        elapsed = [r.elapsed for r in runs]

        s_mean, s_std = mean(scores), stdev(scores) if len(scores) > 1 else 0.0
        d_mean, d_std = mean(deltas), stdev(deltas) if len(deltas) > 1 else 0.0

        lines.append(
            f"| {rc} | {s_mean:.2f} +/- {s_std:.2f} "
            f"| +{d_mean:.1f} +/- {d_std:.1f}% "
            f"| {mean(bt):.1f} | {mean(elapsed):.0f}s |"
        )

    lines.extend(["", "## Per-run details", ""])
    for r in results:
        status = f"score={r.final_score:.2f}" if r.status == "ok" else f"FAILED: {r.error}"
        lines.append(f"- rounds={r.rounds} | run {r.run} -> {status} ({r.elapsed:.1f}s)")
    lines.append("")
    return "\n".join(lines)


def main():
    total = len(ROUND_COUNTS) * RUNS
    print(f"Round scaling: {EXAMPLE} | rounds={ROUND_COUNTS} | {RUNS} runs each = {total} total\n")

    results = []
    idx = 0
    t_start = time.time()

    for rc in ROUND_COUNTS:
        for r in range(1, RUNS + 1):
            idx += 1
            print(f"[{idx}/{total}] rounds={rc} | run {r} ...", end=" ", flush=True)
            result = run_single(rc, r)
            results.append(result)
            if result.status == "ok":
                print(f"-> score={result.final_score:.2f} ({result.elapsed:.1f}s)")
            else:
                print(f"-> FAILED")

    print(f"\nDone. {total} runs in {time.time() - t_start:.0f}s")

    results_dir = ROOT / "experiments" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    raw_path = results_dir / "ablation_rounds_raw.json"
    raw_path.write_text(json.dumps([asdict(r) for r in results], indent=2))
    print(f"Raw results: {raw_path}")

    summary = generate_summary(results)
    summary_path = results_dir / "ablation_rounds_summary.md"
    summary_path.write_text(summary)
    print(f"Summary:     {summary_path}\n")
    print(summary)


if __name__ == "__main__":
    main()
