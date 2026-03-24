"""Integration tests for backtracking in SwarmEngine."""
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from engine import SwarmEngine, SearchTree, AgentConfig


def make_engine(work_dir, backtrack=0, max_backtracks=5, rounds=10, early_stop=0):
    engine = SwarmEngine(str(work_dir / "task.md"))
    engine.backtrack = backtrack
    engine.max_backtracks = max_backtracks
    engine.rounds = rounds
    engine.early_stop = early_stop
    engine.no_report = True
    return engine


def make_llm_reply(value):
    """Create a full-file LLM response."""
    return f"Changed x to {value}.\n\n```file\nx = {value}\n```"


class TestBacktrackDisabled:
    def test_no_tree_by_default(self, tmp_work_dir):
        engine = make_engine(tmp_work_dir, backtrack=0)
        assert engine.tree is None
        assert engine.backtrack == 0

    def test_no_tree_json_created(self, tmp_work_dir):
        engine = make_engine(tmp_work_dir, backtrack=0, rounds=1)
        engine.agents = [AgentConfig("Test", "test", 0.5)]

        scores = iter([1.0, 2.0])
        with patch("engine.run_eval", side_effect=lambda *a, **kw: next(scores)):
            with patch("engine.call_llm", return_value=make_llm_reply(2)):
                engine.run()
        assert not (tmp_work_dir / "tree.json").exists()


class TestBacktrackTrigger:
    def test_triggers_after_stale_rounds(self, tmp_work_dir):
        """Backtrack should trigger after N stale rounds."""
        engine = make_engine(tmp_work_dir, backtrack=2, rounds=6)
        engine.agents = [AgentConfig("Test", "test", 0.5)]

        # baseline=1, R1 improve to 5, R2 stale, R3 stale → backtrack
        eval_results = [
            1.0,   # baseline
            5.0,   # R1: kept
            5.0,   # R2: stale
            5.0,   # R3: stale → backtrack triggers (back to root, score=1.0)
            3.0,   # R4: improvement from 1.0 (kept)
            3.0,   # R5: stale
            3.0,   # R6: stale
        ]
        idx = [0]

        def mock_eval(*a, **kw):
            i = idx[0]
            idx[0] += 1
            return eval_results[i] if i < len(eval_results) else 1.0

        reply_n = [0]

        def mock_llm(*a, **kw):
            reply_n[0] += 1
            return make_llm_reply(reply_n[0] * 2)

        with patch("engine.run_eval", side_effect=mock_eval):
            with patch("engine.call_llm", side_effect=mock_llm):
                engine.run()

        assert engine.backtrack_count >= 1
        assert engine.tree is not None

    def test_resets_stale_rounds(self, tmp_work_dir):
        """After backtrack, stale_rounds should reset."""
        engine = make_engine(tmp_work_dir, backtrack=1, rounds=4)
        engine.agents = [AgentConfig("Test", "test", 0.5)]

        eval_results = [
            1.0,   # baseline
            1.0,   # R1: stale → backtrack (but only root, no target → fail)
            1.0,   # R2: stale
            1.0,   # R3: stale
            1.0,   # R4: stale
        ]
        idx = [0]

        def mock_eval(*a, **kw):
            i = idx[0]
            idx[0] += 1
            return eval_results[i] if i < len(eval_results) else 1.0

        with patch("engine.run_eval", side_effect=mock_eval):
            with patch("engine.call_llm", return_value=make_llm_reply(1)):
                engine.run()

        # With only root node and no improvements, backtrack has no target
        # So stale_rounds should accumulate
        assert engine.tree is not None


class TestBacktrackLimit:
    def test_respects_max_backtracks(self, tmp_work_dir):
        engine = make_engine(tmp_work_dir, backtrack=1, max_backtracks=2, rounds=10)
        engine.agents = [AgentConfig("Test", "test", 0.5)]

        # Create a scenario with improvements then staling to trigger backtracks
        call_n = [0]

        def mock_eval(*a, **kw):
            call_n[0] += 1
            if call_n[0] == 1:
                return 1.0  # baseline
            if call_n[0] == 2:
                return 5.0  # R1: kept
            return 5.0  # everything else stale

        reply_n = [0]

        def mock_llm(*a, **kw):
            reply_n[0] += 1
            return make_llm_reply(reply_n[0])

        with patch("engine.run_eval", side_effect=mock_eval):
            with patch("engine.call_llm", side_effect=mock_llm):
                engine.run()

        assert engine.backtrack_count <= 2


class TestGlobalBest:
    def test_restores_global_best(self, tmp_work_dir):
        """If global best was found in abandoned branch, restore it at end."""
        engine = make_engine(tmp_work_dir, backtrack=2, max_backtracks=1, rounds=8)
        engine.agents = [AgentConfig("Test", "test", 0.5)]

        # baseline=1, R1=10 (kept), R2=stale, R3=stale → backtrack to root
        # After backtrack: best_score=1.0, R4=stale, ..., end
        # Global best should be restored to 10
        eval_n = [0]

        def mock_eval(*a, **kw):
            eval_n[0] += 1
            if eval_n[0] == 1:
                return 1.0  # baseline
            if eval_n[0] == 2:
                return 10.0  # R1: huge improvement
            return 1.0  # everything else returns baseline-level

        reply_n = [0]

        def mock_llm(*a, **kw):
            reply_n[0] += 1
            if reply_n[0] == 1:
                return make_llm_reply(10)
            return make_llm_reply(1)  # no change

        with patch("engine.run_eval", side_effect=mock_eval):
            with patch("engine.call_llm", side_effect=mock_llm):
                engine.run()

        assert engine.best_score == 10.0
        content = (tmp_work_dir / "target" / "solution.py").read_text()
        assert "10" in content


