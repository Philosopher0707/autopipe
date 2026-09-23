# AUTOPIPE — PHASE 0: PRODUCT & ARCHITECTURE NORTH STAR

**Version:** 0.1 (architecture-definition draft)
**Baseline revision:** `57db8694032c402ee97e479fe0a84c4f7165cb3e`
**Evidence basis:** direct source inspection at this revision; the forensic Repository Intelligence Report of the same revision (independently spot-verified where cited); executed test suites on this checkout (core 197 passed/2 skipped, backend 102 passed/119 warnings including worker-thread `OperationalError: no such table: runs`, frontend 34 passed); static symbol/dependency graphs (Python: 1,444 symbols, 245 internal import edges, no nontrivial SCC; TypeScript: 1,090 declarations).
**Status of this document:** architecture definition only. No production code, tests, dependencies, configuration, database, migrations, frontend, or deployment files were modified. No implementation plan is included.

Evidence labels used throughout:

- **OBSERVED** — directly verified from source or execution in this session.
- **SOURCE-DERIVED** — inferred by tracing implementation (static, not runtime-verified).
- **DOCUMENTED** — stated by repository documentation (may not match code; noted when it diverges).
- **INFERRED** — architectural interpretation by this document.
- **UNKNOWN** — not sufficiently established.
- **HYPOTHESIS** — proposed future direction; not a description of current behavior.

---

## 1. Executive Summary

AutoPipe today is two systems wearing one name:

1. A **Python scientific-pipeline library** — a synchronous, in-memory DAG engine with a genuinely rich step library (data, training, deep learning, cross-validation, evaluation, explainability, drift monitoring), a validated YAML configuration contract, and a credential/LLM layer. Its core semantic is *steps + DAG + outputs in process memory*.
2. A **dashboard product** (FastAPI + React) that wraps a *second, divergent execution loop* over SQL-tracked runs, with its own auth, its own telemetry channels, and its own statistical presentations.

The forensic evidence (independently re-verified at OBSERVED level below) shows the central structural fact: **the two execution loops have different semantics** (named input bindings and `step.output` exist only in core; the dashboard re-derives inputs from step names), and **durable evidence is fragmented** across SQL rows, filesystem artifacts, process memory, and browser state, with no provenance binding them.

**Chosen North Star (hypothesis, justified in §4):** AutoPipe should become an **agent-native research execution and evidence engine** — a Python-native system whose fundamental abstractions are *Experiment → Run → Step → Artifact → Evidence*, whose runs produce durable, provenance-linked evidence regardless of execution backend, and whose capability surface is explicitly bounded so that AI research agents can plan and execute experiments without unrestricted host access. The dashboard becomes a *projection* of that evidence, never its source of truth.

The single most important semantic correction this demands: **there must be exactly one execution semantic and one run-state machine, owned by the core library, which every executor (local Python, dashboard worker, future distributed worker) must implement.** Today there are two, and they already disagree.

**NORTH STAR STATUS: DEFINED (as hypothesis; see §29).**
**IMPLEMENTATION STATUS: PAUSED.**
**NEXT PHASE: ARCHITECTURAL SEMANTIC CONTRACT + INVARIANT FREEZE.**

---

## 2. Current System Identity

What AutoPipe *is* today (OBSERVED / SOURCE-DERIVED):

| Facet | Current reality | Evidence |
|---|---|---|
| Library | Synchronous DAG engine (`Pipeline.run`), validated YAML config, 34 YAML-addressable step classes | `autopipe/core/pipeline.py:38-119`; `autopipe/core/loader.py:26-164`; alias-coverage test `tests/unit/test_step_alias_coverage.py` (OBSERVED passing) |
| Dashboard backend | FastAPI; SQL-tracked runs; **its own step loop** that shares the loader but not `Pipeline.run` semantics | `B/app/executor/runner.py:225-229,425-433` vs `C/pipeline.py:83-107` (re-verified OBSERVED) |
| Persistence | 15-table SQL schema (`models.py`), 15 tables created by the single Alembic baseline; filesystem registry (separate); browser localStorage | `B/app/db/models.py` (24 tables enumerated in report; 15 app tables OBSERVED in migration verification earlier in session) |
| Identity | REST: JWT → active DB user. WS: token claims only, no DB-user check. Frontend run-detail WS URL omits token entirely. | `B/app/core/auth.py:83-135` vs `B/.../websocket.py:13-27`; `F/src/pages/runs/RunDetail.tsx:133-135` (re-verified OBSERVED) |
| Drift | Core detector produces in-memory reports; **zero** `DriftReport(` constructor references in executor (re-verified OBSERVED: count 0). Backend normalizes stored JSON for display; drift creation endpoints 501. | `B/app/utils/drift_utils.py:18-31` (verdict precedence OBSERVED); `B/app/api/v1/endpoints/drift.py:86-116` (SOURCE-DERIVED from forensic report) |
| Reproducibility | `Pipeline.config` and `Run.config` JSON exist; `config_hash` column exists on Pipeline; **no** environment/code/input/seed snapshots on Run | `B/app/db/models.py:78-79,146-158` (OBSERVED); absence verified by grep — no `dataset_uri/input_hash/provenance` fields (OBSERVED) |
| Packaging | Whole `autopipe*` tree ships in wheel including quarantined REPL/pi modules; extras add deps only | `pyproject.toml:109-115` (OBSERVED) |
| Eval | `promptfoo@latest` executed while probe checks `0.105` | `autopipe/eval.py:32,98` (OBSERVED) |

