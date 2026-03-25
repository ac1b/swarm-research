# SwarmResearch — TODO

## Paper & Grant Pipeline

### 1. Benchmark Suite
- [ ] Verify all 11 examples run clean with baselines
  - [x] speed-opt — 91.85 ops/sec, maximize
  - [x] tsp-opt — 592.71 distance, minimize, multi-file (3)
  - [x] multi-opt — 7.27 ops/sec, maximize, multi-file (2)
  - [x] algo-opt — 95.00, maximize
  - [x] config-opt — 61.98, maximize
  - [x] compress-opt — 99.98, maximize
  - [x] bio-opt — 39.58, maximize
  - [x] num-opt — 49.31, maximize
  - [x] game-ai — 25.62 win%, maximize, multi-file (2)
  - [x] ml-opt — 65.00 accuracy%, maximize, multi-file (2)
  - [x] scheduler — 500000 tardiness, minimize, multi-file (3)
- [ ] Add examples to README (game-ai, ml-opt, scheduler missing)
- [ ] Run all examples with LLM, record before/after scores
- [ ] Pick 5-6 best for paper benchmark (diverse: NP-hard, game, ML, numerical, speed)

### 2. Ablation Experiments
- [ ] Backtracking vs no backtracking (same budget, same seed)
- [ ] 3 agents vs 1 agent (same total rounds)
- [ ] Board sharing vs isolated agents (disable board)
- [ ] Tree search depth: backtrack=2 vs 3 vs 5
- [ ] LLM comparison: Claude vs GPT-4o vs Kimi K2.5 (same tasks)
- [ ] Statistical significance: 5 runs per config, report mean ± std

### 3. Paper
- [ ] Pick venue: NeurIPS workshop, ICML workshop, or AAMAS
- [ ] Structure: intro, related work, method, experiments, ablations, conclusion
- [ ] Related work: autoresearch, MiroFish, FunSearch, AlphaCode, EvoPrompt
- [ ] Key claim: tree search + multi-agent > greedy single-agent
- [ ] Figures: optimization tree visualization, score curves, ablation tables
- [ ] Write draft

### 4. Grant Applications
- [ ] **Cooperative AI Foundation (CAIF)** — primary target
  - Angle: multi-agent cooperative optimization via shared knowledge board
  - $20K-$150K range
- [ ] **Anthropic Research Grants** — $100K
  - Angle: controllable multi-agent optimization with Claude
- [ ] **OpenPhilanthropy / Long-Term Future Fund**
  - Angle: interpretable tree-search optimization (vs black-box)
- [ ] Prerequisites: need paper (even workshop) before applying

### 5. Known Issues
- [ ] Eval timeout not enforced by default — agent wrote `9**(9**9)`, eval hung 5+ hours. Add mandatory timeout or document it clearly.

## Engine Improvements

### Agent Evolution (roadmap)
- [ ] Track agent win rates across rounds
- [ ] Kill agents with 0 wins after N rounds
- [ ] Mutate successful agent configs (temperature, prompt variations)
- [ ] Spawn new agents from best performers

### Smart Scheduling (roadmap)
- [ ] Board-driven agent selection (not round-robin)
- [ ] Prioritize agents whose style fits current phase
- [ ] Skip agents that have been consistently reverted

## Repo Polish
- [ ] Add game-ai, ml-opt, scheduler to README project structure
- [ ] Twitter thread (draft ready)
- [ ] Record demo GIF/video of a run
