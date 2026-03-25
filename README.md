<div align="center">

# 🐝 SwarmResearch

**Autonomous multi-agent optimization with tree search & backtracking**

*A swarm of AI agents collaboratively optimize any file against a measurable metric — and backtrack when stuck in local optima.*

[![GitHub Stars](https://img.shields.io/github/stars/ac1b/swarm-research?style=flat-square&color=gold)](https://github.com/ac1b/swarm-research/stargazers)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9+-green?style=flat-square)](https://python.org)
[![Tests](https://img.shields.io/badge/Tests-55%20passed-brightgreen?style=flat-square)](#-tests)

Inspired by [Karpathy's autoresearch](https://github.com/karpathy/autoresearch) and [MiroFish](https://github.com/666ghj/MiroFish).

</div>

---

## ⚡ What is this?

Most auto-research tools use a **greedy ratchet** — keep improvements, revert everything else. This gets stuck in local optima fast.

SwarmResearch adds **tree search with backtracking**: when agents hit a plateau, the engine rolls back to an earlier state and explores a different optimization path. Combined with multiple agents (Explorer, Optimizer, Synthesizer) sharing findings via a board, this escapes local optima that single-path approaches can't.

> **Input:** a target file + an eval script that outputs a score
> **Output:** an optimized file + a tree of explored paths

## 🏗️ Architecture

```
              ┌───────────────────────────────────────────┐
              │              Search Tree                  │
              │                                           │
              │   [baseline: 81 ops/sec]                  │
              │      ├── [R1 Explorer +6.0]               │
              │      │     ├── [R3 Explorer +7.3]         │
              │      │     │     └── x abandoned          │
              │      │     └── [R7 Synthesizer +7.1]      │
              │      │           └── x abandoned          │
              │      └── ... (new branches)               │
              └───────────────────────────────────────────┘
                                  │
        ┌─────────────────────────┼─────────────────────────┐
        v                         v                         v
  ┌──────────────┐       ┌──────────────┐       ┌──────────────┐
  │   Explorer   │       │  Optimizer   │       │ Synthesizer  │
  │  temp = 0.9  │       │  temp = 0.3  │       │  temp = 0.6  │
  │  bold moves  │       │  refinement  │       │ combine ideas│
  └──────┬───────┘       └──────┬───────┘       └──────┬───────┘
        │                       │                         │
        └───────────┬───────────┴─────────┬───────────────┘
                    v                     v
              ┌──────────┐         ┌──────────┐
              │  Board   │<------->│  Target  │
              │  (JSON)  │         │   File   │
              └──────────┘         └────┬─────┘
                                        v
                                  ┌──────────┐
                                  │   Eval   │--> score
                                  └──────────┘
```

## 🔄 How it works

1. **Baseline** — eval the target file, record the starting score
2. **Agents take turns** — each proposes a change (full rewrite or SEARCH/REPLACE diff)
3. **Eval & decide** — if score improves, keep the change; otherwise revert
4. **Share findings** — all results (kept and reverted) go to the shared board
5. **Backtrack if stuck** — after N stale rounds, roll back to an earlier state in the tree and try a different path
6. **Restore global best** — at the end, the best result across all branches is restored

## 🚀 Quick start

```bash
git clone https://github.com/ac1b/swarm-research.git
cd swarm-research
pip install -e .

# Configure LLM
cp .env.example .env
# Edit .env with your API key

# Run speed optimization example
python3 run.py examples/speed-opt/task.md

# With backtracking (escape local optima)
python3 run.py examples/speed-opt/task.md --rounds 10 --backtrack 3
```

## 📋 Configuration

Create a `task.md` with YAML frontmatter:

```yaml
---
target: target/solution.py
eval: python3 eval.py
direction: maximize
rounds: 10
backtrack: 3
max_backtracks: 5
---

Description of what to optimize and any constraints.
```

### Options

| Key | Default | Description |
|-----|---------|-------------|
| `target` | *required* | Path to the file agents will modify |
| `eval` | *required* | Command that outputs a numeric score |
| `direction` | `maximize` | `maximize` or `minimize` the score |
| `rounds` | `10` | Number of optimization rounds |
| `timeout` | `300` | Eval timeout in seconds |
| `eval_runs` | `1` | Runs per eval (median used for >1) |
| `mode` | `auto` | `full` = rewrite, `diff` = SEARCH/REPLACE, `auto` = diff if >50 lines |
| `parallel` | `false` | Run agents in parallel (best result wins each round) |
| `early_stop` | `0` | Stop after N stale rounds (0 = disabled) |
| `backtrack` | `0` | Backtrack after N stale rounds (0 = disabled) |
| `max_backtracks` | `5` | Maximum number of backtracks per run |

### CLI overrides

```bash
python3 run.py task.md --rounds 15 --backtrack 3 --max-backtracks 5 --no-report
```

## 📊 Results

### speed-opt example

Optimize a Python function for maximum throughput (Kimi K2.5, 10 rounds, backtrack=3):

```
Baseline:   81 ops/sec

ROUND 1  │ Explorer  KEPT  score=87.12  (+6.0)   ← sqrt elimination
ROUND 3  │ Explorer  KEPT  score=94.40  (+7.3)   ← refined approach
ROUND 4-6│ all reverted... plateau
         │ BACKTRACK #1: 94.40 → 87.12 (trying different path)
ROUND 7  │ Synth     KEPT  score=94.20  (+7.1)   ← found alternative!
ROUND 8-10 all reverted... plateau
         │ BACKTRACK #2: 94.20 → 94.40 (restored global best)

DONE
  Final:      94.40 ops/sec (+16.4%)
  Tree nodes: 4
  Backtracks: 2
```

## 🧬 Key features

| Feature | Description |
|---------|-------------|
| **Tree search** | States form a tree, not a line. Backtrack to explore branches. |
| **Global best tracking** | Best result across all branches is restored at the end. |
| **Multi-agent swarm** | Explorer (bold), Optimizer (careful), Synthesizer (combines ideas). |
| **Shared board** | All agents see what worked and what failed. No repeated mistakes. |
| **Phase-aware prompts** | Agents know if it's early exploration or late refinement. |
| **Per-agent memory** | Each agent remembers its own experiment history. |
| **Resume** | Crash? Just re-run. Picks up from `board.json` + `tree.json`. |
| **Diff mode** | For large files: SEARCH/REPLACE blocks instead of full rewrites. |
| **Any LLM** | Anthropic, OpenAI, or any OpenAI-compatible API. |

## 🔧 Custom agents

Create `agent_prompts.py` next to your `task.md`:

```python
from engine import AgentConfig

AGENTS = [
    AgentConfig("Researcher", "Explore novel approaches. Be creative.", 0.9),
    AgentConfig("Engineer", "Make precise, incremental improvements.", 0.3),
]
```

## 🌐 Supported LLM providers

| Provider | Config |
|----------|--------|
| **Anthropic** (Claude) | `LLM_PROVIDER=anthropic` |
| **OpenAI** (GPT-4o) | `LLM_PROVIDER=openai` |
| **Kimi Code** (K2.5) | `LLM_PROVIDER=anthropic`, `LLM_BASE_URL=https://api.kimi.com/coding/` |
| **Kimi API** (moonshot) | `LLM_PROVIDER=openai`, `LLM_BASE_URL=https://api.moonshot.ai/v1` |
| **MiniMax** | `LLM_PROVIDER=openai`, `LLM_BASE_URL=https://api.minimax.io/v1` |
| **Any OpenAI-compatible** | `LLM_PROVIDER=openai`, set `LLM_BASE_URL` |

## 🧪 Tests

```bash
python3 -m pytest tests/ -v          # all 55 tests
python3 -m pytest tests/test_tree.py  # SearchTree unit tests (33)
python3 -m pytest tests/test_backtrack_engine.py  # engine integration (22)
```

## 📁 Project structure

```
swarm-research/
├── engine.py              # Core engine (~1200 lines)
├── run.py                 # CLI entry point
├── .env.example           # LLM config template
├── tests/
│   ├── test_tree.py       # SearchTree unit tests
│   ├── test_backtrack_engine.py
│   └── conftest.py
└── examples/
    ├── speed-opt/         # Python function speed optimization
    ├── copy-optimize/     # Trading strategy optimization
    └── fade-optimize/     # Signal-based strategy optimization
```

## 🔮 Roadmap

- [ ] Agent evolution — bad strategies die, good ones mutate and reproduce
- [ ] Smart scheduling — board influences which agent goes next
- [ ] Multi-file targets — optimize across multiple files simultaneously

## 📄 License

MIT
