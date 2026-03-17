"""
SwarmResearch Engine v0.2 — autonomous multi-agent optimization framework.

A swarm of AI agents with different strategies collaboratively optimize
any target file against a measurable metric.
"""

import json
import os
import re
import subprocess
import hashlib
from typing import Optional, List, Dict
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime


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
    change_summary: str  # what specifically was changed (for dedup)
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


def load_agent_prompts(work_dir: Path):
    """Try to load agent_prompts.py from work_dir or its parents. Returns module or None."""
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
# Board — shared knowledge between agents (v2: richer context)
# ---------------------------------------------------------------------------

class Board:
    def __init__(self, path: Path):
        self.path = path
        self.findings: List[Finding] = []
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text())
                self.findings = [Finding(**f) for f in data]
            except (json.JSONDecodeError, TypeError):
                self.findings = []

    def add(self, finding: Finding):
        self.findings.append(finding)
        self.path.write_text(json.dumps([asdict(f) for f in self.findings], indent=2))

    def summary(self, last_n: int = 20) -> str:
        if not self.findings:
            return "No experiments yet. You are the first — try something safe and informative."

        recent = self.findings[-last_n:]
        lines = []

        # Group by status for clearer picture
        kept = [f for f in self.findings if f.kept]
        failed = [f for f in self.findings if not f.kept]

        if kept:
            lines.append("=== KEPT (successful changes) ===")
            for f in kept:
                lines.append(
                    f"  R{f.round} {f.agent}: {f.change_summary[:150]} "
                    f"| score={f.score:.4f} (delta={f.delta:+.4f})"
                )

        if failed:
            lines.append("\n=== REVERTED (failed attempts — DO NOT repeat these) ===")
            for f in failed[-10:]:  # last 10 failures
                lines.append(
                    f"  R{f.round} {f.agent}: {f.change_summary[:150]} "
                    f"| score={f.score:.4f} (delta={f.delta:+.4f})"
                )

        if kept:
            best = max(kept, key=lambda f: f.delta)
            lines.append(
                f"\nBest so far: {best.agent} R{best.round} "
                f"(score={best.score:.4f}, +{best.delta:.4f})"
            )

        # Diversity hint
        failed_summaries = [f.change_summary for f in failed]
        if len(failed_summaries) >= 3:
            lines.append(
                f"\n*** {len(failed_summaries)} experiments failed. "
                f"Try a DIFFERENT approach than what's listed above. ***"
            )

        return "\n".join(lines)

    def failed_approaches(self) -> List[str]:
        """Return summaries of failed approaches for dedup."""
        return [f.change_summary for f in self.findings if not f.kept]


# ---------------------------------------------------------------------------
# Task parser
# ---------------------------------------------------------------------------

def parse_task(task_path: Path) -> dict:
    """Parse task.md with YAML-like frontmatter."""
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
# Eval runner (v2: multiple runs + median for robustness)
# ---------------------------------------------------------------------------

