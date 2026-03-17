---
target: target/agent_prompts.py
eval: python3 eval.py
direction: maximize
rounds: 3
timeout: 300
---

You are optimizing the agent prompts for SwarmResearch — a multi-agent optimization framework.

The eval measures: how much improvement do agents achieve when optimizing a Python function for speed.
Higher score = agents find better optimizations.

THE FILE CONTAINS:
- 3 AgentConfig objects (name, strategy, temperature) defining agent personas
- SYSTEM_PROMPT_TEMPLATE — the system prompt sent to each agent
- USER_PROMPT_TEMPLATE — the user prompt with task/file/board/history

WHAT TO OPTIMIZE:
- Agent strategies — make them more effective at proposing good code changes
- Temperatures — find the best creativity/precision balance
- System prompt — better instructions for proposing and formatting changes
- User prompt — better presentation of context, board, history

CONSTRAINTS:
- Keep the AgentConfig dataclass with fields: name, strategy, temperature
- Keep the variable name AGENTS (list of 3 AgentConfig)
- Keep SYSTEM_PROMPT_TEMPLATE and USER_PROMPT_TEMPLATE as strings
- Keep all format placeholders: {agent_name}, {agent_strategy}, {failed_block},
  {task_desc}, {target_name}, {target_content}, {board_summary}, {history_text}, {experiment_num}
- Output format rule MUST stay: ```file markers for complete file content
- Keep all imports
