# AUTOPIPE — CURRENT ARCHITECTURE (PHASE NEXT reassessment)

> Evidence-driven reassessment of AutoPipe as of code commit `29dd8535`.
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
provenance, and (now) file-artifact hashes. Reproducibility and comparison
are first-class at the config/code/environment level; dataset identity and
step-level seeds are the standing gaps.

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
3. **Reproducibility gaps (see §6)** — seed is *declared* but never
   *applied* by the engine; dataset identity MISSING; model identity is a
   config string, not a pinned version. This is the weakest system-level
   axis.
4. **File-artifact registration writer still absent** — the sha256 producer
   (`29dd8535`) is enforced at every insert, but nothing creates rows for
   `figures/*.png`, LIME HTML, drift JSON, eval outputs. Integrity is
   correct-by-construction for rows that exist; coverage of produced files
   is 0 until a writer lands.
5. **No durable event log** — WS is fire-and-forget; polling is the
   authoritative read path (documented). Not a defect; a deliberate ceiling.
6. **Checkpoints are honest stubs** — GET returns `[]`, promote returns 501
   (SOURCE-DERIVED: `runs.py`). No checkpoint store exists. Correctly
   degraded, worth remembering before any "resume a run" feature request.
7. **Transitive dependency provenance is partial** — pinned package list
   captured; the resolved transitive set is not (I15 ceiling, documented).

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
| 8 | Provenance | **ADEQUATE** | Config+hash, code revision, env, top-level seeds captured (I14/I15); data identity MISSING, model version unpinned |
| 9 | Artifact integrity | **ADEQUATE** | Two canonical producers enforced at insert (chart JSON hash, file bytes hash, fail-closed); registration writer absent |
| 10 | Observability | **ADEQUATE** | WS events + run logs capture + MetricLog; no distributed tracing (DEFERRED — single process doesn't need OTel yet) |
| 11 | Concurrency | **ADEQUATE ≤4** | Measured 1/2/4 runs sub-linear, 4/4 success; semaphore design; UNKNOWN above 4 |
| 12 | Performance | **ADEQUATE at tested scale** | 255 ms / 100 steps / 205 commits measured; UNKNOWN beyond envelope |
| 13 | Scalability | **UNKNOWN beyond envelope** | Single process, single-writer SQLite, 4 slots — all measured only inside §2 bounds |
| 14 | Reproducibility | **WEAK** | Seed declared-not-applied; dataset identity missing; model not version-pinned (§6) |
| 15 | Experiment lifecycle | **ADEQUATE** | CRUD + trials (random/grid) + `best_run_id` + 3 compare endpoints; checkpoints stubbed honestly |
| 16 | Configuration lifecycle | **ADEQUATE** | Validate-at-load, hash, immutable-by-API, no hot reload (single writer by design) |
| 17 | Operational recovery | **ADEQUATE** | Startup sweep, graceful shutdown sweep + join, slot release on every path (I11) |
| 18 | Documentation truth | **STRONG** | Every behavior change ships doc updates; gates run per commit; invariant statuses labeled |

**Summary:** 8 STRONG, 8 ADEQUATE, 1 WEAK (reproducibility), 1 UNKNOWN
(beyond-scale scalability). No dimension rated from vibes — each row cites
tests, commits, or the bench above.

## 5. Reproducibility audit (axis-by-axis)

| Axis | Status | Detail |
|------|--------|--------|
| Pipeline config | **CAPTURED** | `Run.config` verbatim copy + `config_hash`; immutable-by-API |
| Code identity | **CAPTURED** (creation-time) | `provenance.code_revision` = git HEAD + dirty flag, or explicit `"unavailable"`; ceiling: mid-run edits undetected (INFERRED, window = run duration) |
| Environment | **CAPTURED (partial)** | python/platform/pinned packages; transitive set UNVERIFIED (documented I15 ceiling) |
| Seed | **DECLARED, NOT APPLIED** | Top-level config seed recorded in provenance; engine never calls `random.seed`/`np.random.seed` — only `explainability.py` hardcodes `np.random.seed(42)`. Application is per-step-author, UNVERIFIED system-wide |
| Model identity | **WEAK** | Provider + model *name* in config params only; providers may silently mutate models behind a name; local weights hashable via `model_registry` but that system is Run-unlinked (documented) |
| Dataset identity | **MISSING** | No input-file hashing in any provenance path (long-standing, honestly documented) |
| Artifact identity | **PARTIAL** | ChartArtifact JSON hash + Artifact file-bytes hash both enforced at insert; writer coverage of produced files = 0; registry hashes not Run-linked |
| Credential reference | **CAPTURED by design** | Provider name in config; secret *value* never recorded (I12 correct: this axis must stay value-free) |
| Compare | **SUPPORTED** | `POST /runs/compare` (2–10 runs, param+metric diffs), `GET /runs/{a}/compare/{b}`, `GET /experiments/{id}/compare` |

## 6. Experiment lifecycle audit (the §15 questions)

| Question | Status | Detail |
|----------|--------|--------|
| What produced this artifact? | **PARTIAL** | Registered artifacts carry `run_id`/`experiment_id` FKs; produced *files* (figures, LIME, drift, eval JSON) have no rows at all |
| Which run produced it? | **SUPPORTED** (for rows that exist) | FKs on ChartArtifact/Artifact; ceiling = registration writer absent |
| Which pipeline config? | **SUPPORTED** | `Run.config` + `config_hash` + `GET /runs/{id}/config` |
| Which code? | **SUPPORTED** | `provenance.code_revision` |
| Which environment? | **SUPPORTED** | `provenance.environment` (partial package list — documented) |
| Which model? | **PARTIAL** | Name string only; no provider-side version pinning |
| Can I reproduce it? | **PARTIAL** | config+code+env re-loadable; seeds not enforced; data identity missing; LLM providers nondeterministic by nature |
| Can I compare two runs? | **SUPPORTED** | Three compare endpoints (runs pairwise, runs 2–10 with % deltas vs baseline, experiment-by-metric); `Experiment.best_run_id/best_metric` |

Extras found (SOURCE-DERIVED): trials = random/grid search over a declared
search space (`experiments.py`); checkpoints = honest empty-list + 501 (no
store — do not promise resume); experiment artifacts endpoint serves
registered artifacts only.

## 7. Recommended next phase

**Theme: reproducibility closure** — attack the one WEAK dimension with
three small, evidence-driven changes. No infrastructure, no distributed
anything.

### Ranked queue — leverage × risk-reduction × evidence ÷ complexity

| Rank | Item | Leverage | Risk↓ | Evidence | Complexity | Verdict |
|------|------|----------|-------|----------|------------|---------|
| 1 | **Apply declared seed at run start** (engine/runner calls `random`+`numpy` seeding once from `Run.config`; record applied-at in provenance) | Closes the biggest honest hole: seed currently DECLARED-not-APPLIED | Repro failures become debuggable | §6 audit: no `set_seed` anywhere in core | ~10 lines + test | **DO NEXT** |
| 2 | **File-artifact registration writer** (small helper used by the 4-5 producers: hash via existing `sha256_file`, insert `Artifact` row) | Makes the `29dd8535` hook actually see rows; closes PROVENANCE gap | Unregistered outputs stop being invisible | CONTEXT KNOWN GAP names exactly this; producers located | one helper + call sites + tests | **DO NEXT** |
| 3 | **Dataset input hashing in provenance** (hash declared input file paths at admission, fail-soft like I12) | Closes the MISSING axis | Data drift becomes detectable | §6: axis MISSING, paths already in config | medium (path walk + fail-soft) | **DO NEXT** |
| 4 | Coverage measurement (`pytest-cov`, record % in gates) | Quantifies test claims | Baseline for future regression checks | Gates currently count tests only | low | Later |
| 5 | Resolved model-version recording (provider response metadata → provenance) | Model identity goes WEAK→ADEQUATE | Silent provider swaps detectable | §6 WEAK rating | medium (LLM client touch — careful with I12) | Later |
| 6 | Transitive dependency freeze in provenance | Closes documented I15 ceiling | Repro env exactness | I15 text | low-medium | Later |
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
- Test gates (this baseline): ruff/format/mypy/diff **PASS**; repo
  **311**; backend **193**; frontend **43**.
