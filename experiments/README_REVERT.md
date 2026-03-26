# Engine changes for ablation experiments

## What was changed in engine.py

`build_prompt()` got a `disable_board=False` parameter.
When True, board summary and failed approaches are not injected into agent prompts.

The call site in `SwarmEngine._run_experiment()` reads `getattr(self, "disable_board", False)`.

## How to revert

These changes are backward-compatible (default=False), so they can stay.
If you want to remove them:

1. Remove `disable_board=False` param from `build_prompt()` signature (line ~593)
2. Revert `[] if disable_board else` on `failed_list` (line ~601)
3. Revert `"" if disable_board else` on two `board_summary=` lines (lines ~627, ~635)
4. Remove `disable_board=...` from the call site (line ~933)

## Files created

- `experiments/ablation.py` — main 3x3x3 ablation (27 runs)
- `experiments/ablation_board.py` — board ablation (9 runs, uses disable_board flag)
- `experiments/ablation_rounds.py` — round scaling on game-ai (12 runs)
