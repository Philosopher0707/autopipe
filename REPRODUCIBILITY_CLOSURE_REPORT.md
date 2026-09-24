# REPRODUCIBILITY CLOSURE REPORT

> Fixed-format mission report (sections BASELINE–K). Labels follow
> NORTH_STAR: OBSERVED (measured/ran here) · SOURCE-DERIVED (read from
> code/tests/docs) · INFERRED · UNKNOWN. Mission phases: A seed · B
> artifacts · C dataset · D reassessment/docs · E e2e reproduction ·
> F adversarial · G perf recheck · H this report. Report section letters
> below (A–K) are the required fixed format and do **not** map 1:1 to
> mission phase letters.

---

## BASELINE:

- Mission baseline revision: `57db8694`.
- Final HEAD: code `d070725e` (all mission phases A–G); this report lands
  as the subsequent commit. Chain: `de220244` (A) → `5c45482c` (B) →
  `dca4eca0` (C) → `1bd5112c` (D reassessment/docs) → `52c4fd56`+
  `1b2f21ff` (E) → `7af0f430`+`26794bc5`+`d070725e` (F) → G (bench,
  numbers below, no repo commit — ad-hoc script) → this report.
- Baseline weak axis: reproducibility rated WEAK in the PHASE NEXT
  reassessment (`AUTOPIPE_CURRENT_ARCHITECTURE.md`, pre-closure 8/8/1/1);
  seed DECLARED-not-APPLIED, zero artifact registration writers, dataset
  identity MISSING. Evidence: §5–§7 of that document.

## A. SEED

- **Status:** DONE — OBSERVED via tests; invariant I21 VERIFIED.
- **RNGs covered:** one `RunRng` per run = seeded `random.Random` +
  `numpy.random.Generator`, created in `ExecutionEngine.execute` and bound
  as `step.run_rng` (attribute bind, like `cancellation_token`).
  `PartialDependenceStep` subsample consumes `run_rng` when bound, else a
  local `RandomState(42)` (legacy stream, no global mutation).
  SOURCE-DERIVED: schema validator `PipelineConfig.validate_seed` admits
  plain non-negative ints only.
- **Concurrency semantics:** never process-global seeding
  (`random.seed`/`np.random.seed` absent from the run path) — worker runs
  share one process on threads, so global seeding would cross-contaminate
  concurrent runs. OBSERVED: barrier-interleaved concurrent seeded runs do
  not cross-contaminate (`test_concurrent_seeded_runs_do_not_cross_contaminate`).
- **Tests:** `tests/unit/core/test_seed_reproducibility.py` (17 tests:
  schema/loader propagation, same/different/zero/absent seed, shared-stream
  identity across chained steps, seed-applied-on-step-failure, no global
  mutation, concurrency isolation, PDP subsample legacy equivalence,
  library path); `backend/tests/test_seed_application.py` (declared+applied
  e2e, unseeded neither, load-failure declared-not-applied, negative seed
  400, seed included in config_hash).
- **Invariant:** I21 — declared seed applied through run-local RNG,
  never global state; provenance distinguishes DECLARED
  (`provenance.seeds`, creation-time) from APPLIED
  (`provenance.seed_applied`, finalize-time iff the engine initialized the
  RNG; load failures stay DECLARED-only). Status: VERIFIED.
- **Commit:** `de220244`.

## B. FILE ARTIFACT REGISTRATION

- **Producers discovered:** SOURCE-DERIVED (commit `5c45482c` + code) —
  `ChartGenerator._save_fig` (one choke covers every chart PNG:
  VisualizationStep, data/deep_learning/core chart paths); explainability
  direct writes (SHAP/LIME HTML+PNG, permutation, PDP, feature-importance,
  attention); cross_validation visualize PNGs (cv_results/splits/bootstrap);
  drift_detection visualize PNGs + `generate_markdown_report` markdown;
  `SklearnTrainerStep.save_path` joblib dump.
- **Registered:** all of the above (run-path writers call
  `autopipe.core.artifacts.record_produced_file`; runner drains the
  worker-thread ContextVar and `_finalize` inserts `Artifact` rows via
  `RunStateStore.register_artifacts` before the terminal write). Idempotent
  per `(run_id, abspath)`; fail-soft per file (OSError skips that file,
  registration failure never blocks terminal state).
- **Unregistered (honest ceiling):** deep-learning Keras checkpoint files
  (async callback-chosen names); `model_registry` saves (separate library,
  Run-linkage is its own gap); `experiments/reporting`; CLI/REPL exports
  (not on the run path).
