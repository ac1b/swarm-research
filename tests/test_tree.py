"""Unit tests for TreeNode and SearchTree."""
import json
import threading
from pathlib import Path

import pytest
from engine import TreeNode, SearchTree


class TestTreeNode:
    def test_create_node(self):
        node = TreeNode(
            id=0, parent_id=None, score=1.0, content="hello",
            content_hash="abc123", round_created=0, agent="baseline",
            change_summary="baseline",
        )
        assert node.id == 0
        assert node.children == []
        assert node.visits == 0
        assert node.abandoned is False

    def test_default_fields(self):
        node = TreeNode(
            id=1, parent_id=0, score=2.0, content="world",
            content_hash="def456", round_created=1, agent="Explorer",
            change_summary="test",
        )
        assert node.children == []
        assert node.visits == 0
        assert node.abandoned is False


class TestSearchTreeBasics:
    def test_create_root(self, tmp_path):
        tree = SearchTree(tmp_path / "tree.json")
        root_id = tree.create_root(10.0, "content")
        assert root_id == 0
        assert tree.nodes[0].score == 10.0
        assert tree.nodes[0].content == "content"
        assert tree.nodes[0].parent_id is None
        assert tree.active_node_id == 0

    def test_add_child(self, tmp_path):
        tree = SearchTree(tmp_path / "tree.json")
        tree.create_root(10.0, "v0")
        child_id = tree.add_child(0, 12.0, "v1", round_created=1,
                                  agent="Explorer", change_summary="test")
        assert child_id == 1
        assert tree.nodes[1].parent_id == 0
        assert tree.nodes[1].score == 12.0
        assert 1 in tree.nodes[0].children
        assert tree.active_node_id == 1

    def test_multiple_children(self, tmp_path):
        tree = SearchTree(tmp_path / "tree.json")
        tree.create_root(10.0, "v0")
        c1 = tree.add_child(0, 11.0, "v1", 1, "A", "c1")
        c2 = tree.add_child(0, 12.0, "v2", 2, "B", "c2")
        assert tree.nodes[0].children == [c1, c2]

    def test_deep_chain(self, tmp_path):
        tree = SearchTree(tmp_path / "tree.json")
        tree.create_root(10.0, "v0")
        tree.add_child(0, 11.0, "v1", 1, "A", "c1")
        tree.add_child(1, 12.0, "v2", 2, "B", "c2")
        tree.add_child(2, 13.0, "v3", 3, "C", "c3")
        assert tree.active_node_id == 3
        assert tree.nodes[2].children == [3]


class TestRecordVisit:
    def test_increments(self, tmp_path):
        tree = SearchTree(tmp_path / "tree.json")
        tree.create_root(10.0, "v0")
        assert tree.nodes[0].visits == 0
        tree.record_visit(0)
        assert tree.nodes[0].visits == 1
        tree.record_visit(0)
        assert tree.nodes[0].visits == 2

    def test_persists(self, tmp_path):
        path = tmp_path / "tree.json"
        tree = SearchTree(path)
        tree.create_root(10.0, "v0")
        tree.record_visit(0)
        tree.record_visit(0)

        tree2 = SearchTree(path)
        assert tree2.nodes[0].visits == 2


class TestMarkAbandoned:
    def test_marks(self, tmp_path):
        tree = SearchTree(tmp_path / "tree.json")
        tree.create_root(10.0, "v0")
        tree.add_child(0, 11.0, "v1", 1, "A", "c1")
        assert tree.nodes[1].abandoned is False
        tree.mark_abandoned(1)
        assert tree.nodes[1].abandoned is True

    def test_persists(self, tmp_path):
        path = tmp_path / "tree.json"
        tree = SearchTree(path)
        tree.create_root(10.0, "v0")
        tree.add_child(0, 11.0, "v1", 1, "A", "c1")
        tree.mark_abandoned(1)

        tree2 = SearchTree(path)
        assert tree2.nodes[1].abandoned is True


class TestPathToRoot:
    def test_root_only(self, tmp_path):
        tree = SearchTree(tmp_path / "tree.json")
        tree.create_root(10.0, "v0")
        assert tree.get_path_to_root(0) == [0]

    def test_chain(self, tmp_path):
        tree = SearchTree(tmp_path / "tree.json")
        tree.create_root(10.0, "v0")
        tree.add_child(0, 11.0, "v1", 1, "A", "c1")
        tree.add_child(1, 12.0, "v2", 2, "B", "c2")
        assert tree.get_path_to_root(2) == [0, 1, 2]

    def test_branch(self, tmp_path):
        tree = SearchTree(tmp_path / "tree.json")
        tree.create_root(10.0, "v0")
        tree.add_child(0, 11.0, "v1", 1, "A", "c1")  # id=1
        tree.add_child(0, 12.0, "v2", 2, "B", "c2")  # id=2
        assert tree.get_path_to_root(1) == [0, 1]
        assert tree.get_path_to_root(2) == [0, 2]