Documentation status: CLAUDE.md/AGENTS.md largely match implementation after the remediation series (OBSERVED for the claims re-checked). README/INTEGRATION_TESTS contain claims that diverge from inspected wiring (WS-aware fallback, HSTS, migration adoption) — treated as DOCUMENTED-but-divergent, not evidence.

---

## 3. Candidate Product Identities

**A. ML pipeline library.**
*Concept:* a pip-installable library of composable ML steps and a correct local DAG engine.
*Supporting capabilities:* the strongest part of the repo — 34 YAML-addressable steps, validated config schema, fit/transform preprocessing, statistical drift machinery.
*Conflicts:* none internally; but the dashboard's parallel loop undermines the "correct engine" claim, and ~800 lines of the step library have no tests beyond import smoke (INFERRED from test inventory).
*Would need to change:* single execution semantic (see §19), exception discipline (G4, paused mid-flight), de-duplicated drift statistics (two implementations: `steps/evaluation.py:422-515` vs `monitoring/drift_detection.py`).
*Unnecessary:* the second execution loop, as currently shaped.

**B. ML orchestration platform.**
*Concept:* schedule/queue/track runs across workers like Airflow/Prefect.
*Capabilities present:* daemon-thread executor, semaphore, cancellation registry, orphan sweep — all process-local.
*Conflicts:* no durable queue, no lease/ownership, no multi-process coordination; cancellation is between-steps only (SOURCE-DERIVED, forensic report §10 — accepted as high-confidence, not reproduced).
*Would need to change:* a real execution-boundary contract (queue, leases, state machine) before "platform" is honest.
*Unnecessary:* for the local-first user this is premature; most of the gap is semantic, not scale.

**C. Experiment management system.**
*Concept:* a system of record for experiments and their comparisons (MLflow/W&B territory).
*Capabilities:* Experiment/Run SQL models, trial generation, best-run fields, derived status.
*Conflicts:* trial `simulate=true` returns 501 **after** committing PENDING runs (SOURCE-DERIVED, forensic §19); experiment config is freeform JSON with no semantic validation; "experiment" in core (`experiments/reporting.py`) and dashboard are unrelated types.
*Would need to change:* a real Experiment contract (§5) rather than a config bag.
*Unnecessary:* the fabricated seed as the only writer of drift rows.

