"""
SwarmResearch Engine v0.6.1

Autonomous multi-agent optimization framework.
Multi-file targets, backtracking/tree search, resume, phase-aware prompting.
"""

import json
import os
import re
import signal
import subprocess
import shutil
import threading
from typing import Optional, List, Dict
from dataclasses import dataclass, asdict, field
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Load .env from engine's directory if available
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    agent: str
    round: int
    experiment: int
    score: float
    baseline: float
    delta: float
    kept: bool
    reasoning: str
    description: str
    change_summary: str
    timestamp: str


@dataclass
class AgentConfig:
    name: str
    strategy: str
    temperature: float = 0.7


DEFAULT_AGENTS = [
    AgentConfig(
        "Explorer",
        "Try bold, creative changes. Explore unconventional approaches that "
        "other agents haven't tried. Rewrite entire sections if you see a better way. "
        "If the board shows everyone trying similar fixes — go in a COMPLETELY different direction.",
        0.9,
    ),
    AgentConfig(
        "Optimizer",
        "Make careful, incremental improvements. Focus on refining what already works. "
        "Small precise changes, one at a time. If something was kept — try to refine it further. "
        "If nothing was kept yet — try the smallest possible change.",
        0.3,
    ),
    AgentConfig(
        "Synthesizer",
        "Your unique skill: COMBINE ideas. Read the board carefully. "
        "If there are kept improvements — combine them. "
        "If all experiments failed — analyze WHY they failed and try the opposite approach. "
        "If the board is empty — act as a careful experimenter, try something safe first.",
        0.6,
    ),
]


# ---------------------------------------------------------------------------
# Search Tree — state tree for backtracking
# ---------------------------------------------------------------------------

@dataclass
class TreeNode:
    id: int
    parent_id: Optional[int]
    score: float
    content: object  # str (legacy single-file) or Dict[str, str] (multi-file)
    content_hash: str
    round_created: int
    agent: str
    change_summary: str
    children: List[int] = field(default_factory=list)
    visits: int = 0
    abandoned: bool = False


class SearchTree:
    """Tree of file states for backtracking. Persisted to tree.json."""

    def __init__(self, path):
        self.path = Path(path)
        self._lock = threading.Lock()
        self.nodes = {}  # type: Dict[int, TreeNode]
        self._next_id = 0
        self.active_node_id = 0
        self.backtrack_count = 0
        if self.path.exists():
            self._load()

    @staticmethod
    def _content_hash(content):
        import hashlib
        if isinstance(content, dict):
            combined = "".join(f"{k}:{v}" for k, v in sorted(content.items()))
        else:
            combined = content
        return hashlib.sha256(combined.encode()).hexdigest()[:16]

    def _save(self):
        data = {
            "active_node_id": self.active_node_id,
            "backtrack_count": self.backtrack_count,
            "next_id": self._next_id,
            "nodes": {str(k): asdict(v) for k, v in self.nodes.items()},
        }
        self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def _load(self):
        try:
            raw = json.loads(self.path.read_text())
            self.active_node_id = raw["active_node_id"]
            self.backtrack_count = raw.get("backtrack_count", 0)
            self._next_id = raw["next_id"]
            for k, v in raw["nodes"].items():
                self.nodes[int(k)] = TreeNode(**v)
        except (json.JSONDecodeError, KeyError, TypeError):
            self.nodes = {}
            self._next_id = 0

    def create_root(self, score, content):
        with self._lock:
            node = TreeNode(
                id=0, parent_id=None, score=score, content=content,
                content_hash=self._content_hash(content),
                round_created=0, agent="baseline",
                change_summary="baseline",
            )
            self.nodes[0] = node
            self._next_id = 1
            self.active_node_id = 0
            self._save()
            return 0

    def add_child(self, parent_id, score, content, round_created, agent, change_summary):
        with self._lock:
            node_id = self._next_id
            self._next_id += 1
            node = TreeNode(
                id=node_id, parent_id=parent_id, score=score,
                content=content, content_hash=self._content_hash(content),
                round_created=round_created, agent=agent,
                change_summary=change_summary,
            )
            self.nodes[node_id] = node
            self.nodes[parent_id].children.append(node_id)
            self.active_node_id = node_id
            self._save()
            return node_id

    def record_visit(self, node_id):
        with self._lock:
            self.nodes[node_id].visits += 1
            self._save()

    def mark_abandoned(self, node_id):
        with self._lock:
            self.nodes[node_id].abandoned = True
            self._save()

    def get_path_to_root(self, node_id):
        path = []
        current = node_id
        while current is not None:
            path.append(current)
            current = self.nodes[current].parent_id
        return list(reversed(path))

    def get_abandoned_paths_summary(self):
        abandoned = [n for n in self.nodes.values() if n.abandoned]
        if not abandoned:
            return ""
        lines = ["Abandoned branches:"]
        for n in abandoned:
            path = self.get_path_to_root(n.id)
            path_str = " -> ".join(
                f"{self.nodes[p].agent}({self.nodes[p].score:.4f})" for p in path
            )
            lines.append(f"  {path_str} [abandoned at score={n.score:.4f}]")
        return "\n".join(lines)

    def select_backtrack_target(self, current_id, minimize=False):
        """Select best node to backtrack to. Returns node_id or None."""
        current_path = set(self.get_path_to_root(current_id))

        # Score lateral candidates (not on current path)
        candidates = []
        for node in self.nodes.values():
            if node.id in current_path:
                continue
            penalty = 0.3 if node.abandoned else 1.0
            raw = 1.0 / (node.score + 1) if minimize else node.score
            node_score = raw * (1 / (1 + node.visits)) * penalty
            candidates.append((node.id, node_score))

        if candidates:
            candidates.sort(key=lambda x: x[1], reverse=True)
            return candidates[0][0]

        # Fallback: ancestor with < 3 children (excluding current node)
        path = self.get_path_to_root(current_id)
        for node_id in reversed(path[:-1]):
            if len(self.nodes[node_id].children) < 3:
                return node_id

        return None

    def max_depth(self):
        if not self.nodes:
            return 0
        max_d = 0
        for node_id in self.nodes:
            d = len(self.get_path_to_root(node_id))
            if d > max_d:
                max_d = d
        return max_d


