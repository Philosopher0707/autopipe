# 🚀 AutoPipe

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-261230.svg)](https://github.com/astral-sh/ruff)

An ML/DL pipeline framework with a built-in monitoring dashboard: define
pipelines as Python or YAML, run them locally or from the web UI, and track
runs, metrics, models and data drift in one place.

> **Status:** early beta (`0.1.x`). The core engine, step library and
> dashboard are functional; several advanced modules (distributed tuning,
> experiment tracking integrations) are being brought up to the same bar —
> see [ROADMAP.md](ROADMAP.md).

## ✨ Features

### Core engine
- **DAG pipelines** — `Pipeline` + `Step` classes with automatic topological
  ordering; define in Python or declarative YAML
- **Step library** — data loading/validation/preprocessing, sklearn /
  PyTorch training, cross-validation (K-Fold, stratified, time-series,
  group, nested), evaluation metrics, SHAP/LIME explainability
- **Model registry** — local versioned store with stage promotion,
  comparison and export
- **Drift detection** — KS, chi-square, PSI and Wasserstein-based feature /
  target / prediction drift reports
- **LLM steps & clients** — Ollama, OpenAI, Anthropic and OpenRouter
  clients usable directly or as pipeline steps
- **CLI + REPL** — `autopipe run/validate/create/models/eval` plus an
  interactive shell

### Dashboard (FastAPI + React)
- Runs, steps and live logs over WebSocket; experiment tracking and trial
  history; model registry UI with staging; drift reports and alerts;
  configurable multi-panel workspace for run analysis
- JWT auth, rate limiting, security headers
- Pages: overview, pipelines, runs, experiments, models, drift, AutoML
  trials, feature engineering, explainability, workspace

## 🚀 Quick start

```bash
pip install -e ".[dev]"        # from a checkout
pytest tests/unit -q           # verify your install
```

Define and run a pipeline:

```python
from autopipe import Pipeline, Step

class Preprocess(Step):
    def run(self, data=None, **kwargs):
        return data.dropna()

pipeline = Pipeline("my_pipeline").add_step(Preprocess("preprocess"))
results = pipeline.run(initial_inputs={"data": my_dataframe})
```

Or from YAML:

```bash
autopipe run examples/example_ollama_pipeline.yaml
```

See [examples/](examples/) for runnable configs covering LLM steps,
feature engineering and cloud models.

## 📊 Dashboard

```bash
# Backend (port 8765)
cd autopipe/dashboard/backend
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m app.seed          # optional demo data
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8765 --reload

# Frontend (port 3000, proxies /api → :8765)
cd autopipe/dashboard/frontend
pnpm install && pnpm dev
```

- API docs: `http://localhost:8765/api/v1/docs`
- Default seeded credentials: `admin` / `admin123` (**dev only** — change
  them before any real deployment)

## 🔍 LLM evaluation

Compare configured models on pipeline tasks via [promptfoo](https://promptfoo.dev)
(requires Node.js):

```bash
autopipe eval --config promptfoo/promptfooconfig.yaml
npx promptfoo@latest eval -c promptfoo/promptfooconfig.yaml   # direct
```

## 🏗️ Architecture

```
autopipe/
├── core/               # Pipeline/Step engine, YAML loader, builtin steps
├── steps/              # ML/DL step library (data, training, CV, XAI…)
├── registry/           # Model versioning and export
├── monitoring/         # Drift detection
├── tuning/             # Search spaces, Optuna search, schedulers
├── llm/                # Provider clients + factory
├── credentials/        # Credential resolution and masking
└── dashboard/
    ├── backend/        # FastAPI + async SQLAlchemy + executor
    └── frontend/       # React 18 + TypeScript + Vite + TanStack Query
```

## 🧪 Testing

```bash
pytest                              # everything under tests/
pytest tests/unit -q                # fast suite
pytest -m "not slow"                # skip slow-marked tests
pytest --cov=autopipe              # with coverage (gate: 80%)
```

Dashboard suites live next to their code (`dashboard/backend/tests/`,
`frontend/src/**/__tests__`); CI runs all of them — see
[CONTRIBUTING.md](CONTRIBUTING.md).

## 🤝 Contributing

Contributions welcome! Read [CONTRIBUTING.md](CONTRIBUTING.md) first — it
covers the three-subsystem layout, the no-fabricated-data rule, and the
exact checks CI will run.

## 📄 License

MIT — see [LICENSE](LICENSE).