def run_eval_once(eval_cmd: str, work_dir: Path, timeout: int = 300) -> Optional[float]:
    """Run eval command once. Expects the LAST number in stdout to be the score."""
    try:
        result = subprocess.run(
            eval_cmd, shell=True, cwd=work_dir,
            capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode != 0:
            stderr_tail = result.stderr[-500:] if result.stderr else "(no stderr)"
            print(f"    eval failed (exit {result.returncode}): {stderr_tail}")
            return None

        for line in reversed(result.stdout.strip().split("\n")):
            match = re.search(r"[-+]?\d*\.?\d+", line.strip())
            if match:
                return float(match.group())

        print("    no score found in eval output")
        return None

    except subprocess.TimeoutExpired:
        print(f"    eval timed out ({timeout}s)")
        return None


def run_eval(eval_cmd: str, work_dir: Path, timeout: int = 300,
             runs: int = 1) -> Optional[float]:
    """Run eval multiple times and return median (robust to outliers)."""
    scores = []
    for i in range(runs):
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
# LLM client — supports anthropic and openai-compatible APIs
# ---------------------------------------------------------------------------

def call_llm(messages: List[dict], temperature: float, max_tokens: int = 16000) -> str:
    provider = os.environ.get("LLM_PROVIDER", "anthropic")

    if provider == "anthropic":
        from anthropic import Anthropic

        client = Anthropic(api_key=os.environ["LLM_API_KEY"])
        system = ""
        user_msgs = []
        for m in messages:
            if m["role"] == "system":
                system = m["content"]
            else:
                user_msgs.append(m)

        resp = client.messages.create(
            model=os.environ.get("LLM_MODEL", "claude-sonnet-4-20250514"),
            max_tokens=max_tokens,
            system=system,
            messages=user_msgs,
            temperature=temperature,
        )
        return resp.content[0].text

    else:  # openai-compatible (kimi, minimax, openai, etc.)
        from openai import OpenAI

        client = OpenAI(
            base_url=os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1"),
            api_key=os.environ.get("LLM_API_KEY", ""),
        )
        resp = client.chat.completions.create(
            model=os.environ.get("LLM_MODEL", "gpt-4o-mini"),
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content


# ---------------------------------------------------------------------------
# Agent prompt construction (v2: anti-repetition, diversity enforcement)
# ---------------------------------------------------------------------------

DEFAULT_SYSTEM_TEMPLATE = """You are {agent_name}, an AI research agent in a swarm optimization team.

Your strategy: {agent_strategy}

You modify a target file to improve a measurable score. After each change the file
is evaluated automatically. If the score improves, your change is kept; otherwise it
is reverted.

CRITICAL RULES:
1. Output the COMPLETE modified file between ```file and ``` markers.
2. Before the file content, write 2-3 sentences explaining:
   - WHAT you changed (specific description for the board)
   - WHY you expect it to improve the score
3. Make exactly ONE conceptual change per experiment.
4. NEVER repeat an approach that was already tried and failed (see board).
5. If many experiments failed — try something radically different.
6. Keep the output clean: no extra commentary after the closing ``` markers.
{failed_block}"""

DEFAULT_USER_TEMPLATE = """## Task
{task_desc}

## Current file: {target_name}
```
{target_content}
```

## Board (shared findings from all agents)
{board_summary}

## Your recent history
{history_text}

This is experiment #{experiment_num}. Propose your next change."""


def build_prompt(agent: AgentConfig, task_desc: str, target_content: str,
                 target_name: str, board: Board,
                 history: List[str], experiment_num: int,
                 prompt_module=None) -> List[dict]:

    failed_list = board.failed_approaches()
    failed_block = ""
    if failed_list:
        failed_block = "\nDO NOT try these approaches (they already failed):\n" + \
            "\n".join(f"- {a[:150]}" for a in failed_list[-10:])

    sys_template = DEFAULT_SYSTEM_TEMPLATE
    usr_template = DEFAULT_USER_TEMPLATE
    if prompt_module:
        sys_template = getattr(prompt_module, "SYSTEM_PROMPT_TEMPLATE", sys_template)
        usr_template = getattr(prompt_module, "USER_PROMPT_TEMPLATE", usr_template)

    system = sys_template.format(
        agent_name=agent.name, agent_strategy=agent.strategy,
        failed_block=failed_block,
    )

    history_text = "\n".join(history[-5:]) if history else "No history yet."

    user = usr_template.format(
        task_desc=task_desc, target_name=target_name,
        target_content=target_content, board_summary=board.summary(),
        history_text=history_text, experiment_num=experiment_num,
    )

    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


# ---------------------------------------------------------------------------
# Response parsing (v2: more robust)
# ---------------------------------------------------------------------------

def strip_think_tags(text: str) -> str:
    """Remove <think>...</think> blocks from LLM response."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def extract_file_content(response: str) -> Optional[str]:
    cleaned = strip_think_tags(response)
    # Try ```file first
    match = re.search(r"```file\s*\n(.*?)```", cleaned, re.DOTALL)
    if match:
        return match.group(1)
    # Try any language-tagged code block
    match = re.search(r"```(?:python|javascript|yaml|json|txt|sh|toml|py)?\s*\n(.*?)```", cleaned, re.DOTALL)
    if match:
        return match.group(1)
    # Last resort: try to find the largest code block
    blocks = re.findall(r"```\w*\s*\n(.*?)```", cleaned, re.DOTALL)
    if blocks:
        return max(blocks, key=len)
    return None


def extract_reasoning(response: str) -> str:
    cleaned = strip_think_tags(response)
    match = re.search(r"```", cleaned)
    if match:
        return cleaned[:match.start()].strip()[:500]
    return cleaned[:500]


def extract_change_summary(reasoning: str) -> str:
    """Extract a short summary of WHAT was changed for dedup."""
    # Take first sentence or first 100 chars
    for sep in [". ", ".\n", "\n"]:
        idx = reasoning.find(sep)
        if 10 < idx < 200:
            return reasoning[:idx].strip()
    return reasoning[:100].strip()


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def git(work_dir: Path, *args) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + list(args), cwd=work_dir,
        capture_output=True, text=True,
    )


def git_init(work_dir: Path):
    if not (work_dir / ".git").exists():
        git(work_dir, "init")
        git(work_dir, "add", "-A")
        git(work_dir, "commit", "-m", "baseline")


def git_commit(work_dir: Path, message: str):
    git(work_dir, "add", "-A")
    git(work_dir, "commit", "-m", message)


# ---------------------------------------------------------------------------
# SwarmEngine — main loop (v2)
# ---------------------------------------------------------------------------

class SwarmEngine:
    def __init__(self, task_path: str):
        self.task_path = Path(task_path).resolve()
        self.work_dir = self.task_path.parent
        self.task = parse_task(self.task_path)

        self.target_file = self.work_dir / self.task.get("target", "target/main.txt")
        self.eval_cmd = self.task.get("eval", "python eval.py")
        self.direction = self.task.get("direction", "maximize")
        self.rounds = int(self.task.get("rounds", "10"))
        self.timeout = int(self.task.get("timeout", "300"))
        self.eval_runs = int(self.task.get("eval_runs", "1"))

        self.board = Board(self.work_dir / "board.json")

        # Load custom agent prompts if available
        self.prompt_module = load_agent_prompts(self.work_dir)
        if self.prompt_module and hasattr(self.prompt_module, "AGENTS"):
            self.agents = self.prompt_module.AGENTS
        else:
            self.agents = DEFAULT_AGENTS

        self.agent_histories: Dict[str, List[str]] = {a.name: [] for a in self.agents}

        self.baseline_score: Optional[float] = None
        self.best_score: Optional[float] = None
        self.experiment_count = 0

    def is_better(self, new: float, old: float) -> bool:
        if self.direction == "minimize":
            return new < old
        return new > old

    def _eval(self) -> Optional[float]:
        """Run eval with configured number of runs."""
        return run_eval(self.eval_cmd, self.work_dir, self.timeout, self.eval_runs)

    def run(self):
        print("SwarmResearch Engine v0.2")
        print(f"  Task:      {self.task_path}")
        print(f"  Target:    {self.target_file}")
        print(f"  Eval:      {self.eval_cmd}")
        print(f"  Direction: {self.direction}")
        print(f"  Rounds:    {self.rounds}")
        print(f"  Eval runs: {self.eval_runs} (median)")
        print(f"  Agents:    {', '.join(a.name for a in self.agents)}")
        print()

        # Baseline
        print(f"Running baseline evaluation ({self.eval_runs} runs)...")
        self.baseline_score = self._eval()
        if self.baseline_score is None:
            print("ERROR: baseline eval failed. Fix your eval command first.")
            return
        self.best_score = self.baseline_score
        print(f"Baseline score: {self.baseline_score:.4f}\n")

        git_init(self.work_dir)

        for round_num in range(1, self.rounds + 1):
            print(f"{'=' * 60}")
            print(f"ROUND {round_num}/{self.rounds}  |  best = {self.best_score:.4f}")
            print(f"{'=' * 60}")

            for agent in self.agents:
                self.experiment_count += 1
                print(f"\n  [{agent.name}] experiment #{self.experiment_count}")

                target_content = self.target_file.read_text()

                messages = build_prompt(
                    agent, self.task["description"], target_content,
                    self.target_file.name, self.board,
                    self.agent_histories[agent.name],
                    self.experiment_count,
                    self.prompt_module,
                )

                # Call LLM
                try:
                    reply = call_llm(messages, agent.temperature)
                except Exception as e:
                    print(f"    LLM error: {e}")
                    continue

                new_content = extract_file_content(reply)
                reasoning = extract_reasoning(reply)
                change_summary = extract_change_summary(reasoning)

                if not new_content:
                    print(f"    could not extract file content from response")
                    # Log to board so other agents know
                    finding = Finding(
                        agent=agent.name, round=round_num,
                        experiment=self.experiment_count,
                        score=0, baseline=self.best_score, delta=0,
                        kept=False, reasoning=reasoning,
                        description=f"PARSE_FAIL: {reasoning[:100]}",
                        change_summary="(response could not be parsed)",
                        timestamp=datetime.now().isoformat(),
                    )
                    self.board.add(finding)
                    continue

                if new_content.strip() == target_content.strip():
                    print(f"    no changes proposed")
                    continue

                # Apply change
                self.target_file.write_text(new_content)

                # Eval
                score = self._eval()

                if score is None:
                    self.target_file.write_text(target_content)
                    finding = Finding(
                        agent=agent.name, round=round_num,
                        experiment=self.experiment_count,
                        score=0, baseline=self.best_score, delta=0,
                        kept=False, reasoning=reasoning,
                        description=f"CRASH: {reasoning[:100]}",
                        change_summary=change_summary,
                        timestamp=datetime.now().isoformat(),
                    )
                    self.board.add(finding)
                    print(f"    CRASH  | {change_summary[:80]}")
                    continue

                delta = (score - self.best_score)
                if self.direction == "minimize":
                    delta = (self.best_score - score)

                kept = self.is_better(score, self.best_score)

                if kept:
                    self.best_score = score
                    git_commit(self.work_dir, f"R{round_num} {agent.name}: {change_summary[:80]}")
                    print(f"    KEPT     score={score:.4f}  delta={delta:+.4f}")
                else:
                    self.target_file.write_text(target_content)
                    print(f"    reverted score={score:.4f}  delta={delta:+.4f}")

                print(f"    change: {change_summary[:100]}")

                finding = Finding(
                    agent=agent.name, round=round_num,
                    experiment=self.experiment_count,
                    score=score, baseline=self.best_score,
                    delta=delta, kept=kept, reasoning=reasoning,
                    description=reasoning[:200],
                    change_summary=change_summary,
                    timestamp=datetime.now().isoformat(),
                )
                self.board.add(finding)

                status = "KEPT" if kept else "reverted"
                self.agent_histories[agent.name].append(
                    f"R{round_num}: [{status}] {change_summary[:80]} -> {score:.4f}"
                )

        # Report
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