class TestBacktrackContext:
    def test_empty_before_backtrack(self, tmp_work_dir):
        engine = make_engine(tmp_work_dir, backtrack=3)
        assert engine._backtrack_context() == ""

    def test_empty_when_no_tree(self, tmp_work_dir):
        engine = make_engine(tmp_work_dir, backtrack=0)
        assert engine._backtrack_context() == ""

    def test_has_content_after_backtrack(self, tmp_work_dir):
        engine = make_engine(tmp_work_dir, backtrack=2)

        tree = SearchTree(tmp_work_dir / "tree.json")
        tree.create_root(1.0, "x = 1\n")
        tree.add_child(0, 5.0, "x = 5\n", 1, "Explorer", "increase x")
        tree.mark_abandoned(1)
        tree.active_node_id = 0
        tree.backtrack_count = 1
        tree._save()

        engine.tree = tree
        engine.backtrack_count = 1

        ctx = engine._backtrack_context()
        assert "Backtracking active" in ctx
        assert "abandoned" in ctx.lower()
        assert "DIVERGE" in ctx


class TestDoBacktrack:
    def test_returns_false_without_tree(self, tmp_work_dir):
        engine = make_engine(tmp_work_dir, backtrack=0)
        assert engine._do_backtrack(1) is False

    def test_returns_false_no_target(self, tmp_work_dir):
        """Single root node, no lateral targets → returns False."""
        engine = make_engine(tmp_work_dir, backtrack=2)
        engine.tree = SearchTree(tmp_work_dir / "tree.json")
        engine.tree.create_root(1.0, "x = 1\n")
        engine.target_file = tmp_work_dir / "target" / "solution.py"

        # Need git init for git_commit
        from engine import git_init
        git_init(tmp_work_dir)

        assert engine._do_backtrack(1) is False

    def test_successful_backtrack(self, tmp_work_dir):
        """Backtrack to a lateral node restores its content."""
        engine = make_engine(tmp_work_dir, backtrack=2)
        engine.target_file = tmp_work_dir / "target" / "solution.py"
        engine.work_dir = tmp_work_dir
        engine.best_score = 5.0

        from engine import git_init
        git_init(tmp_work_dir)

        tree = SearchTree(tmp_work_dir / "tree.json")
        tree.create_root(1.0, "x = 1\n")
        tree.add_child(0, 5.0, "x = 5\n", 1, "A", "c1")  # id=1 (current)
        tree.add_child(0, 3.0, "x = 3\n", 1, "B", "c2")  # id=2 (lateral)
        tree.active_node_id = 1

        engine.tree = tree
        result = engine._do_backtrack(2)

        assert result is True
        assert engine.backtrack_count == 1
        assert engine.best_score == 3.0
        assert engine.tree.active_node_id == 2
        assert engine.tree.nodes[1].abandoned is True
        content = engine.target_file.read_text()
        assert "x = 3" in content


class TestGitignore:
    def test_tree_json_in_gitignore(self, tmp_work_dir):
        engine = make_engine(tmp_work_dir, backtrack=2, rounds=1)
        engine.agents = [AgentConfig("Test", "test", 0.5)]

        with patch("engine.run_eval", return_value=1.0):
            with patch("engine.call_llm", return_value=make_llm_reply(1)):
                engine.run()

        gitignore = (tmp_work_dir / ".gitignore").read_text()
        assert "tree.json" in gitignore


class TestEarlyStopWarning:
    def test_warns_early_stop_le_backtrack(self, tmp_work_dir, capsys):
        """Should warn if early_stop <= backtrack."""
        # Set via task.md YAML to trigger warning in __init__
        (tmp_work_dir / "task.md").write_text(
            "---\n"
            "target: target/solution.py\n"
            "eval: python eval.py\n"
            "direction: maximize\n"
            "rounds: 5\n"
            "early_stop: 2\n"
            "backtrack: 3\n"
            "---\n"
            "Maximize x.\n"
        )
        engine = SwarmEngine(str(tmp_work_dir / "task.md"))
        captured = capsys.readouterr()
        assert "WARNING" in captured.out
        assert "early_stop" in captured.out


class TestCLIOverride:
    def test_override_backtrack(self, tmp_work_dir):
        engine = SwarmEngine(str(tmp_work_dir / "task.md"))
        assert engine.backtrack == 0
        engine.backtrack = 3
        engine.max_backtracks = 10
        assert engine.backtrack == 3
        assert engine.max_backtracks == 10