**D. Experiment execution + evidence engine.**
*Concept:* not just "run pipelines" but *produce durable, provenance-backed evidence about what happened and why a result is believed*.
*Capabilities today:* metrics dicts, Step.logs (populated by a separate endpoint, not the executor — SOURCE-DERIVED), artifacts table with content-hash discipline in the dashboard ORM (`sha256_file` + `validates("file_path")`, but no registration writer yet — SOURCE-DERIVED), config_hash column (used for provenance), SHA-256 in the *Python* registry (not Run-linked).
*Conflicts:* no bridge from core outputs to durable evidence; logs live/durable split; drift verdict re-derivation (fixed in G3 for readers, but the producer bridge still doesn't exist).
*Would need to change:* Evidence/Provenance as first-class entities (§8, §13); run lifecycle as an enforced state machine.
*Unnecessary:* multiple divergent verdict interpretations (largely consolidated already).

**E. AI/ML research laboratory infrastructure.**
*Concept:* the substrate a research team uses to run, compare, and *trust* experiments — levels 3–5 of the reproducibility ladder (§9).
*Capabilities:* everything in D plus environment/seed/lineage capture and comparison semantics.
*Conflicts:* no environment capture; no seed discipline; no lineage graph; LLM steps are non-deterministic with unpinned providers.
*Would need to change:* provenance snapshotting at Run creation; artifact content-addressing; capability-bounded agent entry.

**F. Agent-native scientific execution platform.**
*Concept:* the execution substrate an AI research agent drives through a bounded capability API (§15–16), producing evidence the agent can query and the human can audit.
*Capabilities today:* honest 501s and a pinned-probe eval harness are seeds of this; REPL/pi_coding show the current *unbounded* anti-pattern.
*Conflicts:* current agent-facing surface is "arbitrary Python via REPL" or "promptfoo subprocess" — exactly what a capability boundary must replace.
*Would need to change:* capability model, explicit authorization, evidence-first APIs.
*Unnecessary:* agent-as-root-shell philosophy.

**Candidate North Star problem statement (hypothesis):**

> AutoPipe should be the **trusted execution-and-evidence substrate for ML research**, where a human or an AI agent defines an Experiment, AutoPipe executes it under one semantic contract on whatever executor fits the scale, and every Run durably produces artifacts, metrics, and provenance sufficient to answer *"why do we believe this result?"* — locally first, distributively later, without the semantic contract changing.

Architectural implication: identities D/E/F share one spine (Experiment → Run → Evidence); A is the library layer of that spine; B and C are *projections* the spine must support, not the identity itself. The existing repo is closest to A with aspirations toward C; the seam evidence (dual loops, verdict drift, telemetry fragmentation) says the missing thing is **the evidence spine**, not more features.

---

## 3b. Deriving the hierarchy (input to §7)

The prompt's example hierarchy (`Research Objective → Experiment → …`) assumes research-objective as root. The repository has no Research Objective entity anywhere (OBSERVED — no such table/class). Deriving upward from what exists and what evidence requires:

- Steps produce outputs and metrics (OBSERVED).
- Runs group steps with configuration and status (OBSERVED, SQL).
- Experiments group runs with a shared config/search space (OBSERVED, SQL).
- Nothing groups experiments by question; nothing binds artifacts to the code+env+data that produced them.

Therefore the *derived* hierarchy has **Experiment as the root of execution semantics**, with Research Objective as an optional organizational layer above it (INFERRED; could be a tag/project, which the schema already has as `Project`). Adopting Research-Objective-as-mandatory-root would add a workflow layer with no current consumer; adopt it as optional grouping, not as a required primitive.

---

## 4. Chosen North Star Hypothesis

> **AutoPipe is an experiment execution and evidence engine for ML research, Python-native and local-first, whose every Run durably records what was configured, what executed, what was produced, and why each recorded result should be believed — with one execution semantic shared by every backend, and a bounded capability surface through which AI agents may act.**

This subsumes A (the library is the execution core), requires D (evidence spine), enables E (reproducibility ladder) and F (agent surface), and treats B (platform scale) as a later *deployment* evolution that must not change the semantic contract (§24). It deliberately demotes B and C from identity to capability.

---

## 5. Problem Statement

Researchers and research agents running ML experiments currently get execution *or* record-keeping, never both from the same contract: the library runs correctly and forgets; the dashboard records but executes differently. AutoPipe should make **the executed thing and the recorded thing the same thing**, with provenance durable enough to reconstruct belief, and boundaries tight enough that an autonomous agent can be given real compute without giving it the host.

---

## 6. Primary Users

| User | Role | Evidence/INFERRED basis |
|---|---|---|
| **Primary: ML researcher / research engineer** | defines Experiments, iterates Runs, needs trustworthy comparisons | INFERRED from step library's research orientation (CV, explainability, drift) and dashboard's experiment/trial UX; current repo optimizes for neither cleanly |
| **Secondary: AI research agent** | plans/launches/observes experiments through the API | the API surface already exists and is the only always-on interface; forensic report flags agent-shaped seams (trial dispatch, observe endpoints) |
| **Secondary: data scientist** | uses dashboard for runs/drift/charts | current React+backend surface |
| **Machine actor: executor** | runs steps; must be interchangeable | the local/dashboard seam proves this is already de-facto required |
| **Not first-class: platform engineer** | multi-tenant ops | the codebase has no tenancy model (SOURCE-DERIVED, forensic §4/§6); making them primary would force premature distributed semantics |

**Human-agent interaction model (HYPOTHESIS):** humans own intent and acceptance; agents compose Experiments and request capabilities; AutoPipe validates, authorizes, executes, and returns evidence. The agent never needs arbitrary Python — the step library *is* the capability set.

---

## 7. Semantic Model (derived hierarchy)

```text
Experiment            the question + the controlled variables (identity, config, hypothesis)
   ↓
Execution Plan        resolved step DAG + resource/seed policy (validatable before execution)
   ↓
Run                   one execution of a plan; the unit of evidence
   ↓
Step / Operation      one logged, bounded unit of work inside a Run
   ↓
Artifact              immutable, content-addressed output
   ↓
Metric                typed measurement attached to Run or Step
   ↓
Evidence              provenance-linked claim: metric/artifact + how it was produced
```

Deviation from the prompt's example, and why: **Research Objective** is optional scaffolding above Experiment (projects exist; make them semantic if needed) — not a required root, because evidence chains terminate at Runs, and agents can be productive without a mandatory objective tree. **Execution Plan is promoted to a first-class node** because today's core bug class (deferred load/cycle errors, config-vs-run divergence) comes from plans existing only implicitly.

---

## 8. Experiment Definition

**Contract (HYPOTHESIS, grounded in existing fields):**

- *Represents:* a controlled question: one hypothesis, one configuration family (base config + search space), one comparison policy.
- *Identity:* immutable `experiment_id`; human name is mutable metadata, not identity.
- *Inputs defining it:* resolved base config (steps, params, bindings), search space, dataset references (by artifact id, not path), expected metrics + direction, hypothesis text (free), code/environment references.
- *Mutability:* definition immutable after first Run; amendments create a new Experiment *revision* (HYPOTHESIS; current `Experiment.config` is mutable JSON — SOURCE-DERIVED `models.py:197-205`).
- *Two experiments differ if:* any of base config, search space, dataset refs, or expected-metric policy differ.
- *Contains:* many Runs (OBSERVED), zero-or-one hypothesis statement, expected metrics (direction policy exists implicitly in model-compare `registry/model_registry.py:491-494`), dataset/model/code *references* (ids + hashes, not copies).
- *Reproducible at:* Level 1–3 (config/data/environment refs); re-execution is Run-level.
- *Lifecycle:* `DRAFT → ACTIVE → FROZEN → ARCHIVED` (HYPOTHESIS; current status is *derived from runs* — SOURCE-DERIVED — which is observation, not lifecycle).

Current state maps as: dashboard `Experiment` ≈ ACTIVE experiments with config bags; core `experiments/reporting.py` is unrelated presentation code (KEEP as utility; CONSOLIDATE the name).

---

## 9. Run Definition

- *Identity:* `run_id` (uuid, OBSERVED) + monotonic `run_number` per parent (OBSERVED, but max+1 allocation is racy — SOURCE-DERIVED forensic §7).
- *Parent:* Experiment or Pipeline trigger (both exist; trials omit `project_id` — SOURCE-DERIVED forensic §19 — a hierarchy hole to close).
- *Configuration:* the **resolved, frozen** Execution Plan (not a pointer that can later drift).
- *Input snapshot:* artifact references + hashes for all bound inputs (today: absent — OBSERVED absence).
- *Environment/code identity:* absent today; required for Level ≥2 (§14).
- *Execution state:* **enforced state machine** (below), currently a permissive enum writers ignore (SOURCE-DERIVED forensic §8).
- *Outputs:* artifact references; *metrics:* typed, epoch-aware series (executor `mark_step` now inserts MetricLog rows in the CAS transaction — OBSERVED); *logs:* append-only, executor-written (today: a separate HTTP endpoint appends, executor broadcasts only — SOURCE-DERIVED forensic §12); *errors:* structured (type/message/step) — today a freeform `error_message`.
- *Nature:* append-only facts + state-machine status; **not** event-sourced in v1 (cost > value at this scale — INFERRED); **not resumable** across process death until a durable queue exists; cancellable with explicit semantics (§19 invariants).
- *Lifecycle (derived, tightening today's enum):* `CREATED → QUEUED → RUNNING → (SUCCESS | FAILED | CANCELLED)`; terminal states immutable; `PARTIAL` is a *derived view*, not a stored state (today it is a stored enum value — OBSERVED in `RunStatus`).

---

## 10. Step / Execution Definition

A Step is: a validated unit (params schema-checked at plan time, not constructor-time), executed exactly once per Run occurrence, producing zero-or-more Artifacts/Metrics/Logs, with an explicit cancellation token parameter (HYPOTHESIS: cooperative cancellation becomes part of the Step contract — the missing piece the forensic report identified).

Steps declare: inputs (named bindings — **core already has them; the dashboard loop must adopt them**, OBSERVED divergence), outputs (names + types, declared), resource hints, idempotency class (pure / retryable / side-effecting). This declaration is what later makes executor interchangeability possible without semantic drift.

---

## 11. Artifact Definition

Distinguish (extending the prompt's taxonomy with what the code actually has):

- **Data** — input datasets (immutable, content-addressed, referenced not copied).
- **Artifact** — any durable, immutable, content-addressed output: models, checkpoints, charts, reports, serialized intermediates.
- **Metric** — typed measurement (name, value, step/epoch, unit); not an artifact.
- **Log** — append-only observational stream; not an artifact (may be *anchored* to one).
- **Derived Result** — computed view over artifacts/metrics (e.g., "best run", normalized drift table); never authoritative.
- **Evidence** — a claim plus provenance (§12).

Contract (HYPOTHESIS, grounded in what the Python registry already does right — `model_registry.py:278-293` sha256 + verified load):

- *Identity:* content hash (sha256) + artifact_id; path is a storage detail, never identity.
- *Immutability:* write-once; mutation = new version.
- *Provenance:* producing run/step, input artifact refs, code+env identity.
- *Trust:* checksum verified on read **when recorded**; trust level recorded (producer-attested vs verified vs externally-signed); **no untrusted deserialization without explicit capability** (pickle is the current open hazard — SOURCE-DERIVED).
- *Lifecycle:* referenced by runs; GC only when unreferenced (today: registry has no GC; dashboard artifact rows dangle on file loss — INFERRED risk).
- *Ownership:* the Run that produced it; the registry *stores*, it does not own semantics.

---

## 12. Evidence Definition

**Evidence is a first-class concept** — it is the answer to *"why do we believe this result?"* and the differentiator vs. plain orchestration.

- *Evidence record:* `{claim, subject (run/step/metric/artifact), producer (step/evaluator), provenance (run_id, code, env, inputs), confidence (method-derived: e.g., BH-adjusted p), reproducibility (level achieved, §14), lineage (evidence ids consumed)}`.
- *Producers:* steps (statistical tests, evaluations), comparison operations, humans (annotations), agents (interpretations — always labeled as agent-generated).
- *Confidence:* never a bare number; always (value, method, sample size, correction applied). The BH machinery in `monitoring/drift_detection.py` is exactly the right seed for this.
- *Reproducibility:* an evidence record states which re-execution would regenerate it.
- *Lineage:* evidence may cite other evidence (comparison cites two runs' metrics); cycles disallowed.
- Current gap: everything needed exists in fragments (DriftReport JSON, metrics dicts, config_hash column) but no unified entity; dashboard "evidence" (charts, drift tables) is *derived projection* (OBSERVED via G3 consolidation).

---

## 13. Provenance Model

Provenance = the graph that makes Evidence answerable. Captured at Run creation and step completion:

`code (git SHA + dirty flag) · config (resolved plan hash) · inputs (artifact hashes) · environment (python/dep lock hash — **UNKNOWN today, no snapshot exists**) · seeds (absent today — OBSERVED no seed field) · hardware (optional, psutil exists in executor — OBSERVED) · external services (LLM provider+model+params — recorded in params today but not attested)`.

Enforcement mechanism (HYPOTHESIS): provenance is *written by the engine, not by steps* — steps cannot omit or forge it because the executor stamps it. This is the single highest-leverage invariant for research trust.

---

## 14. Reproducibility Model

Adopt the ladder; **target Level 4** for the platform, Level 3 as the near-term bar (HYPOTHESIS):

| Level | Meaning | AutoPipe today |
|---|---|---|
| 0 Result recorded | metrics/status stored | yes (SQL) |
| 1 Configuration reproducible | resolved plan + params recoverable | partial: `Run.config` JSON + unused `config_hash` |
| 2 Environment reproducible | deps/versions captured | **no** (no lock/env snapshot in Run) |
| 3 Input reproducible | data/model artifacts by hash | Python registry yes; dashboard runs: no input snapshot |
| 4 Execution reproducible | same inputs+code+env+seed → same result | **no** (no seeds, no env, two execution semantics) |
| 5 Independently reproducible | third party re-derives result | out of scope until 4 |

**Explicitly not guaranteeable by AutoPipe (must be documented, not faked):** external LLM/provider nondeterminism (temperature, model drift server-side); hardware nondeterminism for DL training (document per-step); wall-clock-dependent steps; user-supplied code with hidden I/O. AutoPipe's promise is *provenance completeness*, not bit-identical reruns.

---

## 15. Agent Model

Agents are **planners and clients, not hosts** (HYPOTHESIS, strongly supported by the anti-pattern already in-tree: REPL/pi_coding execute arbitrary subprocess code and were quarantined for exactly this reason — DOCUMENTED in CHANGELOG 0.2.0).

| Agent role | Allowed | Boundary |
|---|---|---|
| Pipeline generator | emit Execution Plans (YAML/JSON) | plan validation is the gate, not code |
| Experiment planner | create Experiments, propose search spaces | quota'd; no direct DB |
| Executor | request Runs, stream observation | through Run API only |
| Analyst | query evidence, compare runs | read-only; derived state labeled derived |
| Observer | subscribe WS | same identity rules as REST (fixes the current REST/WS divergence — SOURCE-DERIVED forensic §6) |
| Autonomous actor | multi-run campaigns | rate-limited, budgeted, human-auditable; never unrestricted process access |

The loop `Human → Agent → Experiment → AutoPipe → Evidence → Agent → Interpretation` is already *structurally* anticipated by the API surface (trials, artifacts, comparisons); the missing piece is authorization + evidence semantics, not new endpoints.

---

## 16. Capability Boundary

Minimum agent capability surface (derived from what the API already does + what evidence requires — HYPOTHESIS):

```text
create_experiment / validate_plan / plan_run / execute_run / observe_run /
cancel_run / get_artifacts / compare_runs / query_evidence / reproduce_run
```

- `Agent Intent → Validated Experiment → Authorized Capability → Execution → Evidence` — never `Agent → arbitrary Python → host`.
- Capabilities are *named, declared, and revocable*; step types are the existing natural capability registry (the loader's trusted-roots allowlist is the seed of this — OBSERVED `loader.py:79-84`).
- Destructive/host capabilities (shell, filesystem-write outside artifact store, network egress beyond providers) are **not** agent capabilities. Quarantined modules (REPL, pi_coding) stay human-opt-in forever.

---

## 17. Source-of-Truth Model

| Kind | Owner | Current reality |
|---|---|---|
| **Durable truth** | SQL (run/experiment/evidence records) + content-addressed artifact store | SQL exists; artifacts are loose files w/ hash only in Python registry; dashboard `artifacts` table lacks hash discipline |
| **Ephemeral state** | in-process run context, cancellation events, WS sockets | process-local, dies with process (OBSERVED) |
| **Derived state** | normalized drift tables, best-run, chart projections, experiment derived status | today sometimes *written back* (best-run fields) — must become pure views (HYPOTHESIS) |
| **Cached state** | React Query, credential cache, registry index snapshot | all staleable; none authoritative (OBSERVED) |
| **Observational** | logs, metrics streams | append-only facts; today partially *not persisted at all* (SOURCE-DERIVED) |

**Rule:** the Execution Plan + Run record are the single source of truth for *what happened*; the dashboard is a projection; the filesystem stores *content*; SQL stores *claims about content*. Two writers to one status field (executor + PATCH + sweep — SOURCE-DERIVED forensic §10) is the canonical violation to eliminate.

---

## 18. State Model

Terminal-state immutability is the core upgrade. `CREATED/QUEUED/RUNNING` are owned by the executor; `SUCCESS/FAILED/CANCELLED` are write-once with recorded `finished_at`, `duration`, `error`, and *who* decided (worker vs user vs sweep). Cancel is an *edge* (`CANCEL_REQUESTED → CANCELLED` on confirm), not an instant overwrite (fixes the finalization-race class from forensic §10). Browser and Query-cache state are projections with explicit invalidation contracts, never consulted for truth.

---

## 19. Execution Model

One semantic contract, many executors:

```text
                ExecutionPlan (frozen at Run creation)
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
   LocalExecutor     WorkerExecutor    SandboxExecutor (HYPOTHESIS, later)
   (in-proc, today)  (dashboard today,  (isolated process/container)
        │             reworked to        steps declare effects;
        │             delegate to core   capability-checked)
        │             Pipeline.run)      │
        └─────────────────┼────────────────┘
                          ▼
            Run state machine + Evidence emission
```

**The contract every executor must implement:** same plan hash → same step sequence; same binding semantics (named `inputs` win, deps promoted — core behavior, OBSERVED `pipeline.py:83-95`); same `step.output` lifecycle; same metric/log emission; same cancellation protocol (cooperative token *into* `step.run`); same provenance stamping. The dashboard's current private loop is the concrete violation to retire (KEEP the loader; REWORK the loop to call `Pipeline.run` with an injected state-sink).

---

## 20. Architectural Invariants

| # | Invariant | Rationale | Current status | Enforcement (future) |
|---|---|---|---|---|
| I1 | One execution semantic: every executor runs *the* core engine, not a re-implementation | forensic §9 divergence is the root seam | **violated today** | executor must call `Pipeline.run` (or a core-provided harness); conformance test suite shared by all executors |
| I2 | Run lifecycle is an enforced state machine; terminal states immutable | today PATCH + finalize + sweep race | **violated** | DB constraint/trigger + single-writer executor claim (lease) |
| I3 | Every Run durably records code, config, inputs, env, seed *before* first step | provenance is the product for research | **absent** (no fields) | snapshot-at-creation, hash-bound |
| I4 | Artifacts are content-addressed and immutable | identity ≠ path | partial (registry only) | content-address store; dashboard artifacts adopt sha256 |
| I5 | Evidence cites provenance; provenance is executor-stamped, not step-asserted | steps can't be trusted to self-report | absent | executor-side emission only |
| I6 | Derived/UI state is never authoritative | charts/drift tables re-derive today | partially held | all read models derived from Run+Evidence, recomputable |
| I7 | Cancellation is explicit: requested → confirmed; steps receive a token | today between-steps only, race-prone | **violated** | protocol in Step contract; conformance test |
| I8 | Same Experiment/Run semantics on every backend | core vs dashboard already differ | **violated** | semantic conformance suite (I1) |
| I9 | Agent capabilities are enumerated and bounded; no arbitrary-code capability | REPL/pi anti-pattern exists | **violated by opt-in tools** | capability registry; deny-by-default |
| I10 | Durable telemetry (logs, metric series, drift reports) is written by the executor at completion, not by a separate UI path | MetricLog rows in mark_step CAS txn; drift reports via `RunStateStore.record_drift` in `runner._finalize` (bridged `665ff239`) | **holds** | keep single-writer as new emitters land |
| I11 | Identical Plan + identical executor class ⇒ identical step sequence | provenance meaning | holds today trivially (single backend) | becomes load-bearing with worker/sandbox executors |
| I12 | Secrets resolve through one path, are never logged, never persisted in Run records | CredentialManager + `_resolve_api_key` single path; instance-scoped SDK clients; `PipelineConfig` rejects secret-shaped params (`SecretMaterialError`); `users.api_key` + `get_llm_config` removed; I12-H real-path log/failure witness; design: `docs/architecture/CREDENTIAL_REFERENCE_MODEL.md` (invariants doc I20) | holds (I12-A…I12-I IMPLEMENTED/VERIFIED incl. I12-H witness; T-G value-shape + third-party SDK loggers ceilings open) | optional value-shape heuristics; third-party SDK log audit with live keys |

---

## 21. Current → Future Gap Analysis

| North Star | Current state | Gap | Consequence | Future contract |
|---|---|---|---|---|
| One execution semantic | two loops | dashboard loop bypasses bindings/output | silent wrong results for `inputs:` configs | I1 conformance |
| Enforced lifecycle | enum writers ignore | races: queued→RUNNING, last-step cancel→SUCCESS | corrupted run history | I2 state machine + lease |
| Evidence spine | metrics dicts only; drift unbridged | no Run→Evidence emission | "why believe" unanswerable | I5, I10 emission adapters |
| Reproducibility | config JSON only | no env/code/seed/input snapshot | results can't be trusted or compared fairly | Level 3–4 capture at Run creation |
| Identity across transports | REST checks DB user; WS checks claims only | agent/observer sees stale identity | security seam | single authZ middleware for both |
| Agent capability | arbitrary Python (REPL) vs honest 501s | no capability model | unsafe autonomy | §16 registry |
| Artifact identity | paths-as-identity in dashboard | no content addressing in ORM store | untrustworthy comparisons | content-addressing |
| Provenance | `config_hash` unused; no seed/env | gap | Level ≤1 forever | I3 |

## 22. Subsystem classifications (classification only — no implementation)

| Subsystem | Class | Rationale |
|---|---|---|
| Core Pipeline/Step/loader + alias coverage | **KEEP** | the semantic kernel; conformance target |
| Config schema (Pydantic) | **KEEP**, extend | add plan/seed/env-reference fields |
| Step library (data/training/CV/eval/explain) | **KEEP**; dedupe drift-stats later | real capability; evaluation-vs-monitoring drift engines → **CONSOLIDATE** (Q10) |
| LLM clients/credentials | **REWORK** (light) | remove SDK-global key mutation; timeouts on OpenRouter; I12 |
| Model registry (Python) | **KEEP** as library; **CONSOLIDATE** identity model with future artifact store |
| FastAPI domain routers/schemas | **KEEP** as API; **REWORK** write paths to go through execution contract (trials-before-501, no-frontend drift writer confusion) |
| Executor loop | **REWORK** | delegate to core engine; add lease/state-machine (I1/I2) |
| Drift normalizer (backend) | **KEEP** (post-G3) as *derived-view* code; rename to make non-authority explicit |
| WS manager + RunDetail wiring | **REWORK** | single auth path; contract schemas; fix token/shape mismatches (Q01) |
| Auth core | **KEEP**; extend to WS; add ownership model decision (Q06) |
| Migrations | **KEEP**; add real revision path; stamp≠adopt must be documented (Q07) |
| React app | **KEEP**; treat as projection layer; fix WS contract + auth-state divergence |
| Seed | **QUARANTINE** | dev/demo only; never a production writer |
| REPL / pi_coding | **QUARANTINE** (status quo) → **DEPRECATE** from wheel (G6, paused) |
| eval / promptfoo | **REWORK** (pin executable; stale-result-file guard) — small |
| tracking/caching/observability | **REMOVE** (done, 1489da31) |
| trainer stubs | **REMOVE** (done, 54361a49) |
| Docker/compose | **REWORK** (packaging + core install + path assumptions — Q09) |
| `experiments/reporting.py` naming | **CONSOLIDATE** with dashboard Experiment semantics or rename |

---

## 23. Future Architecture (derived)

```text
            HUMAN ─┐
                   ├─→  INTENT (YAML/JSON plan or API call)
            AGENT ─┘            │
                                ▼
                     EXPERIMENT API  (validate · authorize · budget)
                                │
                       EXPERIMENT (immutable rev)
                                │
                       EXECUTION PLAN (resolved, hashed)
                                │
                    ┌────────── EXECUTION ENGINE (core) ───────────┐
                    │  state machine · binding · provenance stamp  │
                    └──────────┬──────────────┬───────────┬────────┘
                           LOCAL          WORKER       SANDBOX
                           (today)        (dashboard,   (later,
                            executor      delegates)    capability-bounded)
                                │              │            │
                                └──────┬───────┴────────────┘
                                       ▼
                        RUN RECORD (append-only facts)
                          │            │             │
                       ARTIFACTS     METRICS        LOGS
                          (content-addressed)
                                       ▼
                                    EVIDENCE
                                       ▼
                            PROVENANCE GRAPH  ←──── code/env/data snapshots
                                       ▼
                         RESEARCH API ── UI PROJECTION (derived only)
```

Change from the prompt's sketch: **Provenance feeds Evidence (not the reverse)**; the plan is materialized before execution; executors are peers behind one engine contract.

## 24. Local → Distributed Evolution

`LOCAL (today) → MULTI-WORKER → DISTRIBUTED` — stable across all transitions: the Plan hash, Run state machine, Step contract (incl. cancellation token), Artifact identity, Evidence emission, authZ model. What changes: *who* runs steps (process boundary ⇒ serialization contract for inputs/outputs becomes explicit), *who* owns the lease, *how* telemetry ships (push vs stream). **Nothing in the semantic layer may change** — that is I1/I8 restated as the evolution rule. Kubernetes/Rust/etc. are justified only when a *semantic* requirement (isolation, multi-tenancy, durable queueing) demands them — not now.

## 25. Agent-Native Architecture

Minimum surface (from §16), staged: (1) read/observe API hardening — cheap, high value; (2) plan validation + capability-scoped execute; (3) evidence query/compare; (4) reproduce_run (requires Level 3–4 provenance). The Wisp relationship question: AutoPipe should be **independent, exposing a stable API** — a candidate *capability execution substrate* for an agent runtime, never a merged runtime (no evidence in-repo of Wisp coupling; relationship kept at API level, INFERRED).

## 26. Explicit Anti-Goals

Not: generic workflow engine; Airflow/K8s replacement; full MLOps suite (no feature-store/serving layer); cloud provider; unrestricted agent host; notebook replacement; distributed scheduler for its own sake; a second dashboard execution semantic.

## 27. Open Architectural Questions

From the intelligence queue, the architecture-blocking ones: Q03 (execution-parity contract), Q04 (cancellation semantics), Q06 (tenancy/ownership), Q08 (evidence emission contract), Q09 (distribution boundary), Q10 (canonical drift engine), Q12 (removed-API compat). Each maps to an invariant above; none blocks the North Star, all block the *contract freeze*.

## 28. Recommended Next Investigation Phase

Per the prompt's own framing: **ARCHITECTURAL SEMANTIC CONTRACT + INVARIANT FREEZE** — write the machine-checkable contract for I1–I12 (state machine transitions, Step signature incl. cancellation token, evidence emission schema, artifact identity), each with the conformance test that would enforce it. That phase, like this one, is definition work; implementation remains paused.

## 29. Final North Star Statement

> **AutoPipe is the trusted execution-and-evidence engine for ML research: a Python-native system where an Experiment is a question, a Run is one execution of a resolved plan, and every Run durably records what ran, on what, producing what — with identical semantics on every backend, immutable terminal truth, content-addressed artifacts, executor-stamped provenance, and a bounded capability surface through which AI agents may plan, launch, observe, and interpret — but never reach past the engine into the host.**

The existing repository already contains the hardest parts of this (a correct local DAG, a validated config contract, real statistical machinery, a working artifact-hash precedent in the registry). What it lacks is the spine that makes those things *one system*: a single execution semantic, an enforced lifecycle, and an evidence layer that makes results believable. That spine — not scale, not features — is the North Star.

---

*NORTH STAR STATUS: DEFINED (hypothesis-grade: every HYPOTHESIS section above is derivation from OBSERVED/SOURCE-DERIVED evidence, but the product bet itself awaits stakeholder ratification).*
*IMPLEMENTATION STATUS: PAUSED.*
*NEXT PHASE: ARCHITECTURAL SEMANTIC CONTRACT + INVARIANT FREEZE.*
