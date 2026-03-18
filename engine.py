"""
SwarmResearch Engine v0.4

Autonomous multi-agent optimization framework.
v0.4: resume, phase-aware prompting, per-agent memory, LLM report.
"""

import json
import os
import re
import subprocess
import shutil
import threading
from typing import Optional, List, Dict
from dataclasses import dataclass, asdict
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
            for f in failed[-10:]:
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
                    config[key.strip()] = val.strip()
            body = parts[2].strip()

    config["description"] = body
    return config


# ---------------------------------------------------------------------------
# Eval runner
# ---------------------------------------------------------------------------

def run_eval_once(eval_cmd, work_dir, timeout=300):
    # type: (str, Path, int) -> Optional[float]
    try:
        result = subprocess.run(
            eval_cmd, shell=True, cwd=work_dir,
            capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode != 0:
            stderr_tail = result.stderr[-500:] if result.stderr else ""
            print(f"    eval error: {stderr_tail}")
            return None

        # Prefer explicit SCORE: marker, fallback to last number in output
        for line in reversed(result.stdout.strip().split("\n")):
            score_match = re.search(r"SCORE:\s*([-+]?\d*\.?\d+)", line.strip())
            if score_match:
                return float(score_match.group(1))

        for line in reversed(result.stdout.strip().split("\n")):
            match = re.search(r"[-+]?\d*\.?\d+", line.strip())
            if match:
                return float(match.group())

        return None
    except subprocess.TimeoutExpired:
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
                    _llm_clients[provider] = Anthropic(api_key=os.environ["LLM_API_KEY"])
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
# Prompt construction — v0.3: supports both full-file and diff mode
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
Experiment #{experiment_num}. Propose your next change."""


def build_prompt(agent, task_desc, target_content, target_name,
                 board, memory_text, experiment_num, use_diff=False, phase_hint=""):
    # type: (AgentConfig, str, str, str, Board, str, int, bool, str) -> List[dict]

    failed_list = board.failed_approaches()
    failed_block = ""
    if failed_list:
        failed_block = "\nDO NOT try these (already failed):\n" + \
            "\n".join(f"- {a[:120]}" for a in failed_list)

    sys_template = DIFF_SYSTEM_TEMPLATE if use_diff else FULL_SYSTEM_TEMPLATE
    system = sys_template.format(
        agent_name=agent.name, agent_strategy=agent.strategy,
        failed_block=failed_block,
    )

    user = USER_TEMPLATE.format(
        task_desc=task_desc, target_name=target_name,
        target_content=target_content, board_summary=board.summary(),
        memory_text=memory_text, phase_hint=phase_hint,
        experiment_num=experiment_num,
    )

    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


# ---------------------------------------------------------------------------
# Response parsing — v0.3: supports both diff and full-file responses
# ---------------------------------------------------------------------------

def strip_think_tags(text):
    # type: (str) -> str
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def apply_diffs(original, response):
    # type: (str, str) -> Optional[str]
    """Apply SEARCH/REPLACE diff blocks to original content. Returns new content or None."""
    cleaned = strip_think_tags(response)

    # Find all SEARCH/REPLACE blocks
    pattern = r"<<<<\s*SEARCH\s*\n(.*?)\n====\s*\n(.*?)\n>>>>\s*REPLACE"
    blocks = re.findall(pattern, cleaned, re.DOTALL)

    if not blocks:
        return None

    result = original
    for search, replace in blocks:
        search = search.rstrip("\n")
        replace = replace.rstrip("\n")
        if search in result:
            result = result.replace(search, replace, 1)
        else:
            # Try fuzzy match: strip leading/trailing whitespace per line
            search_stripped = "\n".join(l.rstrip() for l in search.split("\n"))
            result_stripped_lines = result.split("\n")
            # Try to find a matching region
            found = False
            for i in range(len(result_stripped_lines)):
                candidate_lines = result_stripped_lines[i:i + search.count("\n") + 1]
                candidate = "\n".join(l.rstrip() for l in candidate_lines)
                if candidate == search_stripped:
                    original_lines = result.split("\n")
                    new_lines = (original_lines[:i] +
                                replace.split("\n") +
                                original_lines[i + len(candidate_lines):])
                    result = "\n".join(new_lines)
                    found = True
                    break
            if not found:
                print(f"    diff mismatch: could not find block starting with: {search[:80]!r}")
                return None  # search text not found

    if result == original:
        return None  # no actual changes

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
    needed = {"board.json", "agent_memory/", "report.md"}
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
# SwarmEngine v0.3 — parallel agents, diff mode, smart exploration
# ---------------------------------------------------------------------------

class SwarmEngine:
    def __init__(self, task_path):
        # type: (str) -> None
        self.task_path = Path(task_path).resolve()
        self.work_dir = self.task_path.parent
        self.task = parse_task(self.task_path)

        self.target_file = self.work_dir / self.task.get("target", "target/main.txt")
        self.eval_cmd = self.task.get("eval", "python eval.py")
        self.direction = self.task.get("direction", "maximize")
        self._task_fingerprint = f"{self.target_file.name}|{self.eval_cmd}|{self.direction}"
        self.rounds = int(self.task.get("rounds", "10"))
        self.timeout = int(self.task.get("timeout", "300"))
        self.eval_runs = int(self.task.get("eval_runs", "1"))

        # v0.3: diff mode for files > 50 lines
        target_lines = self.target_file.read_text().count("\n") if self.target_file.exists() else 0
        self.use_diff = self.task.get("mode", "auto") == "diff" or \
                        (self.task.get("mode", "auto") == "auto" and target_lines > 50)

        # v0.3: parallel mode
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
        self.no_report = False
        self.start_round = 1
        self._lock = threading.Lock()  # for parallel mode

    def is_better(self, new, old):
        if self.direction == "minimize":
            return new < old
        return new > old

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

    def _run_single_agent(self, agent, round_num, target_content):
        # type: (AgentConfig, int, str) -> Optional[tuple]
        """Run one agent's experiment. Returns (Finding, new_content) or None."""

        with self._lock:
            self.experiment_count += 1
            exp_num = self.experiment_count
            current_best = self.best_score

        print(f"\n  [{agent.name}] experiment #{exp_num}")

        messages = build_prompt(
            agent, self.task["description"], target_content,
            self.target_file.name, self.board,
            self.memory.format_for_prompt(agent.name),
            exp_num, self.use_diff,
            phase_hint=self._phase_hint(round_num),
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
            new_content = apply_diffs(target_content, reply)
            if new_content is None:
                # Fallback to full-file extraction
                new_content = extract_file_content(reply)
        else:
            new_content = extract_file_content(reply)

        if not new_content:
            print(f"    could not extract changes from response")
            return (Finding(
                agent=agent.name, round=round_num, experiment=exp_num,
                score=0, baseline=current_best, delta=0,
                kept=False, reasoning=reasoning,
                description=f"PARSE_FAIL: {reasoning[:100]}",
                change_summary="(could not parse response)",
                timestamp=datetime.now().isoformat(),
            ), None)

        if new_content.strip() == target_content.strip():
            print(f"    no changes proposed")
            return None, None

        if self.parallel:
            # Parallel: eval in a temp copy
            finding = self._eval_in_copy(
                agent, round_num, exp_num, target_content,
                new_content, reasoning, change_summary, current_best,
            )
        else:
            # Sequential: eval in place
            finding = self._eval_in_place(
                agent, round_num, exp_num, target_content,
                new_content, reasoning, change_summary, current_best,
            )
        return (finding, new_content) if finding else (None, None)

    def _eval_in_place(self, agent, round_num, exp_num, target_content,
                        new_content, reasoning, change_summary, current_best):
        """Sequential mode: write file, eval, keep or revert."""
        self.target_file.write_text(new_content)
        score = self._eval()

        if score is None:
            self.target_file.write_text(target_content)
            print(f"    CRASH  | {change_summary[:80]}")
            return Finding(
                agent=agent.name, round=round_num, experiment=exp_num,
                score=0, baseline=current_best, delta=0,
                kept=False, reasoning=reasoning,
                description=f"CRASH: {reasoning[:100]}",
                change_summary=change_summary,
                timestamp=datetime.now().isoformat(),
            )

        delta = (score - current_best)
        if self.direction == "minimize":
            delta = (current_best - score)

        kept = self.is_better(score, current_best)

        if kept:
            with self._lock:
                self.best_score = score
            git_commit(self.work_dir, f"R{round_num} {agent.name}: {change_summary[:80]}")
            print(f"    KEPT     score={score:.4f}  delta={delta:+.4f}")
        else:
            self.target_file.write_text(target_content)
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

    def _eval_in_copy(self, agent, round_num, exp_num, target_content,
                       new_content, reasoning, change_summary, current_best):
        """Parallel mode: eval in a temp directory, merge winner after."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            # Copy work_dir contents (excluding .git)
            for item in self.work_dir.iterdir():
                if item.name in (".git", "board.json", "agent_memory"):
                    continue
                dest = tmp_path / item.name
                if item.is_dir():
                    shutil.copytree(item, dest)
                else:
                    shutil.copy2(item, dest)

            # Write modified file
            tmp_target = tmp_path / self.target_file.relative_to(self.work_dir)
            tmp_target.write_text(new_content)

            score = self._eval(tmp_path)

        if score is None:
            print(f"    CRASH  | {change_summary[:80]}")
            return Finding(
                agent=agent.name, round=round_num, experiment=exp_num,
                score=0, baseline=current_best, delta=0,
                kept=False, reasoning=reasoning,
                description=f"CRASH: {reasoning[:100]}",
                change_summary=change_summary,
                timestamp=datetime.now().isoformat(),
            )

        delta = (score - current_best)
        if self.direction == "minimize":
            delta = (current_best - score)

        kept = self.is_better(score, current_best)
        print(f"    {'KEPT' if kept else 'reverted':8s} score={score:.4f}  delta={delta:+.4f}")
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
        print(f"SwarmResearch Engine v0.4 [{mode_label}, {par_label}]")
        print(f"  Task:      {self.task_path}")
        print(f"  Target:    {self.target_file}")
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

        for round_num in range(self.start_round, self.rounds + 1):
            print(f"{'=' * 60}")
            print(f"ROUND {round_num}/{self.rounds}  |  best = {self.best_score:.4f}")
            print(f"{'=' * 60}")

            score_before = self.best_score
            target_content = self.target_file.read_text()

            if self.parallel:
                self._run_round_parallel(round_num, target_content)
            else:
                self._run_round_sequential(round_num, target_content)

            # Early stopping: track consecutive rounds without improvement
            improved = self.is_better(self.best_score, score_before)
            if improved:
                self.stale_rounds = 0
            else:
                self.stale_rounds += 1

            if self.early_stop and self.stale_rounds >= self.early_stop:
                print(f"\n  Early stop: {self.stale_rounds} rounds without improvement.")
                break

        # Report
        self._print_report()
        self._generate_report()

    def _run_round_sequential(self, round_num, target_content):
        """Run agents one by one. Each builds on the previous kept changes."""
        for agent in self.agents:
            target_content = self.target_file.read_text()  # re-read after possible keeps
            finding, _ = self._run_single_agent(agent, round_num, target_content)
            if finding:
                self.board.add(finding)
                self._save_agent_memory(finding)

    def _run_round_parallel(self, round_num, target_content):
        """Run all agents in parallel. Best result wins the round."""
        results = []  # list of (finding, new_content)

        with ThreadPoolExecutor(max_workers=len(self.agents)) as pool:
            futures = {
                pool.submit(self._run_single_agent, agent, round_num, target_content): agent
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
            winner_finding, winner_content = max(candidates, key=lambda x: x[0].delta)
            print(f"\n  >> Round winner: {winner_finding.agent} (delta={winner_finding.delta:+.4f})")

            # Apply winner's content to the actual target file
            self.target_file.write_text(winner_content)
            with self._lock:
                self.best_score = winner_finding.score
            git_commit(self.work_dir, f"R{round_num} {winner_finding.agent}: {winner_finding.change_summary[:80]}")

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