- **Intentionally excluded:** `steps/pi_coding*` (quarantined, I16);
  historical rows predating the hooks keep `sha256=NULL` = "not recorded"
  (I15: no retro-fitting, by design).
- **Hash semantics:** `sha256_file` (canonical in `core/artifacts.py`,
  re-exported by `app/db.models`) — raw file bytes, 64 KiB chunks, no
  text decoding; lowercase 64-hex; written by the single
  `@validates("file_path")` hook at attribute bind (construction or
  path reassignment), before INSERT; fail-closed (missing/unreadable file
  raises, no row persisted); metadata-independent; overwriting bytes
  behind the row leaves the stored hash unchanged (registration-time
  identity). Chart JSON identity remains `hash_config` (canonical JSON).
  Exactly two `.sha256 =` writers app-wide, both validates hooks.
- **Tests:** `backend/tests/test_artifact_registration.py` (8: content
  hash+size, type inference, idempotency, missing-file skip, unknown-run
  noop, empty/non-file inputs, `_finalize` bridge, e2e chart run);
  `tests/unit/core/test_produced_files.py` (6: recorder roundtrip, drain
  semantics, thread-locality, ChartGenerator records); plus
  `backend/tests/test_artifact_integrity.py` (16) from the hook commit.
- **Commit:** `5c45482c`.

## C. DATASET IDENTITY

- **Supported input types:** SOURCE-DERIVED + OBSERVED via tests —
  - local file (`steps/data.py::DataLoaderStep`, `os.path.isfile`):
    `{kind: "file", source: abspath, format, sha256}` — full identity;
  - builtin sample (`core/steps.py::DataLoaderStep`):
    `{kind: "builtin", name, sha256: "unavailable"}` — content is
    scikit-learn-version-defined; `scikit-learn` now pinned in
    `build_provenance._PACKAGES`;
  - sql: `{kind: "sql", format: "sql", sha256: "unavailable"}` —
    the connection string is **never recorded** (secret-shaped, I12);
  - other (URL/buffer/cloud): `{kind: "file", source, format, sha256:
    "unavailable"}` — read succeeded, no local bytes to hash.
- **Hash semantics:** sha256 hex of the exact bytes just consumed
  (`sha256_file`, 64 KiB chunks), computed immediately after a successful
  pandas read — read-time identity. OBSERVED: recorded hash equals
  `hashlib.sha256(original_bytes)`; post-load mutation does not follow
  (recompute diverges — detectable). Ceiling: the tiny post-read mutation
  window (documented).
- **Admission/run timing:** recorded at **execution** time (load-time),
  not admission — admission would hash bytes the run may not read and
  would block the API on hashing (SOURCE-DERIVED: decision recorded in
  PROVENANCE_MODEL Phase C). `runner._run_pipeline_in_thread` drains the
  ContextVar at start (hygiene) and in `finally`; `_finalize` calls
  `RunStateStore.record_dataset_inputs` before the terminal write,
  merging without clobbering sibling provenance keys
  (`seed_applied`, `origin`, …).
- **Failure semantics:** fail-closed hashing (missing/unreadable file
  raises before any entry is recorded); failed reads record nothing;
  non-dict entries skipped; a missing run logs and writes nothing; a
  later step failure does not erase evidence already recorded
  (`seed_applied` + `datasets` persist through finalize — OBSERVED on a
  FAILED-path e2e). Registration failure never blocks terminal state.
- **Tests:** `tests/unit/core/test_dataset_inputs.py` (11: recorder
  roundtrip/drain/thread-local/separation-from-artifacts, hash matches
  hashlib, fail-closed missing, csv records source+hash, sql never records
  connection, missing file raises before recording, iris builtin entry,
  unknown dataset records nothing); `backend/tests/test_dataset_provenance.py`
  (7: merge preserves siblings, bad-entry skip, unknown-run noop,
  `sha256_file` re-export identity, `_finalize` bridge, e2e file-loader
  hash, e2e builtin name).
- **Commit:** `dca4eca0`.

## D. END-TO-END REPRODUCTION

Suite: `backend/tests/test_reproduction_e2e.py` — one seeded config
(`seed=42`, tmp CSV `data_loader` + builtin `sample_data_loader`, Agg
matplotlib, `monkeypatch.chdir`) executed **twice** through the full
HTTP → admission → runner → engine → DB path. OBSERVED (all PASS):

