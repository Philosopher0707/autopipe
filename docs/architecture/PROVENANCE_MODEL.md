# Provenance Model

**Status: PARTIAL. Configuration-hash provenance (target step 1) is
implemented and tested. Steps 2–5 below are not.** Per the repository's
no-fabricated-data rule, **no provenance is recorded that the system cannot
actually capture**; every field that is still unimplemented is listed as such.

## Questions a Run must eventually answer

```
What pipeline was executed?          exists today as Pipeline.config JSON (copy)
Which version of that config?        DONE: Run.config_hash + Pipeline.config_hash
Which code revision?                 not captured
Which environment / dependencies?    not captured
Which data?                          not captured
Which model / parameters?            not captured
Which random seeds?                  not captured
Which artifacts?                     registry has sha256; not linked to Run
Which execution engine version?      ExecutionResult.engine_version (in memory only)
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
- Unique `(pipeline_id, run_number)` with a retrying allocator
  (`app/api/v1/endpoints/run_numbers.py`): concurrent triggers can name and
  compare runs deterministically; exhaustion is an explicit 409, not a 500.
- Rows that predate the migration keep `config_hash = NULL`, which means
  "not recorded" (invariant I15). No retro-fitting.

## Anchor points (VERIFIED to exist but still not persisted)

- `ExecutionResult.engine_version` — set by the engine on every result.
- `ExecutionContext.metadata` — a free-form, injected dict; the dashboard
  currently stores `{"origin": "dashboard", "engine": ENGINE_VERSION}` there.
  It is **not** persisted.
- `ExecutionResult.to_dict()` — a JSON-safe summary that excludes output
  payloads; a candidate payload for a future durable record.

## Target shape (PROPOSED)

Incremental, smallest-first:

1. **Configuration hash** — DONE (see above).
2. **Engine + coordinator identity** — persist `engine_version` and the origin
   (`cli` / `dashboard` / `worker`) on the Run.
3. **Environment fingerprint** — Python version, package versions, at run
   creation. Explicitly unavailable rather than guessed when it cannot be read.
4. **Artifact linkage** — registry artifacts reference the Run that produced
   them, with the existing sha256.
5. **Data and seed provenance** — requires step-level cooperation; only
   recorded where a step genuinely knows it.

## Non-goals

- No retro-fitting of provenance onto historical rows.
- No invented values: if a fingerprint cannot be computed, the field records
  "unavailable", never a placeholder.