def load_agent_prompts(work_dir):
    # type: (Path) -> Optional[object]
    for search_dir in [work_dir, work_dir.parent]:
        prompts_file = search_dir / "agent_prompts.py"
        if prompts_file.exists():
            import importlib.util
            spec = importlib.util.spec_from_file_location("agent_prompts", prompts_file)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    return None


# ---------------------------------------------------------------------------
# Board — shared knowledge (thread-safe for parallel agents)
# ---------------------------------------------------------------------------

class Board:
    def __init__(self, path):
        # type: (Path) -> None
        self.path = path
        self.findings = []  # type: List[Finding]
        self.meta = {}  # type: dict
        self._lock = threading.Lock()
        if self.path.exists():
            try:
                raw = json.loads(self.path.read_text())
                if isinstance(raw, dict):
                    self.meta = raw.get("meta", {})
                    self.findings = [Finding(**f) for f in raw.get("findings", [])]
                elif isinstance(raw, list):
                    # backward compat: old format was a plain list
                    self.findings = [Finding(**f) for f in raw]
            except (json.JSONDecodeError, TypeError):
                self.findings = []

    def _save(self):
        self.path.write_text(json.dumps(
            {"meta": self.meta, "findings": [asdict(f) for f in self.findings]},
            indent=2, ensure_ascii=False,
        ))

    def add(self, finding):
        # type: (Finding) -> None
        with self._lock:
            self.findings.append(finding)
            self._save()

    def summary(self, last_n=20):
        # type: (int) -> str
        with self._lock:
            return self._summary_unlocked(last_n)

    def _summary_unlocked(self, last_n=20):
        if not self.findings:
            return "No experiments yet. You are the first — try something safe and informative."

        kept = [f for f in self.findings if f.kept]
        failed = [f for f in self.findings if not f.kept]
        lines = []

        if kept:
            lines.append("=== KEPT (successful changes) ===")
            for f in kept:
                lines.append(
                    f"  R{f.round} {f.agent}: {f.change_summary[:150]} "
                    f"| score={f.score:.4f} (+{f.delta:.4f})"
                )

        if failed:
            lines.append(f"\n=== REVERTED (DO NOT repeat) [{len(failed)} total] ===")
            for f in failed[-last_n:]:
                lines.append(
                    f"  R{f.round} {f.agent}: {f.change_summary[:150]} "
                    f"| score={f.score:.4f} ({f.delta:+.4f})"
                )

        if kept:
            best = max(kept, key=lambda f: f.delta)
            lines.append(
                f"\nBest: {best.agent} R{best.round} "
                f"(score={best.score:.4f}, +{best.delta:.4f})"
            )

        if len(failed) >= 3:
            lines.append(
                f"\n*** {len(failed)} failed. Try something DIFFERENT. ***"
            )

        return "\n".join(lines)

    def failed_approaches(self):
        # type: () -> List[str]
        with self._lock:
            return [f.change_summary for f in self.findings if not f.kept]


# ---------------------------------------------------------------------------
# Agent memory — per-agent persistent storage
# ---------------------------------------------------------------------------

class AgentMemory:
    """Per-agent persistent memory. Stores detailed experiment history to disk."""

    def __init__(self, memory_dir):
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(exist_ok=True)
        self._lock = threading.Lock()

    def _path(self, agent_name):
        return self.memory_dir / f"{agent_name}.json"

    def load(self, agent_name):
        path = self._path(agent_name)
        if path.exists():
            try:
                return json.loads(path.read_text())
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    def add(self, agent_name, entry):
        with self._lock:
            entries = self.load(agent_name)
            entries.append(entry)
            self._path(agent_name).write_text(
                json.dumps(entries, indent=2, ensure_ascii=False)
            )

    def format_for_prompt(self, agent_name, last_n=10):
        entries = self.load(agent_name)
        if not entries:
            return "No experiments yet."
        lines = []
        for e in entries[-last_n:]:
            status = "KEPT" if e["kept"] else "REVERTED"
            lines.append(
                f"R{e['round']} [{status}] score={e['score']:.4f} delta={e['delta']:+.4f}"
                f"\n  {e['reasoning'][:200]}"
            )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Task parser
# ---------------------------------------------------------------------------

def parse_task(task_path):
    # type: (Path) -> dict
    text = task_path.read_text()
    config = {}
    body = text

    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].strip().split("\n"):
                if ":" in line:
                    key, val = line.split(":", 1)
                    val = val.strip()
                    if val.startswith("[") and val.endswith("]"):
                        val = [item.strip() for item in val[1:-1].split(",")]
                    config[key.strip()] = val
            body = parts[2].strip()

    config["description"] = body
    return config


# ---------------------------------------------------------------------------
# Eval runner
# ---------------------------------------------------------------------------