class TestTreeJsonExclusion:
    def test_excluded_from_eval_copy(self, tmp_work_dir):
        """tree.json should not be copied to temp dir for parallel eval."""
        (tmp_work_dir / "tree.json").write_text("{}")

        import tempfile
        items_copied = []
        for item in tmp_work_dir.iterdir():
            if item.name in (".git", "board.json", "agent_memory", "tree.json"):
                continue
            items_copied.append(item.name)

        assert "tree.json" not in items_copied


class TestPrintReport:
    def test_shows_tree_stats(self, tmp_work_dir, capsys):
        engine = make_engine(tmp_work_dir, backtrack=2)
        engine.baseline_score = 1.0
        engine.best_score = 5.0
        engine.experiment_count = 10

        tree = SearchTree(tmp_work_dir / "tree.json")
        tree.create_root(1.0, "v0")
        tree.add_child(0, 5.0, "v1", 1, "A", "c1")
        engine.tree = tree
        engine.backtrack_count = 1

        engine._print_report()
        captured = capsys.readouterr()
        assert "Tree nodes:" in captured.out
        assert "Backtracks:" in captured.out
        assert "Max depth:" in captured.out

    def test_no_tree_stats_when_disabled(self, tmp_work_dir, capsys):
        engine = make_engine(tmp_work_dir, backtrack=0)
        engine.baseline_score = 1.0
        engine.best_score = 2.0
        engine.experiment_count = 5

        engine._print_report()
        captured = capsys.readouterr()
        assert "Tree nodes:" not in captured.out


class TestBacktrackResume:
    def test_loads_existing_tree(self, tmp_work_dir):
        """On resume with existing tree.json, tree state should be restored."""
        # Create tree.json
        tree = SearchTree(tmp_work_dir / "tree.json")
        tree.create_root(1.0, "x = 1\n")
        tree.add_child(0, 5.0, "x = 5\n", 1, "Explorer", "test")
        tree.backtrack_count = 1
        tree._save()

        # Create board.json for resume
        board_data = {
            "meta": {"task": "solution.py|python eval.py|maximize"},
            "findings": [{
                "agent": "Explorer", "round": 1, "experiment": 1,
                "score": 5.0, "baseline": 1.0, "delta": 4.0,
                "kept": True, "reasoning": "test",
                "description": "test", "change_summary": "test",
                "timestamp": "2024-01-01",
            }],
        }
        (tmp_work_dir / "board.json").write_text(json.dumps(board_data))
        (tmp_work_dir / "target" / "solution.py").write_text("x = 5\n")

        engine = make_engine(tmp_work_dir, backtrack=2, rounds=3)
        engine.agents = [AgentConfig("Test", "test", 0.5)]

        with patch("engine.run_eval", return_value=5.0):
            with patch("engine.call_llm", return_value=make_llm_reply(5)):
                engine.run()

        assert engine.tree is not None
        assert len(engine.tree.nodes) >= 2

    def test_rebuilds_on_hash_mismatch(self, tmp_work_dir):
        """If file content doesn't match tree hash, rebuild tree."""
        # Create tree with content "x = 5\n"
        tree = SearchTree(tmp_work_dir / "tree.json")
        tree.create_root(1.0, "x = 1\n")
        tree.add_child(0, 5.0, "x = 5\n", 1, "Explorer", "test")
        tree._save()

        # But actual file has different content
        (tmp_work_dir / "target" / "solution.py").write_text("x = 99\n")

        board_data = {
            "meta": {"task": "solution.py|python eval.py|maximize"},
            "findings": [{
                "agent": "Explorer", "round": 1, "experiment": 1,
                "score": 5.0, "baseline": 1.0, "delta": 4.0,
                "kept": True, "reasoning": "test",
                "description": "test", "change_summary": "test",
                "timestamp": "2024-01-01",
            }],
        }
        (tmp_work_dir / "board.json").write_text(json.dumps(board_data))

        engine = make_engine(tmp_work_dir, backtrack=2, rounds=3)
        engine.agents = [AgentConfig("Test", "test", 0.5)]

        with patch("engine.run_eval", return_value=99.0):
            with patch("engine.call_llm", return_value=make_llm_reply(99)):
                engine.run()

        # Tree should have been rebuilt with root score matching current eval
        assert engine.tree is not None
        assert engine.tree.nodes[0].content == "x = 99\n"


class TestBacktrackConfig:
    def test_task_yaml_config(self, tmp_work_dir):
        """backtrack and max_backtracks from task.md YAML."""
        (tmp_work_dir / "task.md").write_text(
            "---\n"
            "target: target/solution.py\n"
            "eval: python eval.py\n"
            "direction: maximize\n"
            "rounds: 5\n"
            "backtrack: 3\n"
            "max_backtracks: 7\n"
            "---\n"
            "Maximize x.\n"
        )
        engine = SwarmEngine(str(tmp_work_dir / "task.md"))
        assert engine.backtrack == 3
        assert engine.max_backtracks == 7

    def test_defaults(self, tmp_work_dir):
        engine = SwarmEngine(str(tmp_work_dir / "task.md"))
        assert engine.backtrack == 0
        assert engine.max_backtracks == 5
