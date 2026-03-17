---
target: target/prompts.py
eval: python3 eval.py
direction: maximize
rounds: 5
timeout: 600
eval_runs: 3
---

Optimize the INTENT_BLOCK_TEMPLATE for a Telegram outreach bot.

This prompt block tells an LLM how to classify customer intent from chat messages.
The eval runs 22 real conversation scenarios and checks if intent is classified correctly.

The file has ONE variable: INTENT_BLOCK_TEMPLATE (a Python string with format placeholders).

CONSTRAINTS:
- Keep format placeholders: {landing_price_k}, {portfolio_url}
- Keep the variable name INTENT_BLOCK_TEMPLATE
- Keep the triple-quote string format (Python)
- ALL text must be in Russian
- Output format must stay: first line = INTENT keyword, second line = response text
- Valid intents: CONTINUE, REJECT, HOSTILE, INTERESTED, QUESTION, PRICE_ASK,
  OBJECTION_EXPENSIVE, OBJECTION_THINKING, OBJECTION_NO_NEED, WANTS_EXAMPLES,
  READY_TO_TALK, READY_TO_PITCH, HAS_SITE

KNOWN FAILURES (baseline 86%):
- "Нет, мы этим не занимаемся" should be REJECT but gets CONTINUE
- Multi-question messages sometimes get UNKNOWN (parsing fails)
- "Скиньте на почту mail@..." should be READY_TO_TALK but gets UNKNOWN

Focus on:
- Making intent definitions clearer and more unambiguous
- Better examples that cover edge cases
- Ensuring the model always outputs exactly 2 lines (INTENT + text)
