# Autopipe Hooks

These hooks run inside Claude Code sessions while working on the Autopipe codebase.

| Hook | Trigger | Action |
|------|---------|--------|
| `session-start` | SessionStart | Load project context (conda env, three subsystems) |
| `post-edit-ruff` | After Python file edit | Run `ruff check --fix` and report |
| `post-edit-mypy` | After Python file edit | Run `mypy` on changed file and report |
| `suggest-compact` | ContextCompaction | Suggest files to drop from context |

## Manual Trigger
```bash
# Run ruff + mypy on a specific file
conda run -n pipeline ruff check --fix autopipe/core/runner.py
conda run -n pipeline mypy autopipe/core/runner.py
```