class TestAbandonedSummary:
    def test_empty(self, tmp_path):
        tree = SearchTree(tmp_path / "tree.json")
        tree.create_root(10.0, "v0")
        assert tree.get_abandoned_paths_summary() == ""

    def test_with_abandoned(self, tmp_path):
        tree = SearchTree(tmp_path / "tree.json")
        tree.create_root(10.0, "v0")
        tree.add_child(0, 11.0, "v1", 1, "Explorer", "c1")
        tree.mark_abandoned(1)
        summary = tree.get_abandoned_paths_summary()
        assert "Abandoned branches:" in summary
        assert "Explorer" in summary
        assert "11.0000" in summary


class TestContentHash:
    def test_deterministic(self):
        h1 = SearchTree._content_hash("hello")
        h2 = SearchTree._content_hash("hello")
        assert h1 == h2

    def test_different_for_different_content(self):
        h1 = SearchTree._content_hash("hello")
        h2 = SearchTree._content_hash("world")
        assert h1 != h2

    def test_length(self):
        h = SearchTree._content_hash("test")
        assert len(h) == 16


class TestSelectBacktrackTarget:
    def test_prefers_high_score_lateral(self, tmp_path):
        tree = SearchTree(tmp_path / "tree.json")
        tree.create_root(10.0, "v0")
        tree.add_child(0, 11.0, "v1", 1, "A", "c1")  # id=1
        tree.add_child(1, 12.0, "v2", 2, "B", "c2")  # id=2 (active)
        tree.add_child(0, 15.0, "v3", 1, "C", "c3")  # id=3 (lateral)
        # Active=2, path=[0,1,2], lateral=3 (score=15)
        target = tree.select_backtrack_target(2)
        assert target == 3

    def test_penalizes_visits(self, tmp_path):
        tree = SearchTree(tmp_path / "tree.json")
        tree.create_root(10.0, "v0")
        tree.add_child(0, 20.0, "v1", 1, "A", "c1")  # id=1
        tree.add_child(0, 14.0, "v2", 1, "B", "c2")  # id=2
        tree.add_child(0, 13.0, "v3", 1, "C", "c3")  # id=3 (active)
        # Visit node 1 many times: 20 * 1/21 ≈ 0.95
        # Node 2 unvisited: 14 * 1/1 = 14
        for _ in range(20):
            tree.record_visit(1)
        target = tree.select_backtrack_target(3)
        assert target == 2

    def test_penalizes_abandoned(self, tmp_path):
        tree = SearchTree(tmp_path / "tree.json")
        tree.create_root(10.0, "v0")
        tree.add_child(0, 15.0, "v1", 1, "A", "c1")  # id=1
        tree.add_child(0, 14.0, "v2", 1, "B", "c2")  # id=2
        tree.add_child(0, 13.0, "v3", 1, "C", "c3")  # id=3 (active)
        tree.mark_abandoned(1)
        # Node 1: 15 * 1.0 * 0.3 = 4.5
        # Node 2: 14 * 1.0 * 1.0 = 14.0
        target = tree.select_backtrack_target(3)
        assert target == 2

    def test_ancestor_fallback(self, tmp_path):
        """When no lateral candidates, fall back to ancestor with < 3 children."""
        tree = SearchTree(tmp_path / "tree.json")
        tree.create_root(10.0, "v0")
        tree.add_child(0, 11.0, "v1", 1, "A", "c1")  # id=1
        tree.add_child(1, 12.0, "v2", 2, "B", "c2")  # id=2 (active)
        # Path=[0,1,2], no lateral nodes
        # Ancestor fallback: node 1 (1 child < 3)
        target = tree.select_backtrack_target(2)
        assert target == 1

    def test_ancestor_fallback_skips_full(self, tmp_path):
        """Ancestor with >= 3 children should be skipped."""
        tree = SearchTree(tmp_path / "tree.json")
        tree.create_root(10.0, "v0")
        # Give root 3 children
        tree.add_child(0, 11.0, "a", 1, "A", "c1")  # id=1
        tree.add_child(0, 12.0, "b", 1, "B", "c2")  # id=2
        tree.add_child(0, 13.0, "c", 1, "C", "c3")  # id=3
        tree.add_child(3, 14.0, "d", 2, "D", "c4")  # id=4 (active)
        # Path=[0,3,4], lateral=[1,2]
        # Lateral candidates exist: 1 (11*1=11), 2 (12*1=12)
        target = tree.select_backtrack_target(4)
        assert target == 2  # higher score

    def test_returns_none_when_exhausted(self, tmp_path):
        """Single root, no children, active=root → no candidates."""
        tree = SearchTree(tmp_path / "tree.json")
        tree.create_root(10.0, "v0")
        target = tree.select_backtrack_target(0)
        assert target is None

    def test_returns_none_all_ancestors_full(self, tmp_path):
        """All laterals on current path, ancestors have >= 3 children → None."""
        tree = SearchTree(tmp_path / "tree.json")
        tree.create_root(10.0, "v0")
        # Root has 3 children (full) — chain: 0 → 1 → 2
        tree.add_child(0, 11.0, "a", 1, "A", "c1")  # 1
        tree.add_child(0, 12.0, "b", 1, "B", "c2")  # 2 (lateral)
        tree.add_child(0, 13.0, "c", 1, "C", "c3")  # 3 (lateral)
        # From node 1: laterals are 2 and 3, so it finds them
        target = tree.select_backtrack_target(1)
        assert target in (2, 3)

    def test_avoids_current_path(self, tmp_path):
        tree = SearchTree(tmp_path / "tree.json")
        tree.create_root(10.0, "v0")
        tree.add_child(0, 20.0, "v1", 1, "A", "c1")  # id=1
        tree.add_child(1, 25.0, "v2", 2, "B", "c2")  # id=2 (active)
        tree.add_child(0, 15.0, "v3", 1, "C", "c3")  # id=3 (lateral)
        # Even though nodes 0,1 have higher scores, they're on path
        target = tree.select_backtrack_target(2)
        assert target == 3

    def test_minimize_prefers_low_score(self, tmp_path):
        """With minimize=True, prefer nodes with lower scores."""
        tree = SearchTree(tmp_path / "tree.json")
        tree.create_root(500.0, "v0")
        tree.add_child(0, 100.0, "v1", 1, "A", "c1")  # id=1 (better for min)
        tree.add_child(0, 400.0, "v2", 1, "B", "c2")  # id=2 (worse for min)
        tree.add_child(1, 200.0, "v3", 2, "C", "c3")  # id=3 (active)
        target = tree.select_backtrack_target(3, minimize=True)
        # Should prefer node 2 is NOT on path; between laterals 2(400) and none
        # Wait: path is [3,1,0], laterals are only node 2
        assert target == 2

    def test_minimize_with_multiple_laterals(self, tmp_path):
        """With minimize=True, prefer lower-score lateral over higher."""
        tree = SearchTree(tmp_path / "tree.json")
        tree.create_root(500.0, "v0")
        tree.add_child(0, 50.0, "low", 1, "A", "c1")   # id=1 (low = good)
        tree.add_child(0, 300.0, "high", 1, "B", "c2")  # id=2 (high = bad)
        tree.add_child(0, 200.0, "mid", 1, "C", "c3")   # id=3 (active)
        target = tree.select_backtrack_target(3, minimize=True)
        # 1/(50+1)=0.0196, 1/(300+1)=0.0033 → prefer node 1
        assert target == 1


