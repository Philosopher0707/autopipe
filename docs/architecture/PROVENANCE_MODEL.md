# Provenance Model

**Status: MOSTLY IMPLEMENTED. Configuration-hash, engine/origin, environment
and code-revision snapshots are implemented and tested. Artifact linkage and
step-level data/seed provenance are not.** Per the repository's
no-fabricated-data rule, **no provenance is recorded that the system cannot
actually capture**; every field that is still unimplemented is listed as such.

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
Which random seeds?                  PARTIAL: top-level config `seed`/`seeds`
                                     copied into Run.provenance.seeds; step-level
                                     cooperation still absent
Which artifacts?                     registry has sha256; not linked to Run
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
- Rows that predate a migration keep the new field NULL, which means
  "not recorded" (invariant I15). No retro-fitting.

## Remaining gaps

- **Artifact linkage** — registry artifacts have sha256 but do not reference
  the Run that produced them.
- **Data provenance** — which dataset a run consumed; needs step cooperation.
- **Full seed provenance** — seeds declared inside step parameters (not
  top-level in config) are not visible to the Run-level snapshot.
- **Model / parameter provenance** — only as far as the config itself states.

## Non-goals

- No retro-fitting of provenance onto historical rows.
- No invented values: if a fingerprint cannot be computed, the field records
  "unavailable", never a placeholder.
