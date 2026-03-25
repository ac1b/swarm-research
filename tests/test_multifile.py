"""Tests for multi-file target support."""
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from engine import (
    SwarmEngine, SearchTree, AgentConfig, Board,
    apply_diffs, extract_file_contents, extract_file_content,
    build_prompt, parse_task,
)


# ---------------------------------------------------------------------------
# parse_task: list support
# ---------------------------------------------------------------------------

class TestParseTaskList:
    def test_single_target(self, tmp_path):
        (tmp_path / "task.md").write_text(
            "---\ntarget: target/main.py\neval: python eval.py\n---\nDo it.\n"
        )
        config = parse_task(tmp_path / "task.md")
        assert config["target"] == "target/main.py"

    def test_list_target(self, tmp_path):
        (tmp_path / "task.md").write_text(
            "---\ntarget: [target/a.py, target/b.py]\neval: python eval.py\n---\nDo it.\n"
        )
        config = parse_task(tmp_path / "task.md")
        assert config["target"] == ["target/a.py", "target/b.py"]

    def test_list_target_three_files(self, tmp_path):
        (tmp_path / "task.md").write_text(
            "---\ntarget: [a.py, b.py, c.py]\neval: python eval.py\n---\nDo it.\n"
        )
        config = parse_task(tmp_path / "task.md")
        assert config["target"] == ["a.py", "b.py", "c.py"]


# ---------------------------------------------------------------------------
# apply_diffs: multi-file
# ---------------------------------------------------------------------------

class TestApplyDiffsMultiFile:
    def test_single_file_no_path(self):
        originals = {"main.py": "x = 1\ny = 2\n"}
        response = (
            "Changed x.\n\n```diff\n"
            "<<<< SEARCH\nx = 1\n====\nx = 10\n>>>> REPLACE\n```"
        )
        result = apply_diffs(originals, response)
        assert result is not None
        assert result["main.py"] == "x = 10\ny = 2\n"

    def test_multi_file_with_paths(self):
        originals = {
            "sorter.py": "def sort(a):\n    return sorted(a)\n",
            "config.py": "N = 10\n",
        }
        response = (
            "Changed N.\n\n```diff\n"
            "<<<< SEARCH config.py\nN = 10\n====\nN = 50\n>>>> REPLACE\n```"
        )
        result = apply_diffs(originals, response)
        assert result is not None
        assert result["config.py"] == "N = 50\n"
        assert result["sorter.py"] == originals["sorter.py"]  # unchanged

    def test_multi_file_two_files_changed(self):
        originals = {
            "a.py": "x = 1\n",
            "b.py": "y = 2\n",
        }
        response = (
            "Changed both.\n\n```diff\n"
            "<<<< SEARCH a.py\nx = 1\n====\nx = 10\n>>>> REPLACE\n```\n"
            "```diff\n"
            "<<<< SEARCH b.py\ny = 2\n====\ny = 20\n>>>> REPLACE\n```"
        )
        result = apply_diffs(originals, response)
        assert result is not None
        assert result["a.py"] == "x = 10\n"
        assert result["b.py"] == "y = 20\n"

    def test_unknown_file_returns_none(self):
        originals = {"main.py": "x = 1\n"}
        response = (
            "Changed.\n\n```diff\n"
            "<<<< SEARCH other.py\nx = 1\n====\nx = 2\n>>>> REPLACE\n```"
        )
        result = apply_diffs(originals, response)
        assert result is None

    def test_no_change_returns_none(self):
        originals = {"main.py": "x = 1\n"}
        response = (
            "No real change.\n\n```diff\n"
            "<<<< SEARCH\nx = 1\n====\nx = 1\n>>>> REPLACE\n```"
        )
        result = apply_diffs(originals, response)
        assert result is None

    def test_default_file_is_first_key(self):
        """When no path given, defaults to first file in dict."""
        originals = {"first.py": "a = 1\n", "second.py": "b = 2\n"}
        response = (
            "Changed a.\n\n```diff\n"
            "<<<< SEARCH\na = 1\n====\na = 99\n>>>> REPLACE\n```"
        )
        result = apply_diffs(originals, response)
        assert result is not None
        assert result["first.py"] == "a = 99\n"
        assert result["second.py"] == "b = 2\n"


# ---------------------------------------------------------------------------
# extract_file_contents: multi-file
# ---------------------------------------------------------------------------

