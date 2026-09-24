# Provenance Model

**Status: MOSTLY IMPLEMENTED. Configuration-hash, engine/origin, environment,
code-revision snapshots, top-level seed declare+apply, run-path file-artifact
registration, and dataset input identity are implemented and tested.
Step-level data/seed provenance and registry↔Run linkage are not.** Per the
repository's no-fabricated-data rule,
**no provenance is recorded that the system cannot actually capture**; every
field that is still unimplemented is listed as such.

## Questions a Run must eventually answer

```
What pipeline was executed?          exists today as Pipeline.config JSON (copy)
Which version of that config?        DONE: Run.config_hash + Pipeline.config_hash
Which code revision?                 DONE: Run.provenance.code_revision (git HEAD
                                     at creation, -dirty suffix, or "unavailable")
Which environment / dependencies?    DONE: Run.provenance.environment (python,
                                     platform, package versions)
Which data?                          DONE (DataLoader path): run-path loaders
                                      record an entry per successful read into
                                      provenance.datasets — local file:
                                      abspath + read-time sha256; builtin
                                      sample: name + "unavailable"; sql:
                                      format only (connection never recorded);
                                      other sources: source + "unavailable"
                                      (Phase C ceilings below)
Which model / parameters?            not captured (partially in config)
Which random seeds?                  DONE (top-level): config `seed` copied into
                                     provenance.seeds at creation (DECLARED) and
                                     provenance.seed_applied at finalization iff
                                     the engine initialized run-local RNG from it
                                     (APPLIED); step-level cooperation still absent
Which artifacts?                     DONE (run path): files written by
                                     ChartGenerator, step visualize/save sites
                                     are recorded via core.artifacts and
                                     registered as `artifacts` rows (run_id,
                                     file-byte sha256, step_id NULL — Phase B);
                                     registry files still not Run-linked;
                                     deep-learning checkpoints not registered
Which execution engine version?      DONE: Run.provenance.engine_version
```

## Implemented (verified by `tests/test_run_provenance.py`)

- `hash_config(config)` (`app/db/models.py`) — sha256 hex of canonical JSON
  (`sort_keys=True`, compact separators, `default=str`); `None` hashes to
  `None`. Key order in the source dict cannot change the hash.
- `Pipeline.config_hash` — written by a SQLAlchemy `validates("config")` hook
  whenever `config` is set (creation and config updates both go through it).
- `Run.config_hash` — written when the Run row is inserted: trigger runs hash
  the admission output; experiment trials hash each trial config. The hash
  always describes the run's own stored `config` copy; it is **not** rewritten
  if the pipeline's config changes later.
- `Run.provenance` (JSON, `app/core/provenance.py::build_provenance`) —
  snapshot at Run creation on every creation path (dashboard trigger,
  experiment trials, demo seed):
  - `engine_version` — `autopipe.core.execution.ENGINE_VERSION`
  - `origin` — `"dashboard"` | `"experiment"` | `"seed"`
  - `environment` — python version, platform (recorded, deliberately
    excluded from the hash), and the full installed distribution set as a
    canonical-name → version dict; `environment_hash` = sha256 of canonical
    JSON over python + sorted package pairs. Computed once per run at
    creation; if metadata enumeration fails: `packages: {}`,
    `environment_hash: "unavailable"` (fail-open)
  - `code_revision` — `git rev-parse HEAD` from the backend dir, `-dirty`
    suffix if the work tree is dirty, `"unavailable"` if git cannot run
  - `seeds` — top-level `seed`/`seeds` keys from the run config, else NULL
- Unique `(pipeline_id, run_number)` with a retrying allocator
  (`app/api/v1/endpoints/run_numbers.py`): concurrent triggers can name and
  compare runs deterministically; exhaustion is an explicit 409, not a 500.
- `ChartArtifact.sha256` — written by a `validates("data")` hook with the
  same canonical `hash_config` used for configs: the chart's identity is its
  content, not its row id. `Artifact.sha256` — written by the single
  canonical producer `sha256_file` via a `validates("file_path")` hook (see
  "Artifact integrity" below). Rows that predate a hook keep the field NULL,
  which means "not recorded" (invariant I15). No retro-fitting.
- Rows that predate a migration keep the new field NULL, which means
  "not recorded" (invariant I15). No retro-fitting.

