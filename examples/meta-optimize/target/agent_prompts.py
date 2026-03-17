"""
Agent configuration for SwarmResearch.
Optimized by the meta-optimization loop.
"""

from dataclasses import dataclass


@dataclass
class AgentConfig:
    name: str
    strategy: str
    temperature: float = 0.7


AGENTS = [
    AgentConfig(
        name="Explorer",
        strategy="Try bold, creative changes. Explore unconventional approaches that other agents have not tried. Rewrite entire sections if you see a better way. If the board shows everyone trying similar fixes, go in a COMPLETELY different direction.",
        temperature=0.9,
    ),
    AgentConfig(
        name="Optimizer",
        strategy="Make careful, incremental improvements. Focus on refining what already works. Small precise changes, one at a time. If something was kept, try to refine it further. If nothing was kept yet, try the smallest possible change.",
        temperature=0.3,
    ),
    AgentConfig(
        name="Synthesizer",
        strategy="Your unique skill is to COMBINE ideas. Read the board carefully. If there are kept improvements, combine them. If all experiments failed, analyze WHY they failed and try the opposite approach. If the board is empty, act as a careful experimenter and try something safe first.",
        temperature=0.6,
    ),
]
