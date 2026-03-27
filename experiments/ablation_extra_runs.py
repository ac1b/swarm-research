#!/usr/bin/env python3
"""Extra runs for statistical power: game-ai n=4 more per config (total n=7).

Adds runs 4-7 for all 4 configs (full, no_backtrack, single_agent, no_board).
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
BASELINE = 25.62
DIRECTION = "maximize"
EXTRA_RUNS = 4  # runs 4-7

CONFIGS = {
    "full": {
        "agents": DEFAULT_AGENTS,
        "backtrack": 3,
        "disable_board": False,
    },
    "no_backtrack": {
        "agents": DEFAULT_AGENTS,
        "backtrack": 0,
        "disable_board": False,
    },
    "single_agent": {
        "agents": [DEFAULT_AGENTS[0]],
        "backtrack": 3,
        "disable_board": False,
    },
    "no_board": {
        "agents": DEFAULT_AGENTS,
        "backtrack": 3,
        "disable_board": True,
    },
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
        engine.backtrack = cfg["backtrack"]
        engine.max_backtracks = 5
        engine.agents = cfg["agents"]
        engine.no_report = True
        engine.parallel = False
        engine.early_stop = 0
        if cfg["disable_board"]:
            engine.disable_board = True

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
                engine.backtrack = cfg["backtrack"]
                engine.max_backtracks = 5
                engine.agents = cfg["agents"]
                engine.no_report = True
                engine.parallel = False
                engine.early_stop = 0
                if cfg["disable_board"]:
                    engine.disable_board = True
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
    configs = list(CONFIGS.keys())
    total = len(configs) * EXTRA_RUNS
    print(f"Extra runs: {EXAMPLE} | {len(configs)} configs x {EXTRA_RUNS} runs = {total} total")
    print(f"  Rounds: {ROUNDS} | Run indices: 4-7\n")

    results = []
    idx = 0
    t_start = time.time()

    for cfg_name in configs:
        for r in range(4, 4 + EXTRA_RUNS):
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

    raw_path = results_dir / "ablation_extra_runs_raw.json"
    raw_path.write_text(json.dumps([asdict(r) for r in results], indent=2))
    print(f"Raw results: {raw_path}")

    # Print summary combining with existing data
    print("\n## game-ai combined (n=7 per config):")
    existing_files = [
        results_dir / "ablation_raw.json",
        results_dir / "ablation_board_raw.json",
    ]
    all_game = []
    for f in existing_files:
        if f.exists():
            for r in json.loads(f.read_text()):
                if r["example"] == "game-ai" and r["status"] == "ok":
                    all_game.append(r)
    for r in results:
        if r.status == "ok":
            all_game.append(asdict(r))

    for cfg_name in configs:
        runs = [r for r in all_game if r["config"] == cfg_name]
        if not runs:
            continue
        scores = [r["final_score"] for r in runs]
        s_mean = mean(scores)
        s_std = stdev(scores) if len(scores) > 1 else 0.0
        print(f"  {cfg_name:16s} n={len(runs):2d} | {s_mean:.2f} +/- {s_std:.2f}")


if __name__ == "__main__":
    main()