## Seed application (`provenance.seed_applied`, invariant I21)

- **DECLARED** — `provenance.seeds` written at Run creation from the config's
  top-level `seed` (plain non-negative int, enforced by
  `PipelineConfig.validate_seed`; the admitted config is persisted verbatim).
- **APPLIED** — `provenance.seed_applied` written by
  `RunStateStore.record_seed_applied` from `runner._finalize` (contained like
  `record_drift`, before the terminal write) **iff**
  `ExecutionResult.seed_applied` is non-None, i.e. the engine initialized a
  run-local `RunRng` from that seed. Load failures (engine never entered)
  therefore stay DECLARED-only.
- **Mechanism** — one `RunRng` (seeded `random.Random` + `numpy.random.Generator`)
  created per run inside `ExecutionEngine.execute` and bound as
  `step.run_rng` (attribute bind, like `cancellation_token`; never a
  `run()` kwarg). No process-global `random.seed`/`np.random.seed` is ever
  called: worker runs share one process on threads, so global seeding would
  cross-contaminate concurrent runs. `PartialDependenceStep` subsample uses
  `run_rng` when bound, else a local `RandomState(42)` (same legacy stream,
  no global mutation).
- **Guarantee** — same config (incl. seed) + code + env + inputs → identical
  `step.run_rng` draws for AutoPipe-owned consumers. **Not guaranteed**
  (ceilings): LLM/provider/GPU/torch RNG (e.g. `DataLoader(shuffle=True)`
  uses torch's global generator — not partially seeded, because a partial fix
  would mislead); step-level `random_state` params (declared, per-step);
  experiment trial generation at API time; steps that ignore `run_rng`.

## Artifact integrity (`Artifact.sha256`)

- **Meaning:** SHA-256 of the file's raw bytes that `file_path` pointed at
  when the row was created, or when `file_path` was last reassigned — a
  content address, not a row address (NORTH_STAR: identity is the hash, not
  the path).
- **When generated:** at attribute binding (`validates("file_path")`), i.e.
  construction or path reassignment, before the INSERT commits. Never
  retro-fitted, never a placeholder: a missing/unreadable file raises
  (FileNotFoundError / IsADirectoryError / PermissionError) and no row is
  persisted (fail-closed).
- **What exactly is hashed:** the exact byte stream, read in 64 KiB chunks —
  no text decoding, no newline/Unicode normalization. Lowercase hex, 64
  chars. Equivalent content on different paths hashes the same; any byte
  difference (encoding, newline, one flipped byte) changes the hash.
- **Can it change?** Only by re-binding `file_path` (the hook re-hashes).
  Row metadata (`name`, `artifact_type`, `meta_data`) never enters the hash.
  Overwriting the file's bytes *behind* the row leaves the stored hash
  unchanged — the hash describes registration-time content; divergence is
  detectable only by recomputing `sha256_file(path)` and comparing (same
  discipline as `model_registry.verify_artifact`; the dashboard has no
  verify endpoint yet — ceiling).
- **Provenance/integrity use:** content identity for dedup/comparison, and
  with the (nullable) `run_id`/`step_id` FKs it can anchor "which bytes did
  this run produce" once a registration path exists. The Python model
  registry hashes its own files (directory-aware, `model_registry`) but is
  not Run-linked yet (remaining gap below).
- **Canonical producers (exactly two):** `hash_config(dict)` (in
  `app/db/models.py`) → `ChartArtifact.sha256` / config hashes (canonical
  JSON: sorted keys, compact separators, `default=str`); `sha256_file(path)`
  (canonical definition in `autopipe/core/artifacts.py`, re-exported by
  `app/db.models`) → `Artifact.sha256` and loader dataset entries (raw file
  bytes). Password hashing in `core/auth.py` is a different domain (salting,
  not content addressing).

## File artifact registration (run path, Phase B)

- **Mechanism** — producers call
  `autopipe.core.artifacts.record_produced_file(path)` (thread-local
  `ContextVar`) as they write; `runner._run_pipeline_in_thread` drains the
  worker thread's list and passes it to `_finalize`, which calls
  `RunStateStore.register_artifacts(run_id, paths)` before the terminal write
  (contained like `record_drift`; a registration failure never blocks
  terminal state). Core never imports the dashboard (execution-only boundary).
