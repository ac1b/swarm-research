---
target: target/agent_prompts.py
eval: python3 eval.py
direction: maximize
rounds: 3
timeout: 300
---

Optimize agent configurations for a multi-agent code optimization framework.

The eval runs these agents on a Python speed optimization task and measures improvement.
Higher score = agents find better optimizations.

The file defines 3 agents with: name, strategy (text), and temperature (0.0-1.0).
The strategy text tells each agent HOW to approach optimization.

WHAT TO TRY:
- Rewrite strategies to be more specific about code optimization techniques
- Adjust temperatures (higher = more creative, lower = more focused)
- Change the number of agents or their roles
- Add domain-specific hints (e.g. "use list comprehensions", "cache lookups", "use math module")
- Make strategies more complementary (avoid overlap)

CONSTRAINTS:
- Keep the dataclass import and AgentConfig definition
- Keep AGENTS as a list of AgentConfig objects
- Each agent needs: name (str), strategy (str), temperature (float 0.0-1.0)
- At least 2 agents required
- Strategy text should be 1-3 sentences
- No format placeholders or special characters needed — just plain text