class TestExtractFileContentsMultiFile:
    def test_single_file_fallback(self):
        originals = {"main.py": "x = 1\n"}
        response = "Changed.\n\n```file\nx = 2\n```"
        result = extract_file_contents(originals, response)
        assert result is not None
        assert result["main.py"] == "x = 2\n"

    def test_single_file_python_block(self):
        originals = {"main.py": "x = 1\n"}
        response = "Changed.\n\n```python\nx = 2\n```"
        result = extract_file_contents(originals, response)
        assert result is not None
        assert result["main.py"] == "x = 2\n"

    def test_multi_file_labeled_blocks(self):
        originals = {
            "sorter.py": "def sort(a):\n    pass\n",
            "config.py": "N = 10\n",
        }
        response = (
            "Improved.\n\n"
            "```file:sorter.py\ndef sort(a):\n    return sorted(a)\n```\n"
            "```file:config.py\nN = 50\n```"
        )
        result = extract_file_contents(originals, response)
        assert result is not None
        assert "return sorted(a)" in result["sorter.py"]
        assert result["config.py"] == "N = 50\n"

    def test_multi_file_partial_output(self):
        """Agent outputs only changed files; unchanged kept from originals."""
        originals = {
            "sorter.py": "def sort(a):\n    pass\n",
            "config.py": "N = 10\n",
        }
        response = "Changed config only.\n\n```file:config.py\nN = 50\n```"
        result = extract_file_contents(originals, response)
        assert result is not None
        assert result["sorter.py"] == originals["sorter.py"]  # unchanged
        assert result["config.py"] == "N = 50\n"

    def test_no_content_returns_none(self):
        originals = {"main.py": "x = 1\n"}
        response = "I don't know what to do."
        result = extract_file_contents(originals, response)
        assert result is None

    def test_same_content_returns_none(self):
        originals = {"main.py": "x = 1\n"}
        response = "No change.\n\n```file:main.py\nx = 1\n```"
        result = extract_file_contents(originals, response)
        assert result is None


# ---------------------------------------------------------------------------
# build_prompt: multi-file rendering
# ---------------------------------------------------------------------------

class TestBuildPromptMultiFile:
    def test_single_file_format(self):
        board = Board(Path("/tmp/_test_board_sf.json"))
        contents = {"main.py": "x = 1\n"}
        msgs = build_prompt(
            AgentConfig("Test", "test"), "Maximize x.",
            contents, board, "No experiments.", 1,
        )
        user_msg = msgs[1]["content"]
        assert "## Current file: main.py" in user_msg
        assert "x = 1" in user_msg
        assert "## Target files" not in user_msg

    def test_multi_file_format(self):
        board = Board(Path("/tmp/_test_board_mf.json"))
        contents = {"sorter.py": "def sort(): pass\n", "config.py": "N=10\n"}
        msgs = build_prompt(
            AgentConfig("Test", "test"), "Optimize.",
            contents, board, "No experiments.", 1,
        )
        user_msg = msgs[1]["content"]
        assert "## Target files" in user_msg
        assert "### sorter.py" in user_msg
        assert "### config.py" in user_msg
        assert "## Current file:" not in user_msg

    def test_multi_file_diff_instructions(self):
        board = Board(Path("/tmp/_test_board_mfd.json"))
        contents = {"a.py": "x=1\n", "b.py": "y=2\n"}
        msgs = build_prompt(
            AgentConfig("Test", "test"), "Optimize.",
            contents, board, "No experiments.", 1, use_diff=True,
        )
        system_msg = msgs[0]["content"]
        assert "MULTI-FILE" in system_msg
        assert "SEARCH path/to/file.py" in system_msg

    def test_multi_file_full_instructions(self):
        board = Board(Path("/tmp/_test_board_mff.json"))
        contents = {"a.py": "x=1\n", "b.py": "y=2\n"}
        msgs = build_prompt(
            AgentConfig("Test", "test"), "Optimize.",
            contents, board, "No experiments.", 1, use_diff=False,
        )
        system_msg = msgs[0]["content"]
        assert "MULTI-FILE" in system_msg
        assert "file:path/to/file.py" in system_msg

    def test_single_file_no_multi_instructions(self):
        board = Board(Path("/tmp/_test_board_snm.json"))
        contents = {"main.py": "x=1\n"}
        msgs = build_prompt(
            AgentConfig("Test", "test"), "Optimize.",
            contents, board, "No experiments.", 1,
        )
        system_msg = msgs[0]["content"]
        assert "MULTI-FILE" not in system_msg


# ---------------------------------------------------------------------------
# SwarmEngine: multi-file init
# ---------------------------------------------------------------------------

