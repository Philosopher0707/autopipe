# AUTOPIPE — CURRENT ARCHITECTURE (PHASE NEXT reassessment)

> Evidence-driven reassessment of AutoPipe as of code commit `29dd8535`,
> **reassessed after reproducibility closure (commits `de220244` / `5c45482c`
> / `dca4eca0`, phases A–C)** — evidence-changed rows updated in place;
> **updated after the Model Identity & Environment Exactness mission
> (commits `9f45a8e5`…`15c86abc`)** — model/environment audit rows and
> queue ranks updated with new evidence.
> Labels: OBSERVED (measured/ran here) · SOURCE-DERIVED (read from code/docs)
> · INFERRED · UNKNOWN (no evidence either way) · DEFERRED (deliberately out
> of scope). This document is the PHASE NEXT deliverable; it does not
> implement anything. Mission constraints respected: no step retries, no
> distributed execution, no Redis/Celery/Kafka/K8s, no drift.alert subscriber,
> no I12 reopening — none of these were proven the correct next move.

---

## 1. What AutoPipe is (one paragraph)

A single-process ML pipeline runner: FastAPI dashboard (JWT, rate-limited,
WS + polling read paths) admits validated pipeline configs, a bounded thread
pool (4 slots) runs them through one canonical execution engine, and a
single-writer SQLite layer persists run state, metrics, charts, drift,
provenance, and file-artifact hashes. Reproducibility and comparison
are first-class at the config/code/environment/seed/dataset level; model
identity is captured at name level (requested + resolved, I22) but not
content-pinned, and step-level seed visibility is a standing gap.

## 2. Measured performance baseline (OBSERVED)

Local machine, SQLite WAL, no-op `print` steps, real full path
(HTTP → admission → runner threads → engine → per-step DB commits).
Engine-only numbers: median of 7 runs after warmup.

| Steps (N) | POST latency | Wall to terminal | DB commits | commits/step |
|-----------|-------------:|-----------------:|-----------:|-------------:|
| 1         | 75 ms        | 188 ms           | 7          | 2.00 (warm)  |
| 5         | 30 ms        | 139 ms           | 15         | 3.00         |
| 10        | 29 ms        | 192 ms           | 25         | 2.50         |
| 25        | 34 ms        | 199 ms           | 55         | 2.20         |
| 50        | 33 ms        | 198 ms           | 105        | 2.10         |
| 100       | 34 ms        | 255 ms           | 205        | 2.05         |

**Commits = 2N + 5 exactly** (2 per step: RUNNING + terminal, via
`mark_step`; +5 lifecycle: run insert, pipeline/create-steps, run-running,
finalize, plus one warmup item at N=1). MetricLog rows ride the same
transaction (0 rows: `print` steps emit no metrics).

Engine-only (no DB): 100 steps = 0.43 ms median → **~0.004 ms/step**.
The DB/HTTP path costs ~2.5 ms/step end-to-end; the engine is ~600×
cheaper than its surrounding plumbing. Both are negligible next to real
step bodies (LLM/network/GPU).

Concurrency (10-step runs, per-request sessions, at the `MAX_CONCURRENT_RUNS=4` design point):

| Parallel runs | Wall   | Success | Commits |
|---------------|-------:|---------|--------:|
| 1             | 192 ms | 1/1     | 25      |
| 2             | 232 ms | 2/2     | 50      |
| 4             | 262 ms | 4/4     | 100     |

Wall grows sub-linearly (192 → 262 ms for 4× the work): SQLite WAL absorbs
4 concurrent writers with no lock failures, no failed runs, no 409s.
Beyond 4 the 5th run queues in-thread (slot acquired inside the worker, not
the request path — OBSERVED: `runner.py:336`).

**Honesty ceiling:** no-op steps only. Real workloads are dominated by step
bodies; these numbers bound the *framework* overhead, which stays ≤ ~2.5 ms
per step and ≤ ~255 ms per 100-step run at the tested scale.

## 3. Bottlenecks & risks (ranked)

1. **Single-writer SQLite beyond the tested envelope** — UNKNOWN past
   4 parallel runs / 100-step runs / long-lived DBs. Evidence stops at the
   table above. Mitigation exists (semaphore caps writers at 4); ceiling is
   untested, not theoretical-unknown-but-fine.
2. **2N+5 commits per run** — cheap on WAL today (measured); becomes the
   first thing to batch if step counts go to thousands or step bodies turn
   sub-millisecond *and* runs multiply. `ponytail:` per-step commit, batch
   mark_step if throughput ever matters.
3. **Reproducibility residual (see §6)** — top-level seed now *applied*
   via run-local RNG (`de220244`), dataset identity captured on the
   DataLoader path (`dca4eca0`), model identity captured at name level —
   requested + resolved (`4069e2df`, I22) — and the full resolved package
   set hashed (`9f45a8e5`, I23); LLM content-hash pinning and step-level
   seed visibility remain partial. This is no longer the weakest
   system-level axis.
