"""Shared fixtures for SwarmResearch tests."""
import sys
from pathlib import Path

import pytest

# Ensure engine module is importable
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def tmp_work_dir(tmp_path):
    """Minimal working directory with target + eval + task.md."""
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    (target_dir / "solution.py").write_text("x = 1\n")

    (tmp_path / "eval.py").write_text(
        'import sys\n'
        'sys.path.insert(0, "target")\n'
        'from solution import x\n'
        'print(f"SCORE: {x}")\n'
    )

    (tmp_path / "task.md").write_text(
        "---\n"
        "target: target/solution.py\n"
        "eval: python eval.py\n"
        "direction: maximize\n"
        "rounds: 5\n"
        "---\n"
        "Maximize x.\n"
    )

    return tmp_path