- **Run A / Run B:** two sequential full-path executions of the identical
  `config_override` in one process/test session.
- **Same config:** `config_hash` identical across runs and non-None
  (canonical JSON hash of the admitted config copy).
- **Same code:** both runs execute the same working tree in one session
  (trivially identical; code identity itself is creation-time
  `provenance.code_revision` — see ceilings).
- **Same environment:** same process, same
  `provenance.environment` snapshot inputs.
- **Same seed:** `provenance.seeds == {"seed": 42}` and
  `provenance.seed_applied == 42` on **both** runs (DECLARED and APPLIED).
- **Same dataset identity:** `provenance.datasets` entries compare **equal**
  run-to-run, including a real (non-"unavailable") sha256 for the CSV and
  at least one builtin entry.
- **Same artifact identity:** `artifact_count > 0` (charts were produced)
  and the sorted lists of `Artifact.sha256` are **equal** across runs —
  content-addressed outputs.
- **Same metrics/output:** NOT ASSERTED as a separate axis — the test
  config emits no MetricLog series (loaders + print-class steps); output
  identity is covered by the artifact-hash equality above. Honest gap,
  queued in section K.
- **Differences:** run ids, run numbers, and wall-clock timestamps
  (SOURCE-DERIVED: inherently run-unique; not compared).

## E. ADVERSARIAL RESULTS

Suite: `backend/tests/test_reproduction_adversarial.py` (4 tests, PASS)
plus covered unit probes. OBSERVED:

- **Changed seed:** `test_different_seed_different_draws` — different
  seed → different `py`/`np` draws (seed is actually consumed, not
  decorative); same-seed identity is the converse test. PASS.
- **Changed input:** dataset file mutated **after** the run loaded it —
  the recorded hash still describes the read-time bytes, and recomputing
  now diverges: the attack is **detectable**, the row does not lie by
  silently following the file. PASS. (Admission-side config mutation is
  separately covered: `config_hash` is computed at insert from the run's
  own stored copy and never rewritten.)
- **Changed config:** `hash_config` is deterministic and key-order
  independent; pipeline config updates rewrite the pipeline's hash while
  existing Runs keep their own hash (immutable-by-API). Covered by
  `test_run_provenance.py`. PASS. (Per-run: same input config → same
  hash, section D.)
- **Changed code:** NOT ADVERSARIALLY PROBED end-to-end. Creation-time
  `provenance.code_revision` (git HEAD + `-dirty`, or explicit
  `"unavailable"` when git fails — unit-tested) is the mechanism; a
  mid-run edit window remains a documented ceiling (INFERRED: window =
  run duration). Honest gap, queued in section K.
- **Modified artifact:** file bytes overwritten behind a registered row —
  stored `sha256` does not follow the file; recomputing diverges:
  detectable. PASS.
- **Missing dataset:** missing/unknown file raises **before** any entry
  is recorded (fail-closed; no fabricated hash); unknown builtin dataset
  records nothing. Plus failure-path persistence: a run that loads a CSV
  and then fails still durably records `seed_applied` and the dataset
  entry (finalize runs before the terminal write; drain runs in
  `finally`). PASS.
- **Concurrency:** recorder hygiene — leftover ContextVar entries are
  cleared by the runner's start-of-run drain (no leak across runs on the
  same thread; second drain sees nothing). PASS. Seeded-run isolation
  under barrier interleaving (section A) PASS. Full-path conc=4 bench:
  4/4 success, no lock failures (section F).

## F. PERFORMANCE

- **Baseline** (OBSERVED, `AUTOPIPE_CURRENT_ARCHITECTURE.md` §2, pre-A–C,
  SQLite WAL, no-op print steps, full HTTP path, median of 7 after
  warmup): N=1 → 75 ms POST / 188 ms wall / 7 commits; N=10 → 29 / 192 /
  25; N=100 → 34 / 255 / 205 (**commits = 2N+5 exactly**); engine-only
  100 steps = 0.43 ms. Concurrency (10-step): 1→192 ms, 2→232 ms,
  4→262 ms, 4/4 success.