4. **File-artifact registration ceiling narrowed** — the writer landed
   (`5c45482c`): run-path producers register rows with content hashes.
   Remaining: DL checkpoint callbacks, `model_registry` Run-linkage,
   CLI/REPL exports (documented in PROVENANCE_MODEL).
5. **No durable event log** — WS is fire-and-forget; polling is the
   authoritative read path (documented). Not a defect; a deliberate ceiling.
6. **Checkpoints are honest stubs** — GET returns `[]`, promote returns 501
   (SOURCE-DERIVED: `runs.py`). No checkpoint store exists. Correctly
   degraded, worth remembering before any "resume a run" feature request.
7. **Environment exactness stops at Level 2** — full resolved package set
   + python hashed (`9f45a8e5`, I23); no lockfile is produced (the hash
   records, it does not pin re-resolution), and Level 3 system layers
   (OS/CUDA/glibc/BLAS) are UNKNOWN beyond the `platform.platform()` string.

## 4. The 18 dimensions

| # | Dimension | Rating | Evidence |
|---|-----------|--------|----------|
| 1 | Execution correctness | **STRONG** | One engine (I1–I4), binding resolution, shipped-examples-execute tests |
| 2 | Run state machine | **STRONG** | I5–I7 transition gate, CAS writes, 409 on illegal transitions, terminal immutability |
| 3 | Failure semantics | **STRONG** | I11–I12 every worker path → FAILED; startup/shutdown orphan sweeps; observed in bench (0 failures under load) |
| 4 | Admission / config validation | **STRONG** | I8–I10 loader plan/binding/unknown-key checks; I19 no Run row for unrunnable config; I16 quarantine choke point |
| 5 | Security & credentials | **STRONG** | I12-A…I12-I + I20 one env path, sentinel tests, secret-param deny, instance-scoped API keys |
| 6 | Rate limiting | **STRONG** | I18 wired before auth on all HTTP routes, headers + 429/Retry-After, WS handshake 1013 |
| 7 | WS contract | **STRONG** | Envelope-only `{type,data,timestamp}`, contract doc + parse-guard tests both sides |
| 8 | Provenance | **ADEQUATE** | Config+hash, code revision, full resolved env set + `environment_hash` (I23), top-level seeds applied, dataset identity (DataLoader path), run-path artifact registration (I14/I15), model identity requested+resolved (I22); remaining: LLM content-hash absent, registry Run-unlinked, non-DataLoader data sources record "unavailable" |
| 9 | Artifact integrity | **ADEQUATE** | Two canonical producers enforced at insert (chart JSON hash, file bytes hash, fail-closed); run-path registration writer exists (`5c45482c`); DL checkpoints + registry Run-linkage still open |
| 10 | Observability | **ADEQUATE** | WS events + run logs capture + MetricLog; no distributed tracing (DEFERRED — single process doesn't need OTel yet) |
| 11 | Concurrency | **ADEQUATE ≤4** | Measured 1/2/4 runs sub-linear, 4/4 success; semaphore design; UNKNOWN above 4 |
| 12 | Performance | **ADEQUATE at tested scale** | 255 ms / 100 steps / 205 commits measured; UNKNOWN beyond envelope |
| 13 | Scalability | **UNKNOWN beyond envelope** | Single process, single-writer SQLite, 4 slots — all measured only inside §2 bounds |
| 14 | Reproducibility | **ADEQUATE** | Seed applied via run-local RNG (I21); dataset identity captured (DataLoader path); artifact registration live; model identity requested+resolved at name level (I22); environment resolved-set hash (I23); remaining: LLM Level 3 content hash, step-level seeds partial, no lockfile (§5/§6) |
| 15 | Experiment lifecycle | **ADEQUATE** | CRUD + trials (random/grid) + `best_run_id` + 3 compare endpoints; checkpoints stubbed honestly |
| 16 | Configuration lifecycle | **ADEQUATE** | Validate-at-load, hash, immutable-by-API, no hot reload (single writer by design) |
| 17 | Operational recovery | **ADEQUATE** | Startup sweep, graceful shutdown sweep + join, slot release on every path (I11) |
| 18 | Documentation truth | **STRONG** | Every behavior change ships doc updates; gates run per commit; invariant statuses labeled |

**Summary:** 8 STRONG, 9 ADEQUATE, 0 WEAK, 1 UNKNOWN
(beyond-scale scalability). No dimension rated from vibes — each row cites
tests, commits, or the bench above. (Pre-closure: 8/8/1/1 with
reproducibility WEAK; dimension 14 re-rated after A–C.)

## 5. Reproducibility audit (axis-by-axis)

| Axis | Status | Detail |
|------|--------|--------|
| Pipeline config | **CAPTURED** | `Run.config` verbatim copy + `config_hash`; immutable-by-API |
| Code identity | **CAPTURED** (creation-time) | `provenance.code_revision` = git HEAD + dirty flag, or explicit `"unavailable"`; OBSERVED e2e discrimination (`cc2a5416`): two full-path runs under controlled differing HEADs record their exact respective revisions while `config_hash`/seed/dataset stay equal (config and code are separate dimensions); ceiling: mid-run edits undetected (INFERRED, window = run duration) |
| Environment | **CAPTURED** (Level 2) | Full installed-distribution snapshot (python + platform + canonical name→version dict) + `environment_hash` = sha256 over python + sorted package pairs, computed once per run (`9f45a8e5`, I23; `test_environment_identity.py` OBSERVED: deterministic, order-independent, discriminates version/python change, fail-open "unavailable"); config/env separation OBSERVED (`test_identity_adversarial.py::TestConfigModelEnvironmentSeparation`). Ceilings: no lockfile; platform recorded but excluded from hash; Level 3 system layers (OS/CUDA/glibc/BLAS) UNKNOWN — `platform.platform()` string only |
| Seed | **APPLIED** (top-level) | Top-level config seed → `RunRng` run-local RNG bound per step (`de220244`, I21); `provenance.seed_applied` records the runtime fact. Ceilings: step-level `random_state` params, torch global RNG, LLM/GPU nondeterminism (PROVENANCE_MODEL) |
| Model identity | **CAPTURED** (Level 1+2, name-level) | `provenance.models` records requested identity from config at admission (REQUESTED_ONLY) and resolved identity from provider `response.model` at execution (RESOLVED / explicit UNAVAILABLE) (`4069e2df`+`0f94597e`, I22; `test_model_identity.py` + alias-attack OBSERVED in `test_identity_adversarial.py::TestModelAliasAttack`: equal `config_hash`, resolved revision-a≠b; four provider clients tested); credential-safe (names only). Ceilings: no content-hash Level 3 for LLMs; provider aliasing beyond exposed `response.model` is a provider ceiling; local `model_registry` artifacts hashed but Run-unlinked |
| Dataset identity | **CAPTURED** (DataLoader path) | Loaders record `provenance.datasets` entries at execution (`dca4eca0`): local file abspath + read-time sha256, builtin name, sql format-only (connection never recorded); non-file sources and non-DataLoader steps = documented ceilings |
| Artifact identity | **CAPTURED** (run path) | ChartArtifact JSON hash + Artifact file-bytes hash enforced at insert; run-path producers register rows via `5c45482c`; registry hashes not Run-linked; DL checkpoints unregistered |
| Credential reference | **CAPTURED by design** | Provider name in config; secret *value* never recorded (I12 correct: this axis must stay value-free) |
| Compare | **SUPPORTED** | `POST /runs/compare` (2–10 runs, param+metric diffs), `GET /runs/{a}/compare/{b}`, `GET /experiments/{id}/compare` |

## 6. Experiment lifecycle audit (the §15 questions)

| Question | Status | Detail |
|----------|--------|--------|
| What produced this artifact? | **SUPPORTED** (run path) | Registered artifacts carry `run_id`/`experiment_id` FKs; produced run-path files (figures, LIME, drift, trainer saves) now get rows (`5c45482c`); ceilings: DL checkpoints, model_registry, CLI/REPL exports |
| Which run produced it? | **SUPPORTED** (for rows that exist) | FKs on ChartArtifact/Artifact; run-path writer landed (`5c45482c`); registry↔Run linkage still open |
| Which pipeline config? | **SUPPORTED** | `Run.config` + `config_hash` + `GET /runs/{id}/config` |
| Which code? | **SUPPORTED** | `provenance.code_revision` |
| Which environment? | **SUPPORTED** (Level 2) | `provenance.environment` — full resolved package set + `environment_hash` (deterministic, order-independent; I23); ceiling: no lockfile, Level 3 system layers UNKNOWN |
| Which data? | **SUPPORTED** (DataLoader path) | `provenance.datasets` — file sha256 at read time; sql/non-file = explicit "unavailable" (`dca4eca0`) |
| Which model? | **SUPPORTED** (name-level) | `provenance.models` — requested from config, resolved from provider response with explicit REQUESTED_ONLY/RESOLVED/UNAVAILABLE status (`4069e2df`+`0f94597e`; alias attack OBSERVED `15c86abc`); ceilings: no content-hash Level 3, provider aliasing beyond `response.model` |
| Can I reproduce it? | **SUPPORTED** (local, non-LLM) | config+code+env re-loadable; top-level seed applied via RunRng; dataset bytes hashed at read; artifacts content-addressed; model identity distinguishes aliasing runs at name level; MetricLog series equality OBSERVED for the tested deterministic local workload (`8d9e7cad`: step_index/step_name/metric_name/value exact). Ceilings: LLM providers nondeterministic by nature; no LLM content-hash; step-level seeds partial |
| Can I compare two runs? | **SUPPORTED** | Three compare endpoints (runs pairwise, runs 2–10 with % deltas vs baseline, experiment-by-metric); `Experiment.best_run_id/best_metric` |

Extras found (SOURCE-DERIVED): trials = random/grid search over a declared
search space (`experiments.py`); checkpoints = honest empty-list + 501 (no
store — do not promise resume); experiment artifacts endpoint serves
registered artifacts only.

## 7. Recommended next phase

**Theme: reproducibility closure (completed)** — three small,
evidence-driven changes against the then-WEAK reproducibility dimension,
re-rated ADEQUATE after A–C. Current ratings (§4): 8 STRONG / 9 ADEQUATE /
0 WEAK / 1 UNKNOWN. No infrastructure, no distributed anything.

### Ranked queue — leverage × risk-reduction × evidence ÷ complexity

| Rank | Item | Leverage | Risk↓ | Evidence | Complexity | Verdict |
|------|------|----------|-------|----------|------------|---------|
| 1 | **Apply declared seed at run start** (engine/runner calls `random`+`numpy` seeding once from `Run.config`; record applied-at in provenance) | Closes the biggest honest hole: seed currently DECLARED-not-APPLIED | Repro failures become debuggable | §6 audit: no `set_seed` anywhere in core | ~10 lines + test | **DONE `de220244` (I21)** |
| 2 | **File-artifact registration writer** (small helper used by the 4-5 producers: hash via existing `sha256_file`, insert `Artifact` row) | Makes the `29dd8535` hook actually see rows; closes PROVENANCE gap | Unregistered outputs stop being invisible | CONTEXT KNOWN GAP names exactly this; producers located | one helper + call sites + tests | **DONE `5c45482c`** |
| 3 | **Dataset input hashing in provenance** (hash declared input file paths at admission, fail-soft like I12) | Closes the MISSING axis | Data drift becomes detectable | §6: axis MISSING, paths already in config | medium (path walk + fail-soft) | **DONE `dca4eca0`** (executed at load, not admission — see PROVENANCE_MODEL Phase C) |
| 4 | Coverage measurement (`pytest-cov`, record % in gates) | Quantifies test claims | Baseline for future regression checks | Gates currently count tests only | low | Later |
| 5 | Resolved model-version recording (provider response metadata → provenance) | Model identity was WEAK at queue time; now CAPTURED L1+2 (§5) | Silent provider swaps detectable | Model axis rated WEAK at queue time (pre-re-rate; §6) | medium (LLM client touch — careful with I12) | **DONE `4069e2df`+`0f94597e` (I22; adversarial alias probe `15c86abc`)** |
| 6 | Transitive dependency freeze in provenance | Closes documented I15 ceiling | Repro env exactness | I15 text | low-medium | **DONE `9f45a8e5`+`12927a57` (I23: full resolved set + `environment_hash`; no lockfile — deliberate non-goal)** |
| 7 | Step retries / resumability | — | — | **No evidence** (checkpoints honestly stubbed; containment already works) | — | **DEFERRED** |
| 8 | Distributed execution / Redis / Celery / Kafka / K8s | — | — | **No evidence**: 4-slot semaphore absorbs tested load | — | **DEFERRED** |
| 9 | Durable event log (events table) | — | — | Polling is authoritative read path (D8) | — | **DEFERRED** |
| 10 | drift.alert WS subscriber | — | — | Contract documented; polling works | — | **DEFERRED** |
| 11 | OTel / tracing | — | — | Single process, measured overhead trivial | — | **DEFERRED** |

Rationale for ranking 1–3: they are the only items where the audit produced
*direct evidence of a gap* (declared-vs-applied seed, zero registration
writers, MISSING data axis) **and** the fix reuses machinery that already
exists (engine start, `sha256_file`, config file paths). Items 7–11 were
reviewed and explicitly *not* proven as the correct next move.

## 8. Mission compliance (§10/§16)

- Forbidden items: none implemented, none recommended as next (see ranks
  7–11). I12 untouched beyond citing its ceilings.
- Artifact-integrity work was committed focused: `29dd8535` (6 files,
  +247); this document is a separate docs commit.
- Residual search: exactly two `.sha256 =` writers app-wide, both
  validates hooks (`hash_config` → chart, `sha256_file` → file); password
  salting lives in `core/auth.py` (different domain, documented).
- Test gates (current, after identity mission): ruff/format/mypy/diff
  **PASS**; repo **348**; backend **260**; frontend **43**.
