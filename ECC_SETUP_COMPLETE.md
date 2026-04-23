# ECC (Everything Claude Code) Setup — Autopipe

The Autopipe project now has a production‑grade ECC configuration at the repo root.

## What Was Implemented

### Directory Structure
```
.claude/
├── plugin.json                    # ECC manifest
├── agents/
│   ├── python-pipeline-reviewer.md   # Python + ML pipeline reviewer
│   ├── frontend-reviewer.md          # React/TypeScript/Vite reviewer
│   └── security-scanner.md           # Bandit + Python security reviewer
├── skills/
│   ├── tdd-python/SKILL.md           # RED-GREEN-REFACTOR for Python/pytest
│   ├── pipeline-patterns/SKILL.md    # Autopipe step + YAML patterns
│   └── python-security/SKILL.md      # Security checklist for ML projects
├── rules/
│   ├── common/coding-style.md        # Universal conventions
│   ├── python/patterns.md            # Pydantic, click, rich, async patterns
│   ├── python/testing.md             # pytest, coverage, mocking
│   └── ml-pipeline/config.md         # YAML pipeline design rules
├── hooks/
│   ├── hooks.json                   # Hook configuration
│   └── README.md                    # Hook documentation
└── scripts/hooks/
    ├── session-start.js             # Load project context (3 subsystems, conda)
    ├── post-edit-ruff.js            # Auto lint on Python file edits
    ├── post-edit-mypy.js            # Auto type-check on Python file edits
    └── suggest-compact.js           # Suggest context compaction
```

### Install Script
```bash
# Install all ECC components to ~/.claude/
./install-ecc.sh

# Or install to a custom directory
./install-ecc.sh /path/to/.claude
```

### Key Features

#### Agents (3)
| Agent | Purpose |
|-------|---------|
| `python-pipeline-reviewer` | Python type safety, pipeline step design, CLI patterns, subsystem boundaries |
| `frontend-reviewer` | React + TypeScript + Vite + Tailwind quality checks |
| `security-scanner` | Bandit rules, secrets, input validation, injection risks |

#### Skills (3)
| Skill | Description |
|-------|-------------|
| `tdd-python` | RED-GREEN-REFACTOR with pytest, 80% coverage gate |
| `pipeline-patterns` | Step lifecycle, YAML configs, context, observability |
| `python-security` | Pre-merge security checklist |

#### Rules (4 files)
| Rule | Focus |
|------|-------|
| `common/coding-style` | 4-space indent, 100-char line, snake_case, KISS, DRY, YAGNI |
| `python/patterns` | Pydantic v2, click, rich, asyncio, tenacity, structlog |
| `python/testing` | pytest markers, fixtures, async, mocking, coverage |
| `ml-pipeline/config` | YAML step design, validation, env overrides, anti-patterns |

#### Hooks (4)
| Hook | Trigger | Action |
|------|---------|--------|
| `session-start` | SessionStart | Load conda env + 3-subsystem context |
| `post-edit-ruff` | PostToolUse (Edit) | Run ruff check --fix on edited `.py` |
| `post-edit-mypy` | PostToolUse (Edit) | Run mypy on edited `.py` |
| `suggest-compact` | ContextCompaction | Suggest dropping screenshots / design docs |

## Usage

### In Claude Code
```bash
# Request a Python/pipeline review
/review

# Request a frontend review
/review frontend

# Run security checklist
/security

# View skills
/skill tdd-python
/skill pipeline-patterns
/skill python-security

# View agents
/agent python-pipeline-reviewer
/agent frontend-reviewer
/agent security-scanner
```

### Quick Commands
```bash
# Quality gates
conda run -n pipeline ruff check autopipe tests
conda run -n pipeline black --check autopipe tests
conda run -n pipeline mypy autopipe
conda run -n pipeline pytest tests/unit -q --cov=autopipe --cov-report=term-missing

# Dashboard backend
cd autopipe/dashboard/backend && .venv/bin/python -m pytest tests/ -v

# Dashboard frontend
cd autopipe/dashboard/frontend && pnpm build && pnpm typecheck
```

## Notes
- ECC lives at the **repo root** (`/Users/philosopher/active/autopipe/.claude/`).
- The project already has `AGENTS.md` and `CLAUDE.md` inside `autopipe/autopipe/`; this ECC is complementary and designed for Claude Code session tooling.
- Pre-commit hooks already exist (`.pre-commit-config.yaml`); the ECC hooks add in‑session lint/type feedback.

## References
- `AGENTS.md` — repository human guidelines
- `CLAUDE.md` — Karpathy principles + subsystem commands
- `./install-ecc.sh` — installation script