- **Row content** — `run_id`, `name` (basename), `artifact_type` inferred from
  extension (`.png/.jpg/.jpeg/.svg/.pdf/.html` → `plot`;
  `.pkl/.joblib/.pt/.pth/.keras/.onnx/.h5` → `model`; else `data`),
  `file_path` absolutized, `file_size`, `sha256` from the existing
  `validates("file_path")` hook (fail-closed: an OSError skips that file and
  continues). `step_id` is **NULL** — no step association in Phase B
  (ceiling).
- **Idempotency** — per `(run_id, abspath)`; a path already registered for
  the run is skipped. Non-files (directories, ghosts) are skipped with a
  warning.
- **REGISTERED producers** — `ChartGenerator._save_fig` (one choke covers
  every chart PNG from `VisualizationStep` and every step that uses
  ChartGenerator: data, deep_learning, core); explainability direct writes
  (SHAP/LIME HTML+PNG/permutation/PDP/feature-importance/attention);
  cross_validation visualize PNGs (cv_results/splits/bootstrap);
  drift_detection visualize PNGs + `generate_markdown_report` markdown;
  `SklearnTrainerStep` `save_path` joblib dump.
- **NOT registered (honest ceiling)** — deep-learning Keras checkpoint files
  (async callback-chosen names); `model_registry` saves (separate library
  registry, run-linkage is its own gap); `experiments/reporting`,
  CLI/REPL exports (not on the run path); `steps/pi_coding*` (quarantined).

## Dataset input identity (run path, Phase C)

- **Mechanism** — loaders call
  `autopipe.core.artifacts.record_dataset_input(entry)` after a successful
  read (thread-local `ContextVar`, same pattern as Phase B);
  `runner._run_pipeline_in_thread` drains at start and in `finally` and
  passes the entries to `_finalize`, which calls
  `RunStateStore.record_dataset_inputs(run_id, entries)` before the terminal
  write (contained like `record_drift`; a failure never blocks terminal
  state). Sibling provenance keys (`seed_applied`, `origin`, ...) survive
  the merge; non-dict entries are skipped; a missing run logs and writes
  nothing. Recorded at **execution** time (load-time hash), not admission:
  admission would hash bytes the run may not read and would block the API
  on hashing.
- **Entry shapes** (no fabricated values; "unavailable" where identity
  cannot be computed):
  - local file (`steps/data.py` DataLoaderStep, `os.path.isfile`): `{kind:
    "file", source: abspath, format, sha256}` — hash computed immediately
    after the pandas read, of the bytes just consumed (read-time identity;
    the tiny window for post-read mutation is a ceiling).
  - builtin sample (`core/steps.py` DataLoaderStep): `{kind: "builtin",
    name, sha256: "unavailable"}` — content is scikit-learn-version-defined;
    the full installed-package snapshot in `build_provenance`
    (`environment.packages` + `environment_hash`) pins scikit-learn's
    version when installed.
  - sql: `{kind: "sql", format: "sql", sha256: "unavailable"}` — the
    connection string is **never recorded** (secret-shaped, I12).
  - other (URL, buffer, cloud): `{kind: "file", source, format, sha256:
    "unavailable"}` — read succeeded but no local bytes to hash.
- **Not covered (honest ceilings)** — steps that consume data without a
  DataLoaderStep; `DriftDashboardStep.reference_data_path` (stored, never
  read through a recorder); failed reads record nothing (record happens
  only after a successful read).

## Remaining gaps

- **Registry artifact ↔ Run linkage** — the Python model registry hashes
  files but does not record which Run produced them.
- **Deep-learning checkpoints** — Keras `save_path`/callback files are not
  routed through `record_produced_file` (async callback names).
- **Step association** — registered file artifacts carry `step_id = NULL`;
  attributing a file to the step that wrote it needs a Step-bound recorder.
- **Full seed provenance** — seeds declared inside step parameters (not
  top-level in config) are not visible to the Run-level snapshot; steps must
  opt into `self.run_rng` (cooperation unverified system-wide beyond the
  PDP consumer).
- **Model / parameter provenance** — only as far as the config itself states.

## Non-goals

- No retro-fitting of provenance onto historical rows.
- No invented values: if a fingerprint cannot be computed, the field records
  "unavailable", never a placeholder.