- **After changes** (OBSERVED, phase G re-run, same full path, machine
  load average ≈ 6 during measurement — honest ceiling on absolute
  numbers; median of 5–7 runs): N=1 → 71.7 / 197.7; N=10 → 59.8 / 202.3;
  N=100 → 58.0 / **337.4** (min 277.4); conc=4 × N=10 → 361.7 ms,
  **4/4 success**, no lock failures. Same order of magnitude as baseline;
  wall at N=100 is ~1.3× the pre-closure figure under a loaded machine —
  no structural regression (commit topology unchanged; no-op print steps
  produce zero artifact/dataset records, so finalize adds no writes on
  that path). An earlier G run on a heavily loaded moment showed N=100
  wall median 694 ms (max 1654) — absolute wall time is load-sensitive;
  the framework still finishes 100 steps in well under a second.
- **Hashing overhead:** not separately micro-benchmarked (UNKNOWN as a
  standalone delta). Design bound: one sha256 pass over bytes already
  read (loaders) or written (artifacts), 64 KiB chunks; print-step bench
  exercises zero hash work, so F/section deltas are framework-only.
- **Artifact overhead:** on paths that produce files, `_finalize` does
  one extra idempotent insert batch before the terminal write (≤1 extra
  commit when files exist; 0 when none). E2e chart-producing runs
  complete within normal test timeouts (OBSERVED: suite runtime
  unchanged within noise).
- **Dataset hashing overhead:** same shape — hash computed once per
  successful read at load; e2e file-loader runs pass in ~2 s total
  including HTTP/wait polling (OBSERVED via suite). Not isolated as a
  standalone number (UNKNOWN); bounded by file size, not step count.

## G. REPRODUCIBILITY MATRIX

| Axis | Status | Evidence / ceiling |
|------|--------|--------------------|
| Pipeline config | **CAPTURED (full)** | `Run.config` verbatim + `config_hash`; immutable-by-API; order-independent canonical hash (OBSERVED tests). |
| Code | **CAPTURED (creation-time)** | `provenance.code_revision` = git HEAD + `-dirty` or explicit `"unavailable"` (OBSERVED unit test for the unavailable path). Ceiling: mid-run edits undetected (INFERRED). |
| Environment | **CAPTURED (partial)** | python/platform/pinned packages incl. `scikit-learn` (I15 ceiling: transitive set not frozen). |
| Seed | **APPLIED (top-level)** | `RunRng` per run, never global; `seed_applied` recorded at finalize iff applied (I21 VERIFIED). Ceilings: step-level `random_state` params, torch global generator, LLM/GPU/provider nondeterminism, steps ignoring `run_rng`. |
| Model | **WEAK** | Provider + model *name* string in config only; no provider-side version pin (OUT OF SCOPE this mission; queue rank 5). Local weights hashable via `model_registry` but Run-unlinked. |
| Dataset | **CAPTURED (DataLoader path)** | file: abspath + load-time sha256; builtin: name (+ env pins sklearn); sql/other: explicit `"unavailable"`. Ceilings: non-DataLoader consumers, `DriftDashboardStep.reference_data_path`, read-time window. |
| Artifact | **CAPTURED (run path)** | ChartArtifact JSON hash + Artifact file-bytes hash at insert; run-path registration writer live (`5c45482c`). Ceilings: `step_id=NULL`, DL checkpoints, registry↔Run linkage, no verify endpoint. |
| Credentials | **CAPTURED by design (value-free)** | Provider name in config; secret *value* never recorded (I12 correct: this axis must stay value-free — reproducibility is by reference, not by value). |

## H. REMAINING CEILINGS

All documented in PROVENANCE_MODEL / ARCHITECTURAL_INVARIANTS; none are
hidden defects:

1. **Model identity unpinned** — provider may mutate a model behind a
   name; registry not Run-linked (queue rank 5, deliberately out of
   scope).
2. **Step-level seed visibility partial** — only top-level config seed is
   run-level; torch/LLM/GPU RNGs and steps ignoring `run_rng` are not
   covered (documented I21 ceilings; a partial fix would mislead).
3. **Transitive dependency set not frozen** — pinned package list only
   (I15 ceiling, queue rank 6).
4. **Registered artifacts carry `step_id = NULL`** — per-step attribution
   needs a Step-bound recorder (Phase B ceiling).
5. **DL checkpoints + `model_registry` not registered / not Run-linked.**
6. **Dataset ceilings** — sql/non-file sources record `"unavailable"`;
   non-DataLoader data consumers and
   `DriftDashboardStep.reference_data_path` not recorded; failed reads
   record nothing (correct, fail-closed); post-read mutation window
   (tiny, documented).