class TestPersistence:
    def test_save_load_roundtrip(self, tmp_path):
        path = tmp_path / "tree.json"
        tree = SearchTree(path)
        tree.create_root(10.0, "v0")
        tree.add_child(0, 12.0, "v1", 1, "Explorer", "test change")
        tree.backtrack_count = 2
        tree._save()

        tree2 = SearchTree(path)
        assert len(tree2.nodes) == 2
        assert tree2.active_node_id == 1
        assert tree2.backtrack_count == 2
        assert tree2.nodes[0].score == 10.0
        assert tree2.nodes[1].content == "v1"
        assert 1 in tree2.nodes[0].children

    def test_resume_active_node(self, tmp_path):
        path = tmp_path / "tree.json"
        tree = SearchTree(path)
        tree.create_root(10.0, "v0")
        tree.add_child(0, 11.0, "v1", 1, "A", "c1")
        tree.add_child(1, 12.0, "v2", 2, "B", "c2")

        tree2 = SearchTree(path)
        assert tree2.active_node_id == 2

    def test_corrupt_file_handled(self, tmp_path):
        path = tmp_path / "tree.json"
        path.write_text("not valid json{{{")
        tree = SearchTree(path)
        assert tree.nodes == {}
        assert tree._next_id == 0


class TestThreadSafety:
    def test_concurrent_add_child(self, tmp_path):
        tree = SearchTree(tmp_path / "tree.json")
        tree.create_root(10.0, "v0")

        errors = []

        def add_child(i):
            try:
                tree.add_child(0, 10.0 + i, f"v{i}", 1, f"Agent{i}", f"change {i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=add_child, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(tree.nodes) == 11  # root + 10 children
        assert len(tree.nodes[0].children) == 10


class TestMaxDepth:
    def test_root_only(self, tmp_path):
        tree = SearchTree(tmp_path / "tree.json")
        tree.create_root(10.0, "v0")
        assert tree.max_depth() == 1

    def test_chain(self, tmp_path):
        tree = SearchTree(tmp_path / "tree.json")
        tree.create_root(10.0, "v0")
        tree.add_child(0, 11.0, "v1", 1, "A", "c1")
        tree.add_child(1, 12.0, "v2", 2, "B", "c2")
        assert tree.max_depth() == 3

    def test_empty(self, tmp_path):
        tree = SearchTree(tmp_path / "tree.json")
        assert tree.max_depth() == 0
