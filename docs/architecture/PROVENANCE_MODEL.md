# Provenance Model

**Status: PROPOSED. Nothing in this document is implemented yet.**

This document exists to state the target honestly and to record what already
exists as an anchor point, so that the eventual implementation does not have to
invent a shape under pressure. Per the repository's no-fabricated-data rule,
**no provenance is currently recorded that the system cannot actually capture**,
and no field below is populated today.

## Questions a Run must eventually answer

```
What pipeline was executed?          exists today as Pipeline.config JSON (copy)
Which version of that config?        config_hash column exists; NO writer found
Which code revision?                 not captured
Which environment / dependencies?    not captured
Which data?                          not captured
Which model / parameters?            not captured
Which random seeds?                  not captured
Which artifacts?                     registry has sha256; not linked to Run
Which execution engine version?      ExecutionResult.engine_version (in memory only)
```

## What already exists (anchor points, VERIFIED to exist but not persisted)

- `ExecutionResult.engine_version` — set by the engine on every result.
- `ExecutionContext.metadata` — a free-form, injected dict; the dashboard
  currently stores `{"origin": "dashboard", "engine": ENGINE_VERSION}` there.
  It is **not** persisted.
- `ExecutionResult.to_dict()` — a JSON-safe summary that excludes output
  payloads; a candidate payload for a future durable record.
- `Pipeline.config_hash` — a database column with **no writer**. Either it gets
  one or it should be removed; a column that looks like provenance but is never
  populated is worse than no column.

## Target shape (PROPOSED)

Incremental, smallest-first:

1. **Configuration hash** — write `config_hash` when a run is created from a
   config. Cheap, unblocks reproducibility comparisons.
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