def run_eval_once(eval_cmd, work_dir, timeout=300):
    # type: (str, Path, int) -> Optional[float]
    try:
        # Use process group so we can kill the entire tree on timeout
        # (shell=True spawns a shell that may fork children — plain
        #  subprocess.run(timeout=) only kills the shell, not children)
        proc = subprocess.Popen(
            eval_cmd, shell=True, cwd=work_dir,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            preexec_fn=os.setsid,
        )
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            # Kill the entire process group
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            proc.wait()
            print(f"    eval TIMEOUT ({timeout}s)")
            return None

        if proc.returncode != 0:
            stderr_tail = stderr[-500:] if stderr else ""
            print(f"    eval error: {stderr_tail}")
            return None

        # Prefer explicit SCORE: marker, fallback to last number in output
        for line in reversed(stdout.strip().split("\n")):
            score_match = re.search(r"SCORE:\s*([-+]?\d*\.?\d+)", line.strip())
            if score_match:
                return float(score_match.group(1))

        for line in reversed(stdout.strip().split("\n")):
            match = re.search(r"[-+]?\d*\.?\d+", line.strip())
            if match:
                return float(match.group())

        return None
    except Exception as e:
        print(f"    eval exception: {e}")
        return None


def run_eval(eval_cmd, work_dir, timeout=300, runs=1):
    # type: (str, Path, int, int) -> Optional[float]
    scores = []
    for _ in range(runs):
        s = run_eval_once(eval_cmd, work_dir, timeout)
        if s is not None:
            scores.append(s)
    if not scores:
        return None
    scores.sort()
    mid = len(scores) // 2
    if len(scores) % 2 == 0 and len(scores) > 1:
        return (scores[mid - 1] + scores[mid]) / 2
    return scores[mid]


# ---------------------------------------------------------------------------
# LLM client
# ---------------------------------------------------------------------------

_llm_clients = {}  # type: Dict[str, object]
_llm_clients_lock = threading.Lock()


def _get_llm_client():
    """Get or create a cached LLM client. Thread-safe."""
    provider = os.environ.get("LLM_PROVIDER", "anthropic")
    if provider not in _llm_clients:
        with _llm_clients_lock:
            if provider not in _llm_clients:  # double-check after lock
                if provider == "anthropic":
                    from anthropic import Anthropic
                    kwargs = {"api_key": os.environ["LLM_API_KEY"]}
                    if os.environ.get("LLM_BASE_URL"):
                        kwargs["base_url"] = os.environ["LLM_BASE_URL"]
                    _llm_clients[provider] = Anthropic(**kwargs)
                else:
                    from openai import OpenAI
                    _llm_clients[provider] = OpenAI(
                        base_url=os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1"),
                        api_key=os.environ.get("LLM_API_KEY", ""),
                    )
    return _llm_clients[provider]


def call_llm(messages, temperature, max_tokens=16000):
    # type: (List[dict], float, int) -> str
    provider = os.environ.get("LLM_PROVIDER", "anthropic")
    client = _get_llm_client()

    if provider == "anthropic":
        system = ""
        user_msgs = []
        for m in messages:
            if m["role"] == "system":
                system = m["content"]
            else:
                user_msgs.append(m)
        resp = client.messages.create(
            model=os.environ.get("LLM_MODEL", "claude-sonnet-4-20250514"),
            max_tokens=max_tokens, system=system,
            messages=user_msgs, temperature=temperature,
        )
        return resp.content[0].text
    else:
        resp = client.chat.completions.create(
            model=os.environ.get("LLM_MODEL", "gpt-4o-mini"),
            messages=messages, temperature=temperature, max_tokens=max_tokens,
        )
        return resp.choices[0].message.content


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

DIFF_SYSTEM_TEMPLATE = """You are {agent_name}, an AI research agent in a swarm optimization team.

Your strategy: {agent_strategy}

You modify a target file to improve a measurable score. If the score improves, your
change is kept; otherwise it is reverted.

RESPONSE FORMAT — use SEARCH/REPLACE blocks to describe changes:

```diff
<<<< SEARCH
exact lines from the current file to find
====
replacement lines
>>>> REPLACE
```

RULES:
1. Write 2-3 sentences explaining WHAT you changed and WHY before the diff blocks.
2. Make ONE conceptual change per experiment (can be multiple SEARCH/REPLACE blocks).
3. SEARCH text must match the file EXACTLY (including whitespace and indentation).
4. NEVER repeat failed approaches from the board.
5. If many experiments failed — try something radically different.
{failed_block}"""

FULL_SYSTEM_TEMPLATE = """You are {agent_name}, an AI research agent in a swarm optimization team.

Your strategy: {agent_strategy}

You modify a target file to improve a measurable score. If the score improves, your
change is kept; otherwise it is reverted.

RULES:
1. Output the COMPLETE modified file between ```file and ``` markers.
2. Before the file, write 2-3 sentences explaining WHAT you changed and WHY.
3. Make ONE conceptual change per experiment.
4. NEVER repeat failed approaches from the board.
5. If many experiments failed — try something radically different.
{failed_block}"""

USER_TEMPLATE = """## Task
{task_desc}

## Current file: {target_name}
```
{target_content}
```

## Board (shared findings from all agents)
{board_summary}

## Your experiment memory
{memory_text}

{phase_hint}
{backtrack_context}
Experiment #{experiment_num}. Propose your next change."""

USER_TEMPLATE_MULTI = """## Task
{task_desc}

## Target files
{target_files_block}

## Board (shared findings from all agents)
{board_summary}

## Your experiment memory
{memory_text}

{phase_hint}
{backtrack_context}
Experiment #{experiment_num}. Propose your next change."""


