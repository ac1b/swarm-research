#!/usr/bin/env python3
"""
Meta-eval: measures how well engine.py performs on the speed-opt benchmark.

Metric: final_best / baseline (improvement ratio).
Higher = engine finds better optimizations.

Uses a fresh copy of speed-opt each run to avoid state leakage.
"""

import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import re
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
SWARM_ROOT = SCRIPT_DIR.parent.parent
SPEED_OPT_SRC = SWARM_ROOT / "examples" / "speed-opt"


def setup_test_env(tmpdir):
    """Create a fresh speed-opt environment with the modified engine."""
    test_dir = Path(tmpdir) / "speed-opt"
    shutil.copytree(SPEED_OPT_SRC, test_dir)

    # Remove any leftover state
    board = test_dir / "board.json"
    if board.exists():
        board.unlink()
    git_dir = test_dir / ".git"
    if git_dir.exists():
        shutil.rmtree(git_dir)

    # Reset solution to baseline
    (test_dir / "target" / "solution.py").write_text(
        'def process_data(data: list) -> float:\n'
        '    """Process a list of numbers: filter, transform, aggregate."""\n'
        '    result = 0.0\n'
        '    for x in data:\n'
        '        if x > 0:\n'
        '            val = x ** 0.5\n'
        '            if val > 1.0:\n'
        '                result += val * 2.0 + 1.0 / (val + 1.0)\n'
        '            else:\n'
        '                result += val\n'
        '    return round(result, 6)\n'
    )

    # Override task to 1 round (fast eval)
    (test_dir / "task.md").write_text(
        '---\n'
        'target: target/solution.py\n'
        'eval: python3 eval.py\n'
        'direction: maximize\n'
        'rounds: 1\n'
        'timeout: 30\n'
        '---\n\n'
        'Optimize the Python function process_data for maximum speed.\n'
        'Keep the function signature: def process_data(data: list) -> float\n'
        'You may use any Python standard library. NumPy is NOT available.\n'
    )

    # Copy the main engine from project root
    shutil.copy(SWARM_ROOT / "engine.py", test_dir / "engine.py")

    # Copy the modified agent_prompts.py (this is what agents optimize)
    prompts_src = SCRIPT_DIR / "target" / "agent_prompts.py"
    if prompts_src.exists():
        shutil.copy(prompts_src, test_dir / "agent_prompts.py")

    # Copy run.py
    shutil.copy(SWARM_ROOT / "run.py", test_dir / "run.py")

    # Copy .env
    env_file = SWARM_ROOT / ".env"
    if env_file.exists():
        shutil.copy(env_file, test_dir / ".env")

    return test_dir


def validate_prompts(prompts_path):
    """Check that agent_prompts.py is valid Python with required exports."""
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("test_prompts", prompts_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        # Check required attributes
        assert hasattr(mod, "AGENTS"), "Missing AGENTS"
        assert len(mod.AGENTS) >= 1, "AGENTS is empty"
        for a in mod.AGENTS:
            assert hasattr(a, "name") and hasattr(a, "strategy") and hasattr(a, "temperature"), \
                f"AgentConfig missing fields: {a}"
        return True, ""
    except Exception as e:
        return False, str(e)


def run_swarm(test_dir):
    """Run the swarm engine and extract results."""
    # Pre-validate agent_prompts.py
    prompts_file = test_dir / "agent_prompts.py"
    if prompts_file.exists():
        valid, err = validate_prompts(prompts_file)
        if not valid:
            return None, None, 0, 0, f"agent_prompts.py validation failed: {err}"

    result = subprocess.run(
        [sys.executable, "run.py", "task.md", "--rounds", "1"],
        cwd=test_dir,
        capture_output=True, text=True, timeout=180,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )

    output = result.stdout + result.stderr

    # Extract baseline and final scores
    baseline = None
    final = None
    kept = 0
    total = 0

    for line in output.split("\n"):
        if "Baseline:" in line and "score" not in line:
            m = re.search(r"[-+]?\d+\.?\d+", line)
            if m:
                baseline = float(m.group())
        if "Final best:" in line:
            m = re.search(r"[-+]?\d+\.?\d+", line)
            if m:
                final = float(m.group())
        if "Kept:" in line and "/" in line:
            m = re.search(r"(\d+)/(\d+)", line)
            if m:
                kept = int(m.group(1))
                total = int(m.group(2))
        if "KEPT" in line and "score=" in line:
            # Count actual keeps from log
            pass

    return baseline, final, kept, total, output


def main():
    # Run 2 trials and take the better one (reduces variance)
    best_score = 0.0

    for trial in range(2):
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                test_dir = setup_test_env(tmpdir)
                baseline, final, kept, total, output = run_swarm(test_dir)

                if baseline is None or final is None or baseline == 0:
                    print(f"Trial {trial+1}: could not parse results", file=sys.stderr)
                    print(f"Output:\n{output[-500:]}", file=sys.stderr)
                    continue

                # Score = improvement ratio * kept_rate
                improvement = final / baseline
                kept_rate = kept / total if total > 0 else 0
                # Composite score: mostly improvement, bonus for kept rate
                score = improvement * 100 + kept_rate * 10

                print(
                    f"Trial {trial+1}: baseline={baseline:.2f} final={final:.2f} "
                    f"improvement={improvement:.3f}x kept={kept}/{total} score={score:.2f}",
                    file=sys.stderr,
                )
                best_score = max(best_score, score)

        except subprocess.TimeoutExpired:
            print(f"Trial {trial+1}: timed out", file=sys.stderr)
        except Exception as e:
            print(f"Trial {trial+1}: error: {e}", file=sys.stderr)

    print(f"{best_score:.2f}")


if __name__ == "__main__":
    main()