7. **No artifact verify endpoint** — divergence detection is manual
   (`sha256_file(path)` vs stored), same discipline as
   `model_registry.verify_artifact`.
8. **Code identity window** — mid-run edits after Run creation are not
   detected; git-unavailable environments record `"unavailable"`.
9. **E2e reproduction does not assert metric-series equality** (test
   config emits no metrics) and does not adversarially vary code (D/E
   honest gaps → K).
10. **No retro-fitting** — pre-hook rows keep NULL/"unavailable" forever
    (I15 non-goal, by design).
11. **Perf envelope unchanged** — no-op steps only; real workloads
    dominated by step bodies; absolute wall numbers load-sensitive.

## I. ARCHITECTURAL EFFECT

- **Added, no new top-level invariant beyond I21** — I21 (seed
  application) added VERIFIED; I14/I15 text updated for artifact
  registration + dataset identity (status-labeled, no silent rewrites).
- **Boundaries preserved** — execution-only boundary intact (core never
  imports the dashboard; `core.artifacts` is pure, ContextVar-based);
  single-writer DB rule intact (all new durable writes go through
  `RunStateStore` in `_finalize`, contained like `record_drift` before
  the terminal write); I12 not reopened (sql connection strings and
  secret values stay unrecorded); canonical hash producers remain exactly
  two (`hash_config`, `sha256_file`) plus password hashing (different
  domain).
- **No forbidden items** — no step retries, resume/checkpoints, Redis,
  Celery, Kafka, K8s, distributed execution, durable event log, OTel, or
  drift.alert subscriber touched (mission constraints respected).
- **Failure containment unchanged (I11)** — recorder/registration/
  dataset-write failures are contained and never block terminal state;
  failure injection tests green.
- **Docs updated where behavior changed** — PROVENANCE_MODEL (seed/
  artifact/dataset sections), ARCHITECTURAL_INVARIANTS (I21, I14/I15
  statuses), ARCHITECTURE/EXECUTION_MODEL (recorders), NORTH_STAR
  currency notice, AUTOPIPE_CURRENT_ARCHITECTURE reassessment, CONTEXT.
- **Test totals moved** 311→348 repo, 193→219 backend, 43 frontend; no
  existing test deleted or weakened (green stays green).

## J. FULL GATES

All run at final HEAD (`d070725e` + this report commit), sequential, no
races:

| Gate | Result |
|------|--------|
| `ruff check .` | PASS (0 errors) |
| `ruff format --check .` | PASS (154 files clean) |
| `mypy autopipe/core` | PASS (strict, 9 source files) |
| `git diff --check` | PASS (no whitespace errors) |
| `PYTHONPATH=. pytest tests -q` | **348 passed** |
| backend `pytest …/backend/tests -q` | **219 passed** |
| frontend `pnpm typecheck && pnpm test` | PASS, **43 passed** |

## K. NEXT EVIDENCE-BASED QUEUE

Ranked by evidence × leverage ÷ complexity. **Not implemented — this
report explicitly does not start any of these.**

1. **Metric-series equality in the e2e reproduction test** (extend D's
   config with one metric-emitting step; assert identical MetricLog
   rows) — closes the one honest assertion gap in section D. Low.
2. **Changed-code adversarial probe** (dirty the tree between two runs,
   assert `code_revision` differs and reproduction evidence flags it) —
   closes section E gap. Low.
3. **Coverage measurement** (`pytest-cov`, record % in gates) —
   quantifies test claims; baseline for regression checks (reassessment
   rank 4). Low.
4. **Resolved model-version recording** (provider response metadata →
   provenance; careful with I12) — model axis WEAK→ADEQUATE
   (reassessment rank 5). Medium.
5. **Transitive dependency freeze in provenance** — closes I15 ceiling
   (reassessment rank 6). Low-medium.
6. **Step-bound artifact recorder** (`step_id` attribution) + **DL
   checkpoint / registry Run-linkage** — closes Phase B ceilings when
   evidence of use appears. Medium.
7. **Artifact verify endpoint** (`sha256_file(path)` vs stored) —
   operationalizes divergence detection (PROVENANCE_MODEL ceiling). Low.
8. **DEFERRED (reaffirmed, zero supporting evidence at measured scale):**
   step retries/resume, distributed execution, Redis/Celery/Kafka/K8s,
   durable event log, drift.alert WS subscriber, OTel — do not start
   without new evidence.

---

*End of report. Mission phases A–H complete; gates green; queue K is
recorded for a future mission and was not started.*
