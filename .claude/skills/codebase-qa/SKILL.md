---
name: codebase-qa
description: Generate Q&A pairs, FAQs, and knowledge quizzes for any codebase. Use this skill whenever the user asks to create questions, quiz, FAQ, onboarding guide, interview prep, or knowledge assessment for a codebase. Trigger on phrases like "Q&A", "quiz", "FAQ", "onboarding questions", "interview questions about this code", "test my knowledge of the repo", or "create questions about this project".
---

# Codebase Q&A Generator

Generate structured question-and-answer content from any codebase using Mempalace MCP semantic search and file inspection.

## When to Use
- Creating onboarding docs for new team members
- Preparing interview questions about a project
- Building knowledge assessments or quizzes
- Generating FAQ pages for open-source projects
- Summarizing architecture decisions as Q&A

## Workflow

### Step 1 — Understand the Repo
Query Mempalace MCP to build context. Budget: **at most 3 semantic searches + 5 direct file reads**. Stop when you have enough to answer accurately.

```
mempalace_get_taxonomy → get wings and rooms
mempalace_search → query key concepts (limit 5 results each, max 3 queries)
```

Also inspect key files directly (pick what exists):
- `README.md`
- `pyproject.toml` / `package.json`
- `CLAUDE.md` or `.claude/rules/`
- Core module `__init__.py` files
- `architecture.md` or `DESIGN.md` if present

### Step 2 — Respect User's Scope
- If user asks for **N questions**, produce **exactly N** (±1 allowed for quality).
- If user asks for a **focused topic** (e.g., "testing setup"), stay in that category. Do not expand to unrelated areas.
- If user asks for a **comprehensive FAQ** with no count, cap at **15 questions max**. State the cap if you hit it.

### Step 3 — Identify Q&A Categories
From repo analysis, determine which categories apply:

| Category | Trigger |
|----------|---------|
| Architecture | System design, component relationships, data flow |
| Setup & Install | Dependencies, env vars, first-run steps |
| API & Usage | Public interfaces, CLI commands, config formats |
| Testing | Test structure, fixtures, coverage, CI gates |
| Patterns & Conventions | Coding style, naming, error handling, logging |
| Troubleshooting | Common errors, debugging steps, known issues |
| Contribution | PR process, commit style, review checklist |

### Step 4 — Generate Questions
For each category, generate 3-8 questions at chosen depth:

**Surface** — Findable by reading README or top-level docs.
**Deep** — Requires understanding relationships between modules or design rationale.
**Expert** — Edge cases, trade-offs, internals that aren't documented.

Question types:
- **Factual**: "What is the purpose of X?"
- **Procedural**: "How do you Y?"
- **Conceptual**: "Why is Z designed this way?"
- **Troubleshooting**: "What causes error W and how to fix?"
- **Comparative**: "When should you use A vs B?"

### Step 5 — Write Answers
Answers must be:
- **Accurate** — cite file paths or mempalace drawer IDs when possible
- **Concise prose** — 2-5 sentences for factual/conceptual answers
- **Procedural answers may include code blocks** — copy-pasteable commands are OK; keep explanatory text to 2-5 sentences
- **Self-contained** — reader should not need to open files
- **Honest about uncertainty** — "Not documented; inferred from..."

Format citations as: `(Source: path/to/file.py:42)` or `(Sources: file1.py, file2.py)`.

### Step 6 — Format Output

**Default: Markdown Q&A**
Use this exact structure:
```markdown
# [Repo Name] — [Topic] Q&A

## Category: [Category Name]

### Q1: [Question]
**A:** [Answer text]
(Source: `path/to/file.py:42`)
```

Do not use `<details>` tags or multi-level nesting unless the user explicitly requests hidden answers.

**JSON output** (if user requests machine-readable):
```json
[
  {
    "id": "arch-001",
    "category": "Architecture",
    "depth": "deep",
    "question": "...",
    "answer": "...",
    "sources": ["autopipe/core/pipeline.py"]
  }
]
```

**Flashcard format** (Anki-compatible):
```
Q: What does X do?
A: Y
Tags: autopipe::architecture
```

## Anti-Patterns
- **Don't** produce 20+ questions when user asked for 5.
- **Don't** answer with only a code block and no prose explanation.
- **Don't** cite files you didn't actually read.
- **Don't** mix unrelated categories when user scoped the request narrowly.
- **Don't** use `<details>` tags for standard Q&A output.

## Example Invocation

User: "Create interview questions about this repo's pipeline engine."

Expected skill behavior:
1. Query mempalace for "pipeline engine step lifecycle" (1 search, limit 5)
2. Read `autopipe/core/pipeline.py` and `autopipe/core/step.py`
3. Generate 5-8 deep questions across factual/conceptual/troubleshooting
4. Output markdown with file citations in `(Source: file:line)` format