class TestEngineMultiFileInit:
    def test_single_target_from_string(self, tmp_path):
        target_dir = tmp_path / "target"
        target_dir.mkdir()
        (target_dir / "main.py").write_text("x = 1\n")
        (tmp_path / "eval.py").write_text('print("SCORE: 1")\n')
        (tmp_path / "task.md").write_text(
            "---\ntarget: target/main.py\neval: python eval.py\n"
            "direction: maximize\nrounds: 1\n---\nDo it.\n"
        )
        engine = SwarmEngine(str(tmp_path / "task.md"))
        assert len(engine.target_files) == 1
        assert engine.target_files[0] == tmp_path / "target" / "main.py"

    def test_multi_target_from_list(self, tmp_path):
        target_dir = tmp_path / "target"
        target_dir.mkdir()
        (target_dir / "a.py").write_text("x = 1\n")
        (target_dir / "b.py").write_text("y = 2\n")
        (tmp_path / "eval.py").write_text('print("SCORE: 1")\n')
        (tmp_path / "task.md").write_text(
            "---\ntarget: [target/a.py, target/b.py]\neval: python eval.py\n"
            "direction: maximize\nrounds: 1\n---\nDo it.\n"
        )
        engine = SwarmEngine(str(tmp_path / "task.md"))
        assert len(engine.target_files) == 2

    def test_read_write_targets(self, tmp_path):
        target_dir = tmp_path / "target"
        target_dir.mkdir()
        (target_dir / "a.py").write_text("x = 1\n")
        (target_dir / "b.py").write_text("y = 2\n")
        (tmp_path / "eval.py").write_text('print("SCORE: 1")\n')
        (tmp_path / "task.md").write_text(
            "---\ntarget: [target/a.py, target/b.py]\neval: python eval.py\n"
            "direction: maximize\nrounds: 1\n---\nDo it.\n"
        )
        engine = SwarmEngine(str(tmp_path / "task.md"))
        contents = engine._read_targets()
        assert contents == {"target/a.py": "x = 1\n", "target/b.py": "y = 2\n"}

        new_contents = {"target/a.py": "x = 99\n", "target/b.py": "y = 42\n"}
        engine._write_targets(new_contents)
        assert (target_dir / "a.py").read_text() == "x = 99\n"
        assert (target_dir / "b.py").read_text() == "y = 42\n"

    def test_fingerprint_multi(self, tmp_path):
        target_dir = tmp_path / "target"
        target_dir.mkdir()
        (target_dir / "b.py").write_text("y = 2\n")
        (target_dir / "a.py").write_text("x = 1\n")
        (tmp_path / "eval.py").write_text('print("SCORE: 1")\n')
        (tmp_path / "task.md").write_text(
            "---\ntarget: [target/b.py, target/a.py]\neval: python eval.py\n"
            "direction: maximize\nrounds: 1\n---\nDo it.\n"
        )
        engine = SwarmEngine(str(tmp_path / "task.md"))
        # Fingerprint should be sorted
        assert engine._task_fingerprint.startswith("target/a.py|target/b.py|")


# ---------------------------------------------------------------------------
# SearchTree: dict content
# ---------------------------------------------------------------------------

class TestTreeDictContent:
    def test_create_root_with_dict(self, tmp_path):
        tree = SearchTree(tmp_path / "tree.json")
        content = {"a.py": "x = 1\n", "b.py": "y = 2\n"}
        tree.create_root(1.0, content)
        assert tree.nodes[0].content == content

    def test_add_child_with_dict(self, tmp_path):
        tree = SearchTree(tmp_path / "tree.json")
        content0 = {"a.py": "x = 1\n"}
        content1 = {"a.py": "x = 2\n"}
        tree.create_root(1.0, content0)
        tree.add_child(0, 2.0, content1, 1, "Explorer", "changed x")
        assert tree.nodes[1].content == content1

    def test_dict_content_hash_deterministic(self):
        content = {"b.py": "y = 2\n", "a.py": "x = 1\n"}
        h1 = SearchTree._content_hash(content)
        h2 = SearchTree._content_hash(content)
        assert h1 == h2

    def test_dict_content_hash_order_independent(self):
        """Dict hash should be the same regardless of insertion order."""
        c1 = {"a.py": "x", "b.py": "y"}
        c2 = {"b.py": "y", "a.py": "x"}
        assert SearchTree._content_hash(c1) == SearchTree._content_hash(c2)

    def test_dict_content_persistence(self, tmp_path):
        path = tmp_path / "tree.json"
        content = {"sorter.py": "def sort(): pass\n", "config.py": "N=10\n"}
        tree = SearchTree(path)
        tree.create_root(1.0, content)
        tree.add_child(0, 2.0, {"sorter.py": "def sort(): return sorted(a)\n", "config.py": "N=50\n"},
                        1, "Explorer", "improved")

        tree2 = SearchTree(path)
        assert tree2.nodes[0].content == content
        assert tree2.nodes[1].content["config.py"] == "N=50\n"

    def test_string_content_still_works(self, tmp_path):
        """Backward compat: string content in tree still works."""
        tree = SearchTree(tmp_path / "tree.json")
        tree.create_root(1.0, "hello world")
        assert tree.nodes[0].content == "hello world"
        h = SearchTree._content_hash("hello world")
        assert len(h) == 16


