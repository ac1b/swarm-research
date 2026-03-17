# SwarmResearch

Autonomous multi-agent optimization framework. A swarm of AI agents with different strategies collaboratively optimize any target file against a measurable metric.

Inspired by [Karpathy's autoresearch](https://github.com/karpathy/autoresearch) and [MiroFish](https://github.com/666ghj/MiroFish).

## How it works

1. You define a **target file** and an **eval script** that outputs a numeric score
2. Multiple AI agents take turns modifying the target file
3. After each modification, the eval runs — if the score improves, the change is **kept**; otherwise it's **reverted**
4. Agents share findings via a **board** (JSON) so they learn from each other's successes and failures

```
┌─────────┐     ┌─────────┐     ┌──────────────┐
│ Explorer │     │Optimizer│     │ Synthesizer  │
│ temp=0.9 │     │temp=0.3 │     │  temp=0.6    │
└────┬─────┘     └────┬────┘     └──────┬───────┘
     │                │                 │
     └────────┬───────┴─────────┬───────┘
              ▼                 ▼
         ┌─────────┐     ┌──────────┐
         │  Board  │◄───►│  Target  │
         │ (JSON)  │     │  File    │
         └─────────┘     └────┬─────┘
                              ▼
                        ┌──────────┐
                        │   Eval   │──► score
                        └──────────┘
```

## Quick start

```bash
# Clone
git clone https://github.com/ac1b/swarm-research.git
cd swarm-research

# Install deps
pip install -e .

# Configure LLM provider
cp .env.example .env
# Edit .env with your API key

# Run the speed optimization example
python3 run.py examples/speed-opt/task.md
```

## Configuration

Create a `task.md` with YAML frontmatter:

```yaml
---
target: target/solution.py
eval: python3 eval.py
direction: maximize
rounds: 5
timeout: 30
eval_runs: 1
mode: auto        # auto | full | diff
parallel: false   # true for parallel agent execution
---

Description of what to optimize and any constraints.
```

### Options

| Key | Default | Description |
|-----|---------|-------------|
| `target` | required | Path to the file agents will modify |
| `eval` | required | Command that outputs a numeric score |
| `direction` | `maximize` | `maximize` or `minimize` the score |
| `rounds` | `10` | Number of optimization rounds |
| `timeout` | `300` | Eval timeout in seconds |
| `eval_runs` | `1` | Runs per eval (median used for >1) |
| `mode` | `auto` | `full` = rewrite file, `diff` = SEARCH/REPLACE blocks, `auto` = diff for >50 lines |
| `parallel` | `false` | Run agents in parallel (best result wins each round) |

## Supported LLM providers

- **Anthropic** (Claude)
- **OpenAI** (GPT-4o, etc.)
- **Any OpenAI-compatible API** (MiniMax, Kimi, etc.)

Configure in `.env`:

```bash
LLM_PROVIDER=openai              # "anthropic" or "openai"
LLM_API_KEY=sk-...
LLM_MODEL=MiniMax-M2.5-highspeed
LLM_BASE_URL=https://api.minimax.io/v1
```

## Examples

### speed-opt
Optimize a Python function for maximum speed. Baseline ~80 ops/sec → 93+ ops/sec (+18%).

```bash
python3 run.py examples/speed-opt/task.md --rounds 5
```

### webhunter-prompts
Optimize an intent classification prompt for a Telegram bot.

### meta-optimize
Meta-optimization: SwarmResearch optimizing its own agent configurations.

## Custom agents

Create `agent_prompts.py` in your task directory:

```python
from dataclasses import dataclass

@dataclass
class AgentConfig:
    name: str
    strategy: str
    temperature: float = 0.7

AGENTS = [
    AgentConfig(
        name="MyAgent",
        strategy="Your optimization strategy here.",
        temperature=0.5,
    ),
]
```

## License

MIT