def build_prompt(agent, task_desc, target_contents, board, memory_text,
                 experiment_num, use_diff=False, phase_hint="",
                 backtrack_context="", disable_board=False):
    # type: (AgentConfig, str, Dict[str, str], Board, str, int, bool, str, str, bool) -> List[dict]

    keys = list(target_contents.keys())
    is_multi = len(keys) > 1

    failed_list = [] if disable_board else board.failed_approaches()
    failed_block = ""
    if failed_list:
        failed_block = "\nDO NOT try these (already failed):\n" + \
            "\n".join(f"- {a[:120]}" for a in failed_list)

    sys_template = DIFF_SYSTEM_TEMPLATE if use_diff else FULL_SYSTEM_TEMPLATE
    system = sys_template.format(
        agent_name=agent.name, agent_strategy=agent.strategy,
        failed_block=failed_block,
    )

    if is_multi:
        if use_diff:
            system += ("\n\nMULTI-FILE TARGET: Add the file path after SEARCH:\n"
                       "<<<< SEARCH path/to/file.py\n"
                       "If no path is given, the first file is assumed.")
        else:
            system += ("\n\nMULTI-FILE TARGET: Label each modified file block:\n"
                       "```file:path/to/file.py\n...\n```\n"
                       "Only output files you changed. Unchanged files are kept as-is.")

    if is_multi:
        files_block = ""
        for key in keys:
            files_block += f"\n### {key}\n```\n{target_contents[key]}```\n"
        user = USER_TEMPLATE_MULTI.format(
            task_desc=task_desc, target_files_block=files_block,
            board_summary="" if disable_board else board.summary(),
            memory_text=memory_text,
            phase_hint=phase_hint, backtrack_context=backtrack_context,
            experiment_num=experiment_num,
        )
    else:
        key = keys[0]
        user = USER_TEMPLATE.format(
            task_desc=task_desc, target_name=key,
            target_content=target_contents[key],
            board_summary="" if disable_board else board.summary(),
            memory_text=memory_text, phase_hint=phase_hint,
            backtrack_context=backtrack_context, experiment_num=experiment_num,
        )

    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

def strip_think_tags(text):
    # type: (str) -> str
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def apply_diffs(originals, response):
    # type: (Dict[str, str], str) -> Optional[Dict[str, str]]
    """Apply SEARCH/REPLACE diff blocks to original contents.

    Args:
        originals: Dict mapping rel_path -> content
        response: LLM response text

    Returns Dict with applied changes, or None if no valid changes.
    """
    cleaned = strip_think_tags(response)

    # Find all SEARCH/REPLACE blocks with optional file path
    pattern = r"<<<<\s*SEARCH\s*([\w/.\-]*)\s*\n(.*?)\n====\s*\n(.*?)\n>>>>\s*REPLACE"
    blocks = re.findall(pattern, cleaned, re.DOTALL)

    if not blocks:
        return None

    result = dict(originals)
    keys = list(originals.keys())

    for filepath, search, replace in blocks:
        filepath = filepath.strip()
        if not filepath:
            filepath = keys[0]

        if filepath not in result:
            print(f"    diff error: unknown file {filepath!r}")
            return None

        search = search.rstrip("\n")
        replace = replace.rstrip("\n")
        content = result[filepath]

        if search in content:
            result[filepath] = content.replace(search, replace, 1)
        else:
            # Try fuzzy match: strip trailing whitespace per line
            search_stripped = "\n".join(l.rstrip() for l in search.split("\n"))
            content_lines = content.split("\n")
            found = False
            for i in range(len(content_lines)):
                candidate_lines = content_lines[i:i + search.count("\n") + 1]
                candidate = "\n".join(l.rstrip() for l in candidate_lines)
                if candidate == search_stripped:
                    new_lines = (content_lines[:i] +
                                replace.split("\n") +
                                content_lines[i + len(candidate_lines):])
                    result[filepath] = "\n".join(new_lines)
                    found = True
                    break
            if not found:
                print(f"    diff mismatch in {filepath}: {search[:80]!r}")
                return None

    if all(result[k] == originals[k] for k in originals):
        return None

    return result


def extract_file_content(response):
    # type: (str) -> Optional[str]
    cleaned = strip_think_tags(response)
    match = re.search(r"```file\s*\n(.*?)```", cleaned, re.DOTALL)
    if match:
        return match.group(1)
    match = re.search(r"```(?:python|javascript|yaml|json|txt|sh|toml|py)?\s*\n(.*?)```", cleaned, re.DOTALL)
    if match:
        return match.group(1)
    blocks = re.findall(r"```\w*\s*\n(.*?)```", cleaned, re.DOTALL)
    if blocks:
        return max(blocks, key=len)
    return None


def extract_file_contents(originals, response):
    # type: (Dict[str, str], str) -> Optional[Dict[str, str]]
    """Extract full-file contents from LLM response (multi-file aware).

    Looks for ```file:path blocks first, falls back to single-file extraction.
    Returns merged Dict with originals for unchanged files, or None.
    """
    cleaned = strip_think_tags(response)
    keys = list(originals.keys())

    # Try ```file:path blocks (multi-file format)
    file_blocks = re.findall(r"```file:(\S+)\s*\n(.*?)```", cleaned, re.DOTALL)
    if file_blocks:
        result = dict(originals)
        for path, content in file_blocks:
            if path in result:
                result[path] = content
        if all(result[k] == originals[k] for k in originals):
            return None
        return result

    # Single-file fallback
    if len(keys) == 1:
        content = extract_file_content(response)
        if content:
            return {keys[0]: content}

    return None


def extract_reasoning(response):
    # type: (str) -> str
    cleaned = strip_think_tags(response)
    # Find first code/diff block
    match = re.search(r"(?:```|<<<<)", cleaned)
    if match:
        return cleaned[:match.start()].strip()[:500]
    return cleaned[:500]


def extract_change_summary(reasoning):
    # type: (str) -> str
    for sep in [". ", ".\n", "\n"]:
        idx = reasoning.find(sep)
        if 10 < idx < 200:
            return reasoning[:idx].strip()
    return reasoning[:100].strip()


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def git(work_dir, *args):
    return subprocess.run(
        ["git"] + list(args), cwd=work_dir, capture_output=True, text=True,
    )