# ---------------------------------------------------------------------------
# Integration: multi-file engine run
# ---------------------------------------------------------------------------

class TestMultiFileEngineRun:
    @pytest.fixture
    def multi_work_dir(self, tmp_path):
        target_dir = tmp_path / "target"
        target_dir.mkdir()
        (target_dir / "sorter.py").write_text("x = 1\n")
        (target_dir / "config.py").write_text("N = 10\n")
        (tmp_path / "eval.py").write_text(
            'import sys\nsys.path.insert(0, "target")\n'
            'from sorter import x\nfrom config import N\n'
            'print(f"SCORE: {x * N}")\n'
        )
        (tmp_path / "task.md").write_text(
            "---\n"
            "target: [target/sorter.py, target/config.py]\n"
            "eval: python eval.py\n"
            "direction: maximize\n"
            "rounds: 2\n"
            "---\n"
            "Maximize x * N.\n"
        )
        return tmp_path

    def test_multi_file_run(self, multi_work_dir):
        engine = SwarmEngine(str(multi_work_dir / "task.md"))
        engine.agents = [AgentConfig("Test", "test", 0.5)]
        engine.no_report = True

        # baseline=10, then 100 after change
        scores = iter([10.0, 100.0, 100.0, 100.0, 100.0])

        def mock_llm(*a, **kw):
            return (
                "Changed x and N.\n\n"
                "```file:target/sorter.py\nx = 5\n```\n"
                "```file:target/config.py\nN = 20\n```"
            )

        with patch("engine.run_eval", side_effect=lambda *a, **kw: next(scores)):
            with patch("engine.call_llm", side_effect=mock_llm):
                engine.run()

        assert engine.best_score == 100.0
        assert (multi_work_dir / "target" / "sorter.py").read_text() == "x = 5\n"
        assert (multi_work_dir / "target" / "config.py").read_text() == "N = 20\n"

    def test_multi_file_partial_change(self, multi_work_dir):
        """Agent changes only one file; other stays unchanged."""
        engine = SwarmEngine(str(multi_work_dir / "task.md"))
        engine.agents = [AgentConfig("Test", "test", 0.5)]
        engine.no_report = True

        scores = iter([10.0, 100.0, 100.0, 100.0, 100.0])

        def mock_llm(*a, **kw):
            return "Changed config.\n\n```file:target/config.py\nN = 100\n```"

        with patch("engine.run_eval", side_effect=lambda *a, **kw: next(scores)):
            with patch("engine.call_llm", side_effect=mock_llm):
                engine.run()

        assert engine.best_score == 100.0
        assert (multi_work_dir / "target" / "sorter.py").read_text() == "x = 1\n"  # unchanged

    def test_multi_file_with_backtrack(self, multi_work_dir):
        """Backtracking works with multi-file dict content."""
        engine = SwarmEngine(str(multi_work_dir / "task.md"))
        engine.agents = [AgentConfig("Test", "test", 0.5)]
        engine.backtrack = 1
        engine.max_backtracks = 2
        engine.rounds = 4
        engine.no_report = True

        eval_n = [0]
        def mock_eval(*a, **kw):
            eval_n[0] += 1
            if eval_n[0] == 1: return 10.0   # baseline
            if eval_n[0] == 2: return 50.0   # R1: kept
            return 50.0                       # stale

        reply_n = [0]
        def mock_llm(*a, **kw):
            reply_n[0] += 1
            return f"Changed.\n\n```file:target/sorter.py\nx = {reply_n[0] * 5}\n```"

        with patch("engine.run_eval", side_effect=mock_eval):
            with patch("engine.call_llm", side_effect=mock_llm):
                engine.run()

        assert engine.tree is not None
        # Tree should have dict content
        for node in engine.tree.nodes.values():
            assert isinstance(node.content, dict)
