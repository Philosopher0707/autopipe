# AutoPipe LLM Evaluation Pipeline (promptfoo)

This directory contains a **[promptfoo](https://promptfoo.dev)** configuration for evaluating
and comparing your configured Ollama models on AutoPipe-specific LLM tasks.

## Prerequisites

- **Node.js** ≥ 18
- **npx** (comes with Node/npm)

No global install needed — promptfoo runs via `npx`.

## Quick Start

### 1. Run evaluations via npx (recommended)

```bash
cd /path/to/autopipe

# Compare all models on all tests
npx promptfoo@latest eval -c promptfoo/promptfooconfig.yaml

# Run only pipeline-generation tests
npx promptfoo@latest eval -c promptfoo/promptfooconfig.yaml --prompts pipeline-generation

# Run only against kimi
npx promptfoo@latest eval -c promptfoo/promptfooconfig.yaml --providers ollama-kimi
```

### 2. Run via AutoPipe CLI (integrated)

```bash
# Full comparison across all 3 models
autopipe eval --compare

# Filter by task
autopipe eval --task pipeline-generation

# Filter by model
autopipe eval --provider ollama-kimi
autopipe eval --provider kimi-k2.5:cloud

# Output JSON results
autopipe eval --compare --output eval-results.json --verbose
```

## What Is Evaluated

| Task | Description | Why It Matters |
|------|-------------|--------------|
| **pipeline-generation** | Generate valid AutoPipe YAML configs from natural language | Core UX — users describe pipelines, LLM writes YAML |
| **step-explanation** | Explain what a given pipeline step does | Documentation generation, IDE tooltips |
| **error-diagnosis** | Suggest fixes for common pipeline errors | Better error messages, faster debugging |

## Configured Models

| Provider | Model | Label |
|----------|-------|-------|
| `ollama-kimi` | `kimi-k2.5:cloud` | High-performance reasoning |
| `ollama-glm` | `glm-5.1:cloud` | General-purpose chat |
| `ollama-minimax` | `minimax-m2.7:cloud` | Multi-modal capable |

## Assertions

Each test validates LLM output with multiple assertions:

- **`contains`** — output must include specific keywords
- **`regex`** — output must match regex (e.g. YAML `name:` field)
- **`not-contains`** — output must NOT include unwanted text (e.g. markdown code fences)

## Extending the Suite

Add new tests to `promptfooconfig.yaml` under `tests:

```yaml
  - description: "My new test"
    prompt: pipeline-generation
    vars:
      task_description: "Load images, run ResNet50 inference, export predictions to Parquet"
    assert:
      - type: contains
        value: "resnet"
      - type: contains
        value: "parquet"
```

## CI/CD Integration

Add to `.github/workflows/` or `pre-commit`:

```bash
npx promptfoo@latest eval -c promptfoo/promptfooconfig.yaml --output promptfoo-results.json
# Parse JSON and gate PR if pass rate < 80%
```

## Files

```
promptfoo/
├── promptfooconfig.yaml      # Main config (providers, prompts, tests)
└── README.md                 # This file
```