def _ensure_gitignore(work_dir):
    gitignore = work_dir / ".gitignore"
    needed = {"board.json", "agent_memory/", "report.md", "tree.json"}
    if gitignore.exists():
        existing = set(gitignore.read_text().splitlines())
        missing = needed - existing
        if missing:
            with gitignore.open("a") as f:
                f.write("\n" + "\n".join(sorted(missing)) + "\n")
    else:
        gitignore.write_text("\n".join(sorted(needed)) + "\n")

def git_init(work_dir):
    _ensure_gitignore(work_dir)
    if not (work_dir / ".git").exists():
        git(work_dir, "init")
        git(work_dir, "add", "-A")
        git(work_dir, "commit", "-m", "baseline")

def git_commit(work_dir, message):
    git(work_dir, "add", "-A")
    git(work_dir, "commit", "-m", message)


# ---------------------------------------------------------------------------
# SwarmEngine
# ---------------------------------------------------------------------------

_EVAL_COPY_EXCLUDE = {
    ".git", "board.json", "agent_memory", "tree.json",
    "__pycache__", ".venv", "venv", "node_modules", ".mypy_cache",
    ".pytest_cache", ".ruff_cache",
}


class SwarmEngine:
    def __init__(self, task_path):
        # type: (str) -> None
        self.task_path = Path(task_path).resolve()
        self.work_dir = self.task_path.parent
        self.task = parse_task(self.task_path)

        raw_target = self.task.get("target", "target/main.txt")
        if isinstance(raw_target, list):
            self.target_files = [self.work_dir / t for t in raw_target]
        else:
            self.target_files = [self.work_dir / raw_target]
        self.eval_cmd = self.task.get("eval", "python eval.py")
        self.direction = self.task.get("direction", "maximize")
        target_names = sorted(str(f.relative_to(self.work_dir)) for f in self.target_files)
        self._task_fingerprint = f"{'|'.join(target_names)}|{self.eval_cmd}|{self.direction}"
        self.rounds = int(self.task.get("rounds", "10"))
        self.timeout = int(self.task.get("timeout", "300"))
        self.eval_runs = int(self.task.get("eval_runs", "1"))

        # diff mode for files > 50 lines
        mode = self.task.get("mode", "auto")
        total_lines = sum(f.read_text().count("\n") for f in self.target_files if f.exists())
        self.use_diff = mode == "diff" or (mode == "auto" and total_lines > 50)

        # parallel mode
        self.parallel = self.task.get("parallel", "false").lower() == "true"

        self.board = Board(self.work_dir / "board.json")
        self.memory = AgentMemory(self.work_dir / "agent_memory")

        prompt_module = load_agent_prompts(self.work_dir)
        if prompt_module and hasattr(prompt_module, "AGENTS"):
            self.agents = prompt_module.AGENTS
        else:
            self.agents = DEFAULT_AGENTS

        self.baseline_score = None  # type: Optional[float]
        self.best_score = None  # type: Optional[float]
        self.experiment_count = 0
        self.stale_rounds = 0  # consecutive rounds without improvement
        self.early_stop = int(self.task.get("early_stop", "0"))  # 0 = disabled
        self.disable_board = False

        # backtracking / tree search
        self.backtrack = int(self.task.get("backtrack", "0"))
        self.max_backtracks = int(self.task.get("max_backtracks", "5"))
        self.backtrack_count = 0
        self.tree = None  # type: Optional[SearchTree]
        self.global_best_score = None  # type: Optional[float]
        self.global_best_content = None  # type: Optional[Dict[str, str]]

        if self.backtrack > 0 and 0 < self.early_stop <= self.backtrack:
            print(f"WARNING: early_stop ({self.early_stop}) <= backtrack ({self.backtrack}). "
                  f"Early stopping may trigger before backtracking.")

        self.no_report = False
        self.start_round = 1
        self._lock = threading.Lock()  # for parallel mode

    def is_better(self, new, old):
        if self.direction == "minimize":
            return new < old
        return new > old

    def _read_targets(self):
        # type: () -> Dict[str, str]
        """Read all target files. Returns Dict[rel_path, content]."""
        return {str(f.relative_to(self.work_dir)): f.read_text() for f in self.target_files}

    def _write_targets(self, contents):
        # type: (Dict[str, str]) -> None
        """Write target file contents. contents: Dict[rel_path, content]."""
        for rel_path, content in contents.items():
            path = self.work_dir / rel_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)

    def _phase_hint(self, round_num):
        progress = round_num / self.rounds
        if progress <= 0.3:
            phase = "EXPLORATION — early stage, many approaches untested"
        elif progress <= 0.7:
            phase = "DEVELOPMENT — some patterns emerging, build on findings"
        else:
            phase = "REFINEMENT — late stage, diminishing returns expected"
        return f"Round {round_num}/{self.rounds} ({phase}). Adapt your strategy accordingly."

    def _eval(self, work_dir=None):
        wd = work_dir or self.work_dir
        return run_eval(self.eval_cmd, wd, self.timeout, self.eval_runs)

    def _run_single_agent(self, agent, round_num, target_contents):
        # type: (AgentConfig, int, Dict[str, str]) -> Optional[tuple]
        """Run one agent's experiment. Returns (Finding, new_contents) or None."""

        with self._lock:
            self.experiment_count += 1
            exp_num = self.experiment_count
            current_best = self.best_score

        print(f"\n  [{agent.name}] experiment #{exp_num}")

        messages = build_prompt(
            agent, self.task["description"], target_contents,
            self.board,
            self.memory.format_for_prompt(agent.name),
            exp_num, self.use_diff,
            phase_hint=self._phase_hint(round_num),
            backtrack_context=self._backtrack_context(),
            disable_board=self.disable_board,
        )

        # Call LLM
        try:
            reply = call_llm(messages, agent.temperature)
        except Exception as e:
            print(f"    LLM error: {e}")
            return (None, None)

        reasoning = extract_reasoning(reply)
        change_summary = extract_change_summary(reasoning)

        # Apply changes — diff mode or full-file mode
        if self.use_diff:
            new_contents = apply_diffs(target_contents, reply)
            if new_contents is None and "<<<< SEARCH" not in reply:
                # Fallback to full-file only if response isn't a diff
                new_contents = extract_file_contents(target_contents, reply)
        else:
            new_contents = extract_file_contents(target_contents, reply)

        if not new_contents:
            print(f"    could not extract changes from response")
            return (Finding(
                agent=agent.name, round=round_num, experiment=exp_num,
                score=0, baseline=current_best, delta=0,
                kept=False, reasoning=reasoning,
                description=f"PARSE_FAIL: {reasoning[:100]}",
                change_summary="(could not parse response)",
                timestamp=datetime.now().isoformat(),
            ), None)

        if all(new_contents.get(k, "").strip() == v.strip()
               for k, v in target_contents.items()):
            print(f"    no changes proposed")
            return None, None

        if self.parallel:
            finding = self._eval_in_copy(
                agent, round_num, exp_num, target_contents,
                new_contents, reasoning, change_summary, current_best,
            )
        else:
            finding = self._eval_in_place(
                agent, round_num, exp_num, target_contents,
                new_contents, reasoning, change_summary, current_best,
            )
        return (finding, new_contents) if finding else (None, None)

    def _delta(self, score, baseline):
        if self.direction == "minimize":
            return baseline - score
        return score - baseline

    def _crash_finding(self, agent, round_num, exp_num, reasoning, change_summary, current_best):
        return Finding(
            agent=agent.name, round=round_num, experiment=exp_num,
            score=0, baseline=current_best, delta=0,
            kept=False, reasoning=reasoning,
            description=f"CRASH: {reasoning[:100]}",
            change_summary=change_summary,
            timestamp=datetime.now().isoformat(),
        )

    def _record_kept(self, score, contents, round_num, agent_name, change_summary):
        git_commit(self.work_dir, f"R{round_num} {agent_name}: {change_summary[:80]}")
        if self.tree:
            self.tree.add_child(
                self.tree.active_node_id, score, contents,
                round_created=round_num, agent=agent_name,
                change_summary=change_summary,
            )
            if self.global_best_score is None or self.is_better(score, self.global_best_score):
                self.global_best_score = score
                self.global_best_content = contents

    def _eval_in_place(self, agent, round_num, exp_num, target_contents,
                        new_contents, reasoning, change_summary, current_best):
        """Sequential mode: write files, eval, keep or revert."""
        self._write_targets(new_contents)
        score = self._eval()

        if score is None:
            self._write_targets(target_contents)
            print(f"    CRASH  | {change_summary[:80]}")
            return self._crash_finding(agent, round_num, exp_num, reasoning, change_summary, current_best)

        delta = self._delta(score, current_best)
        kept = self.is_better(score, current_best)

        if kept:
            with self._lock:
                self.best_score = score
            self._record_kept(score, new_contents, round_num, agent.name, change_summary)
            print(f"    KEPT     score={score:.4f}  delta={delta:+.4f}")
        else:
            self._write_targets(target_contents)
            print(f"    reverted score={score:.4f}  delta={delta:+.4f}")

        print(f"    change: {change_summary[:100]}")

        return Finding(
            agent=agent.name, round=round_num, experiment=exp_num,
            score=score, baseline=current_best, delta=delta,
            kept=kept, reasoning=reasoning,
            description=reasoning[:200],
            change_summary=change_summary,
            timestamp=datetime.now().isoformat(),
        )

    def _eval_in_copy(self, agent, round_num, exp_num, target_contents,
                       new_contents, reasoning, change_summary, current_best):
        """Parallel mode: eval in a temp directory, merge winner after."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            # Copy work_dir contents (excluding build artifacts)
            for item in self.work_dir.iterdir():
                if item.name in _EVAL_COPY_EXCLUDE:
                    continue
                dest = tmp_path / item.name
                if item.is_dir():
                    shutil.copytree(item, dest,
                                    ignore=shutil.ignore_patterns(
                                        "__pycache__", "node_modules",
                                        ".venv", "venv"))
                else:
                    shutil.copy2(item, dest)

            # Write all modified target files
            for rel_path, content in new_contents.items():
                tmp_target = tmp_path / rel_path
                tmp_target.parent.mkdir(parents=True, exist_ok=True)
                tmp_target.write_text(content)

            score = self._eval(tmp_path)

        if score is None:
            print(f"    [{agent.name}] CRASH  | {change_summary[:80]}")
            return self._crash_finding(agent, round_num, exp_num, reasoning, change_summary, current_best)

        delta = self._delta(score, current_best)
        kept = self.is_better(score, current_best)
        print(f"    [{agent.name}] {'KEPT' if kept else 'reverted':8s} score={score:.4f}  delta={delta:+.4f}")
        print(f"    change: {change_summary[:100]}")

        return Finding(
            agent=agent.name, round=round_num, experiment=exp_num,
            score=score, baseline=current_best, delta=delta,
            kept=kept, reasoning=reasoning,
            description=reasoning[:200],
            change_summary=change_summary,
            timestamp=datetime.now().isoformat(),
        )

    def run(self):
        mode_label = "diff" if self.use_diff else "full-file"
        par_label = "parallel" if self.parallel else "sequential"
        print(f"SwarmResearch Engine v0.6.1 [{mode_label}, {par_label}]")
        print(f"  Task:      {self.task_path}")
        if len(self.target_files) == 1:
            print(f"  Target:    {self.target_files[0]}")
        else:
            print(f"  Targets:   {', '.join(str(f) for f in self.target_files)}")
        print(f"  Eval:      {self.eval_cmd}")
        print(f"  Direction: {self.direction}")
        print(f"  Rounds:    {self.rounds}")
        print(f"  Eval runs: {self.eval_runs}")
        print(f"  Agents:    {', '.join(a.name for a in self.agents)}")
        print()

        # Eval current state
        print(f"Evaluating current state ({self.eval_runs} runs)...")
        current_score = self._eval()
        if current_score is None:
            print("ERROR: eval failed.")
            return

        # Resume from previous run if board has findings
        if self.board.findings:
            old_fp = self.board.meta.get("task")
            if old_fp and old_fp != self._task_fingerprint:
                print(f"Board is from a different task. Clearing stale data.")
                self.board.findings.clear()
                self.board.meta.clear()
                self.board._save()
                # also clear agent memory
                if self.memory.memory_dir.exists():
                    shutil.rmtree(self.memory.memory_dir)
                    self.memory.memory_dir.mkdir(exist_ok=True)

        if self.board.findings:
            self.start_round = max(f.round for f in self.board.findings) + 1
            self.experiment_count = len(self.board.findings)
            self.baseline_score = self.board.findings[0].baseline
            self.best_score = current_score
            if self.start_round > self.rounds:
                print(f"Previous run completed all {self.rounds} rounds. Nothing to do.")
                print(f"  Delete board.json to start fresh, or increase --rounds.")
                self._print_report()
                return
            print(f"Resuming from round {self.start_round}")
            print(f"  Original baseline: {self.baseline_score:.4f}")
            print(f"  Current best:      {self.best_score:.4f}")
            print(f"  Previous experiments: {self.experiment_count}")
        else:
            self.baseline_score = current_score
            self.best_score = current_score
            self.board.meta["task"] = self._task_fingerprint
            self.board._save()
            print(f"Baseline: {self.baseline_score:.4f}")
        print()

        git_init(self.work_dir)

        # Initialize search tree for backtracking
        if self.backtrack > 0:
            tree_path = self.work_dir / "tree.json"
            current_contents = self._read_targets()
            if tree_path.exists() and self.board.findings:
                self.tree = SearchTree(tree_path)
                self.backtrack_count = self.tree.backtrack_count
                # Migrate old string content to dict format
                first_key = list(current_contents.keys())[0]
                for node in self.tree.nodes.values():
                    if isinstance(node.content, str):
                        node.content = {first_key: node.content}
                        node.content_hash = SearchTree._content_hash(node.content)
                self.tree._save()
                current_hash = SearchTree._content_hash(current_contents)
                active_node = self.tree.nodes.get(self.tree.active_node_id)
                if active_node and active_node.content_hash != current_hash:
                    print(f"  Tree hash mismatch, rebuilding tree.")
                    tree_path.unlink()
                    self.tree = SearchTree(tree_path)
                    self.tree.create_root(self.best_score, current_contents)
                else:
                    print(f"  Resumed tree: {len(self.tree.nodes)} nodes, "
                          f"{self.backtrack_count} backtracks")
            else:
                self.tree = SearchTree(tree_path)
                self.tree.create_root(self.best_score, current_contents)
            self.global_best_score = self.best_score
            self.global_best_content = current_contents

        for round_num in range(self.start_round, self.rounds + 1):
            print(f"{'=' * 60}")
            print(f"ROUND {round_num}/{self.rounds}  |  best = {self.best_score:.4f}")
            print(f"{'=' * 60}")

            score_before = self.best_score
            target_contents = self._read_targets()

            if self.parallel:
                self._run_round_parallel(round_num, target_contents)
            else:
                self._run_round_sequential(round_num, target_contents)

            # Early stopping: track consecutive rounds without improvement
            improved = self.is_better(self.best_score, score_before)
            if improved:
                self.stale_rounds = 0
            else:
                self.stale_rounds += 1

            # Backtracking: try different branch if stuck
            if (self.backtrack > 0 and self.stale_rounds >= self.backtrack
                    and self.backtrack_count < self.max_backtracks):
                if self._do_backtrack(round_num):
                    self.stale_rounds = 0
                    continue

            if self.early_stop and self.stale_rounds >= self.early_stop:
                print(f"\n  Early stop: {self.stale_rounds} rounds without improvement.")
                break

        # Restore global best if it's better than current
        if self.tree and self.global_best_content is not None:
            if self.is_better(self.global_best_score, self.best_score):
                self._write_targets(self.global_best_content)
                self.best_score = self.global_best_score
                git_commit(self.work_dir,
                           f"Restore global best ({self.global_best_score:.4f})")
                print(f"\n  Restored global best: {self.global_best_score:.4f}")

        # Report
        self._print_report()
        self._generate_report()

    def _run_round_sequential(self, round_num, target_contents):
        """Run agents one by one. Each builds on the previous kept changes."""
        if self.tree:
            self.tree.record_visit(self.tree.active_node_id)
        for agent in self.agents:
            target_contents = self._read_targets()  # re-read after possible keeps
            finding, _ = self._run_single_agent(agent, round_num, target_contents)
            if finding:
                self.board.add(finding)
                self._save_agent_memory(finding)

    def _run_round_parallel(self, round_num, target_contents):
        """Run all agents in parallel. Best result wins the round."""
        if self.tree:
            self.tree.record_visit(self.tree.active_node_id)
        results = []  # list of (finding, new_contents)

        with ThreadPoolExecutor(max_workers=len(self.agents)) as pool:
            futures = {
                pool.submit(self._run_single_agent, agent, round_num, target_contents): agent
                for agent in self.agents
            }
            for future in as_completed(futures):
                agent = futures[future]
                try:
                    result = future.result()
                    if result and result[0]:
                        results.append(result)
                except Exception as e:
                    print(f"    [{agent.name}] error: {e}")

        # Pick the best among candidates that improved
        candidates = [(f, c) for f, c in results if f.kept and c]

        if candidates:
            winner_finding, winner_contents = max(candidates, key=lambda x: x[0].delta)
            print(f"\n  >> Round winner: {winner_finding.agent} (delta={winner_finding.delta:+.4f})")

            self._write_targets(winner_contents)
            with self._lock:
                self.best_score = winner_finding.score
            self._record_kept(winner_finding.score, winner_contents, round_num,
                              winner_finding.agent, winner_finding.change_summary)

            for f, _ in results:
                f_copy = Finding(**asdict(f))
                f_copy.kept = (f is winner_finding)
                self.board.add(f_copy)
                self._save_agent_memory(f_copy)
        else:
            # All failed
            for f, _ in results:
                self.board.add(f)
                self._save_agent_memory(f)

    def _save_agent_memory(self, finding):
        self.memory.add(finding.agent, {
            "round": finding.round, "experiment": finding.experiment,
            "score": finding.score, "delta": finding.delta,
            "kept": finding.kept, "reasoning": finding.reasoning[:300],
            "change_summary": finding.change_summary,
        })

    def _do_backtrack(self, round_num):
        """Try to backtrack to a better starting point. Returns True if successful."""
        if not self.tree:
            return False

        current_id = self.tree.active_node_id
        target_id = self.tree.select_backtrack_target(
            current_id, minimize=(self.direction == "minimize"))
        if target_id is None:
            print(f"\n  Backtrack: no viable targets (search exhausted).")
            return False

        target_node = self.tree.nodes[target_id]
        current_node = self.tree.nodes[current_id]

        self.tree.mark_abandoned(current_id)

        self._write_targets(target_node.content)
        self.best_score = target_node.score

        self.tree.active_node_id = target_id
        self.backtrack_count += 1
        self.tree.backtrack_count = self.backtrack_count
        self.tree._save()

        git_commit(self.work_dir,
                   f"BACKTRACK #{self.backtrack_count}: "
                   f"{current_node.score:.4f} -> {target_node.score:.4f} "
                   f"(node {current_id} -> {target_id})")

        print(f"\n  BACKTRACK #{self.backtrack_count}: "
              f"score {current_node.score:.4f} -> {target_node.score:.4f}")
        print(f"    from: node {current_id} ({current_node.agent})")
        print(f"    to:   node {target_id} ({target_node.agent})")

        return True

    def _backtrack_context(self):
        """Generate backtrack context for agent prompts."""
        if not self.tree or self.backtrack_count == 0:
            return ""

        path = self.tree.get_path_to_root(self.tree.active_node_id)
        path_str = " -> ".join(
            f"{self.tree.nodes[p].agent}({self.tree.nodes[p].score:.4f})" for p in path
        )

        abandoned_summary = self.tree.get_abandoned_paths_summary()

        lines = [
            f"## Backtracking active ({self.backtrack_count} backtracks so far)",
            f"Current branch: {path_str}",
        ]
        if abandoned_summary:
            lines.append(abandoned_summary)
            lines.append("Try approaches that DIVERGE from the abandoned branches.")

        return "\n".join(lines)

    def _print_report(self):
        print(f"\n{'=' * 60}")
        print("DONE")
        print(f"  Experiments: {self.experiment_count}")
        print(f"  Baseline:    {self.baseline_score:.4f}")
        print(f"  Final best:  {self.best_score:.4f}")
        total_delta = self.best_score - self.baseline_score
        if self.direction == "minimize":
            total_delta = self.baseline_score - self.best_score
        pct = (total_delta / self.baseline_score * 100) if self.baseline_score else 0
        print(f"  Improvement: {total_delta:+.4f} ({pct:+.1f}%)")
        kept_count = len([f for f in self.board.findings if f.kept])
        print(f"  Kept:        {kept_count}/{self.experiment_count}")
        print(f"  Board:       {self.work_dir / 'board.json'}")
        if self.tree:
            print(f"  Tree nodes:  {len(self.tree.nodes)}")
            print(f"  Backtracks:  {self.backtrack_count}")
            print(f"  Max depth:   {self.tree.max_depth()}")
        print(f"{'=' * 60}")

    def _generate_report(self):
        if self.no_report or not self.board.findings:
            return
        kept_count = len([f for f in self.board.findings if f.kept])
        total_delta = self.best_score - self.baseline_score
        if self.direction == "minimize":
            total_delta = self.baseline_score - self.best_score

        prompt = (
            f"Analyze the optimization results and write a brief report.\n\n"
            f"## Task\n{self.task['description']}\n\n"
            f"## Results\n"
            f"- Baseline: {self.baseline_score:.4f}\n"
            f"- Final best: {self.best_score:.4f}\n"
            f"- Improvement: {total_delta:+.4f}\n"
            f"- Total experiments: {self.experiment_count}\n"
            f"- Kept: {kept_count}\n\n"
            f"## All experiments\n{self.board.summary(last_n=100)}\n\n"
            f"Write a brief analysis (3-5 paragraphs):\n"
            f"1. What approaches worked and why?\n"
            f"2. What patterns failed?\n"
            f"3. Key insights for future optimization.\n"
            f"4. Recommendations for next run."
        )

        try:
            print("\nGenerating optimization report...")
            report = call_llm(
                [{"role": "system", "content": "You are an optimization analyst. Be concise and specific."},
                 {"role": "user", "content": prompt}],
                temperature=0.3, max_tokens=2000,
            )
            report_path = self.work_dir / "report.md"
            report_path.write_text(f"# Optimization Report\n\n{report}\n")
            print(f"  Report: {report_path}")
        except Exception as e:
            print(f"  Report generation failed: {e}")
