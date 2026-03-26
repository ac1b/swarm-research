#!/usr/bin/env python3
"""Board ablation: test the value of shared board (findings visible to agents).

Runs 'no_board' config on all 3 examples, 3 runs each = 9 runs.
Compare with 'full' results from ablation.py.
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
from experiments.ablation import EXAMPLES, ROUNDS, RunResult, generate_summary

CONFIG_NO_BOARD = {
    "agents": DEFAULT_AGENTS,
    "backtrack": 3,
    "description": "Board disabled (3 agents + backtracking, no shared findings)",
}

RUNS = 3


def run_single(example, run_idx):
    example_dir = ROOT / "examples" / example
    result = RunResult(example=example, config="no_board", run=run_idx)

    tmpdir = Path(tempfile.mkdtemp(prefix=f"ablation_{example}_no_board_"))
    try:
        work_dir = tmpdir / example
        shutil.copytree(example_dir, work_dir)
        for stale in ["board.json", "tree.json"]:
            (work_dir / stale).unlink(missing_ok=True)
        mem_dir = work_dir / "agent_memory"
        if mem_dir.exists():
            shutil.rmtree(mem_dir)

        engine = SwarmEngine(str(work_dir / "task.md"))
        engine.rounds = ROUNDS
        engine.backtrack = CONFIG_NO_BOARD["backtrack"]
        engine.max_backtracks = 5
        engine.agents = CONFIG_NO_BOARD["agents"]
        engine.no_report = True
        engine.parallel = False
        engine.early_stop = 0
        engine.disable_board = True  # <-- the ablation flag

        t0 = time.time()
        engine.run()
        result.elapsed = time.time() - t0
        result.baseline = engine.baseline_score or 0.0
        result.final_score = engine.global_best_score or engine.best_score or result.baseline
        result.backtracks = engine.backtrack_count
        if result.baseline != 0:
            direction = EXAMPLES[example]["direction"]
            if direction == "minimize":
                result.delta_pct = (result.baseline - result.final_score) / result.baseline * 100
            else:
                result.delta_pct = (result.final_score - result.baseline) / result.baseline * 100
        result.status = "ok"
    except Exception as e:
        if "429" in str(e) or "rate" in str(e).lower():
            print(f"    Rate limited, sleeping 60s and retrying...")
            time.sleep(60)
            try:
                engine = SwarmEngine(str(work_dir / "task.md"))
                engine.rounds = ROUNDS
                engine.backtrack = CONFIG_NO_BOARD["backtrack"]
                engine.max_backtracks = 5
                engine.agents = CONFIG_NO_BOARD["agents"]
                engine.no_report = True
                engine.parallel = False
                engine.early_stop = 0
                engine.disable_board = True
                t0 = time.time()
                engine.run()
                result.elapsed = time.time() - t0
                result.baseline = engine.baseline_score or 0.0
                result.final_score = engine.global_best_score or engine.best_score or result.baseline
                result.backtracks = engine.backtrack_count
                if result.baseline != 0:
                    direction = EXAMPLES[example]["direction"]
                    if direction == "minimize":
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
            result.error = str(e)
            print(f"    FAILED: {e}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    return result


def main():
    examples = list(EXAMPLES.keys())
    total = len(examples) * RUNS
    print(f"Board ablation: {len(examples)} examples x {RUNS} runs = {total} total")
    print(f"  Config: no_board (3 agents + backtrack, board disabled)")
    print(f"  Rounds: {ROUNDS}\n")

    results = []
    idx = 0
    t_start = time.time()

    for ex in examples:
        for r in range(1, RUNS + 1):
            idx += 1
            print(f"[{idx}/{total}] {ex} | no_board | run {r} ...", end=" ", flush=True)
            result = run_single(ex, r)
            results.append(result)
            if result.status == "ok":
                print(f"-> score={result.final_score:.2f} ({result.elapsed:.1f}s)")
            else:
                print(f"-> FAILED")

    print(f"\nDone. {total} runs in {time.time() - t_start:.0f}s")

    results_dir = ROOT / "experiments" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    raw_path = results_dir / "ablation_board_raw.json"
    raw_path.write_text(json.dumps([asdict(r) for r in results], indent=2))
    print(f"Raw results: {raw_path}")

    # Merge with main ablation results if they exist
    main_raw = results_dir / "ablation_raw.json"
    if main_raw.exists():
        main_results = json.loads(main_raw.read_text())
        all_results = [RunResult(**r) for r in main_results] + results
        summary = generate_summary(all_results)
    else:
        summary = generate_summary(results)

    summary_path = results_dir / "ablation_board_summary.md"
    summary_path.write_text(summary)
    print(f"Summary:     {summary_path}\n")
    print(summary)


if __name__ == "__main__":
    main()
