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
- **Reproducible by construction** — a top-level `seed:` governs the data
  split, the estimator, cross-validation folds, bootstrap resampling, feature
  selection, permutation importance and the drift null. Same seed and data →
  same split, same model, same curve.
- **Model registry** — local versioned store with stage promotion,
  comparison and export
- **Drift detection** — KS, chi-square, PSI and Wasserstein, each reported as
  a *permutation p-value* and decided after Benjamini-Hochberg correction, so
  the false-alarm rate is set by your significance level rather than by your
  dataset size
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
outputs = pipeline.run(initial_inputs={"data": my_dataframe})
```

`pipeline.run()` returns a dict of step outputs keyed by step name.

## 🎯 Training a model

The pattern that matters: **split once, name your target column, and set a
seed.** All three are easy to get silently wrong.

```yaml
name: credit_baseline
seed: 42                     # governs the split, the model and every fold
steps:
  - name: split
    type: data_splitter
    params:
      train_size: 0.7
      val_size: 0.15
      test_size: 0.15
      stratify: true
      target_column: target   # required for stratify to do anything
  - name: train
    type: sklearn_training
    depends_on: [split]
    params:
      target_column: target   # names the label instead of guessing "last column"
      use_cross_validation: true
      cv_folds: 5
```

```bash
autopipe run credit_baseline.yaml
```

Two things to know before you rely on this:

- **`target_column` is not optional in practice.** Without it the trainer
  assumes the label is the *last column*. If that is wrong you get a model
  trained on the wrong target — no error, just a useless model.
- **`stratify` needs `target_column` on the splitter too.** Set on one and not
  the other and the split quietly is not stratified; AutoPipe logs a warning
  when it cannot honour the request.

The trainer returns the fitted estimator, and writes per-metric cross-validation
means to the step's metrics (available via `pipeline.get_step("train").metrics`).
A fold whose scorer was undefined — `roc_auc` on a single-class fold returns
`NaN` — is excluded from the mean and counted in `cv_val_<metric>_dropped_folds`,
never averaged in and never stored as a number.

### Available step types

`data_loader`, `data_validator`, `preprocessing`, `feature_selection`,
`data_splitter`, `cross_validation`, `nested_cross_validation`,
`stratified_group_kfold`, `bootstrap_validation`, `sklearn_training`,
`hyperparameter_tuning`, `pytorch_training`, `tensorflow_training`,
`transfer_learning`, `model_evaluation`, `explainability`,
`permutation_importance`, `shap_explainer`, `lime_explainer`,
`feature_importance`, `statistical_drift_detection`, `target_drift_detection`,
`prediction_drift_monitoring`, `drift_dashboard`, `llm`, `print`,
`visualization`, `feature_engineering`. The full alias table is
`BUILTIN_ALIASES` in `autopipe/core/loader.py`.

See [examples/](examples/) for runnable configs covering LLM steps, feature
engineering and cloud models.

## 📊 Dashboard

```bash
# Backend (port 8765)
cd autopipe/dashboard/backend
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -e ../../..   # core library, from the REPO ROOT (not ../..)
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
├── schemas/            # Pydantic pipeline/step config
├── experiments/        # Experiment tracking
├── visualization/      # Chart generation
├── data/               # Shared data types
├── utils/              # Shared numeric helpers
└── dashboard/
    ├── backend/        # FastAPI + async SQLAlchemy + executor
    └── frontend/       # React 18 + TypeScript + Vite + TanStack Query
```

### Behavioural contracts

Correctness properties are written down and machine-checked in
[`docs/architecture/`](docs/architecture/), not left to prose. Each invariant
carries one status — **VERIFIED** (a passing test enforces it), **IMPLEMENTED**
or **PROPOSED**. Start with
[ARCHITECTURAL_INVARIANTS.md](docs/architecture/ARCHITECTURAL_INVARIANTS.md).

The ones that bite hardest, all found by review rather than by a bug report:

| | |
|---|---|
| **I24** | A training step consumes the dataset it was configured to train on — train/test leakage is unreachable |
| **I25** | A declared run seed reaches every stochastic step, not three of them |
| **I26** | Cross-validation honours its own `groups`/`metrics`, and never reports an undefined fold as a measurement |
| **I27** | Every drift method reports whether it detected drift |
| **I28** | A drift verdict is a calibrated, multiplicity-corrected test, not a fixed threshold |
| **I29** | Evaluation resolves label↔column mapping from the fitted model |
| **I30** | Per-run state on a reused step does not leak into the next run |

A behavioural baseline that exercises the real engine lives in
`baseline/run_baseline.py`, with `baseline/mutation_check.sh` proving the
baseline can actually go red when the engine is broken.

## 🧪 Testing

```bash
pytest                              # everything under tests/
pytest tests/unit -q                # fast suite
pytest -m "not slow"                # skip slow-marked tests
python3 baseline/run_baseline.py    # engine behavioural baseline
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