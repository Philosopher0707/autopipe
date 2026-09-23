# Provenance Model

**Status: MOSTLY IMPLEMENTED. Configuration-hash, engine/origin, environment,
code-revision snapshots, and top-level seed declare+apply are implemented and
tested. Artifact linkage and step-level data/seed provenance are not.** Per the
repository's no-fabricated-data rule, **no provenance is recorded that the
system cannot actually capture**; every field that is still unimplemented is
listed as such.

## Questions a Run must eventually answer

```
What pipeline was executed?          exists today as Pipeline.config JSON (copy)
Which version of that config?        DONE: Run.config_hash + Pipeline.config_hash
Which code revision?                 DONE: Run.provenance.code_revision (git HEAD
                                     at creation, -dirty suffix, or "unavailable")
Which environment / dependencies?    DONE: Run.provenance.environment (python,
                                     platform, package versions)
Which data?                          not captured
Which model / parameters?            not captured (partially in config)
Which random seeds?                  DONE (top-level): config `seed` copied into
                                     provenance.seeds at creation (DECLARED) and
                                     provenance.seed_applied at finalization iff
                                     the engine initialized run-local RNG from it
                                     (APPLIED); step-level cooperation still absent
Which artifacts?                     PARTIAL: dashboard chart_artifacts carry
                                     sha256 of canonical data JSON (content
                                     address) + run_id linkage; registry has
                                     file sha256 but not linked to Run; file
                                     `artifacts` rows now always carry a
                                     file-byte sha256 at insert (hook, this
                                     phase) — but no code path registers rows
                                     yet (NULL only on pre-hook rows)
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
  - `environment` — python version, platform, versions of a fixed package
    list (`autopipe`, `fastapi`, `sqlalchemy`, `pydantic`); uninstalled →
    `"unavailable"`
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
- **Canonical producers (exactly two, both in `app/db/models.py`):**
  `hash_config(dict)` → `ChartArtifact.sha256` / config hashes (canonical
  JSON: sorted keys, compact separators, `default=str`); `sha256_file(path)`
  → `Artifact.sha256` (raw file bytes). Password hashing in `core/auth.py`
  is a different domain (salting, not content addressing).

## Remaining gaps

- **Registry artifact ↔ Run linkage** — the Python model registry hashes
  files but does not record which Run produced them.
- **File-artifact writer** — the dashboard `artifacts` table still has no
  code path that inserts rows; the hash producer now exists and is enforced
  at the insert boundary (any future writer cannot skip it, and unreadable
  files fail the insert).
- **Data provenance** — which dataset a run consumed; needs step cooperation.
- **Full seed provenance** — seeds declared inside step parameters (not
  top-level in config) are not visible to the Run-level snapshot; steps must
  opt into `self.run_rng` (cooperation unverified system-wide beyond the
  PDP consumer).
- **Model / parameter provenance** — only as far as the config itself states.

## Non-goals

- No retro-fitting of provenance onto historical rows.
- No invented values: if a fingerprint cannot be computed, the field records
  "unavailable", never a placeholder.
