# Credential Reference Model (NORTH_STAR I12)

Design-first contract for secret handling: where key material may live, how it
is referenced by durable state, and the boundaries it may never cross.
Implementation follows this document; each claim carries an evidence label.

Numbering note: NORTH_STAR calls secrets invariant **I12**; this document's
invariants are I12-A…I12-I (sub-invariants of the NORTH_STAR row). The
`ARCHITECTURAL_INVARIANTS.md` numbering already uses I12 for terminal-state
completeness — there the secrets contract is recorded as **I20**.

---

## 1. Current-state flow map (OBSERVED)

| Path | Location | Evidence | Boundary label |
|------|----------|----------|----------------|
| `users.api_key` column | removed (`2fa61352`, migration `f2a9c1d4e7b8`) | zero accessors/serialization ever; residual `rg` audit clean | **DEAD (removed)** |
| `Config.get_llm_config` + `Config.*_API_KEY` attrs | removed (`2fa61352`) | only caller was their own tests; `cli.py` uses `os.getenv` directly | **DEAD (removed)** |
| Env vars → `CredentialManager` → `Credentials` | `autopipe/credentials/manager.py` | env-only load (docstring previously claimed file/config priority — corrected); frozen dataclass; per-provider cache | **SAFE** (runtime only) |
| `_resolve_api_key(provider, explicit, default)` | `autopipe/llm/client.py:13` | priority: explicit arg > CredentialManager > default; single choke point for client constructors | **SAFE** |
| `LLMStep` → `LLMFactory.create_client` | `autopipe/core/steps.py:59` | no inline key; resolves from env at construction (first `run()`) | **SAFE** |
| `LLMProviderConfig.api_key` schema slot | `autopipe/schemas/models.py:74` | no production importer of `AutoPipeGlobalConfig`; footgun, not a live path | **UNKNOWN → removed** (I12-G) |
| `StepConfig.params` free-form dict | `schemas/models.py:15` → `Run.config` | admitted config is persisted verbatim; nothing forbade `api_key:` in params | **UNSAFE (closed by I12-A enforcement)** |
| Provenance snapshot | `app/core/provenance.py` | fixed field list (engine/origin/packages/platform/code/seeds); never `os.environ` | **SAFE** (regression-tested) |
| RunEvent / MetricLog / WS envelopes | `sink.py`, `websocket.py` | status/log/metric/drift payloads; no credential fields | **SAFE** |

Live flow: process env (`T1`) → `CredentialManager` cache (`T2`) → client
instance at construction (`T3`) → Authorization header / SDK client (`T4`).
Material exists only in process memory between `T2` and process exit.

## 2. Invariants

| ID | Invariant | Status |
|----|-----------|--------|
| I12-A | Durable state (Run.config, provenance, events, artifacts) holds credential **references**, never material. Enforced by `PipelineConfig` secret-param validation at load — the same choke point every config path (CLI, YAML, dashboard admission) passes through (I16 pattern). | IMPLEMENTED — test below |
| I12-B | Resolution happens at execution boundary: env → `CredentialManager` → `_resolve_api_key` → client constructor. Nothing resolves earlier or elsewhere. | VERIFIED (`_resolve_api_key` is sole importer of `get_credentials` outside tests) |
| I12-C | Provenance, RunEvent, MetricLog never contain secret material. Provenance fields are a fixed list; sentinel test greps the persisted DB. | IMPLEMENTED — sentinel test |
| I12-D | Missing credential fails deterministically and closed: `ConfigurationError`/`ValueError` naming the **env var**, never a value; step → FAILED → run terminal (I11 containment). | VERIFIED (`test_credentials.py`, client constructors) |
| I12-E | Identical semantics on CLI, library, YAML, dashboard admission — all configs validate through `PipelineConfig.model_validate`. | VERIFIED (single loader; admission wraps loader) |
| I12-F | No process-global secret mutation (no `openai.api_key = …`). Instance-scoped clients only. | VERIFIED (`test_llm_client.py` sentinel-global assertion) |
| I12-G | Serialized references are non-secret by construction: schemas offer no field that accepts key material (`LLMProviderConfig.api_key` removed). | IMPLEMENTED |
| I12-H | Key material never appears in log output; `Credentials.masked_key` is the only formatter permitted near logging. | PARTIAL — no emission site exists (rg audit); masking formatter unexercised in anger |
| I12-I | One credential subsystem: `credentials/` + `llm/client.py::_resolve_api_key`. No dashboard-, CLI-, or step-local credential loading. | VERIFIED (call graph audit) |

## 3. Secret lifetime (T0–T10)

| Stage | Event | Guarantee |
|-------|-------|-----------|
| T0 | Operator creates key | outside the system |
| T1 | Process env / `.env` via `load_dotenv` | never dumped (provenance fixed fields) |
| T2 | First `CredentialManager.get_credentials` — cached per provider | cache is in-process dict; `clear_credential_cache()` drops it |
| T3 | Client constructor stores key on instance | instance-scoped; not shared across clients (I12-F) |
| T4 | Use: Authorization header / SDK call | header never logged; HTTP errors carry URL not headers |
| T5 | Logging boundary | no emission site; `masked_key` for any future site (I12-H) |
| T6 | Persistence boundary | deny-list at load (I12-A); provenance fixed fields (I12-C) |
| T7 | Serialization (API/WS/artifacts) | refs only; schemas closed (I12-G) |
| T8 | Rotation | set new env + `clear_credential_cache()`; already-constructed clients keep the old key until re-created (`LLMStep` caches `self.client` for the run) — ceiling documented |
| T9 | Process exit | memory released; no at-rest footprint |
| T10 | Retirement | env unset; next construction fails closed (I12-D) |

## 4. Threat model

| # | Attack | Boundary | Mitigation | Witness |
|---|--------|----------|------------|---------|
| T-A | Config author embeds `api_key: sk-…` in `params` → persisted in `Run.config`, returned by API, greppable in DB | load/admission | `PipelineConfig` rejects deny-listed param keys (normalized exact/suffix match, non-empty value); error names key+step only | deny-list unit tests |
| T-B | Nested smuggle `params: {client: {api_key: …}}` | load | recursive walk, depth limit 10 (ceiling: deeper nesting rejected) | nested unit test |
| T-C | Provenance env dump leaks keys | run creation | fixed field list, never `os.environ` | sentinel provenance test |
| T-D | Log/WS broadcast echoes a key | logging | no emission site; run-log payloads are step text (I12-H) | rg audit + sentinel DB grep |
| T-E | SDK global key mutation cross-leaks | client | instance-scoped (closed `881beb4b`-era) | `test_llm_client.py` |
| T-F | User-row API key (old design) | DB | column removed (`2fa61352`) | `test_users_api_key_column_removed` |
| T-G | Value under innocuous key (`data: "sk-…"`) | load | **not caught by key-name check** — accepted ceiling; value-shape heuristics rejected (false positives on ids); rely on T-A key naming + review | documented ceiling |

## 5. Design decision: reference indirection

Key material in configs is rejected, not scrubbed (scrubbing silently mutates
intent; rejection is deterministic, I12-D-consistent). References are the
existing provider→env-var-name mapping:

- default: `provider: openrouter` → `OPENROUTER_API_KEY` (env alias list in
  `CredentialManager`), resolved at construction;
- in-process/library callers may pass `api_key=` **explicitly** — legal only
  because it can never reach durable state (constructed objects are not
  serialized);
- future multi-credential support extends `CredentialManager`'s provider map;
  the reference *syntax* in configs does not change (provider name stays the
  ref). No templating language, no `{{secret:…}}` interpolation — YAGNI.

Reject-list (normalized: lowercase, strip `_`/`-`): exact match on
`apikey, secret, password, passwd, token, credential, credentials,
authorization, bearer, accesskey, privatekey, secretkey, clientsecret` OR
suffix match on `apikey, secret, password, token, privatekey`.
Applies to `params` values that are non-None and non-empty-string.

## 6. Failure semantics

- Secret-shaped param at load/admission → `ValueError` → CLI validate fails /
  admission 400 (`RunAdmissionError`); **no Run row created** (I19).
- Missing env at client construction → `ValueError("OPENAI_API_KEY not set in
  environment")` naming the variable, never a value; raised inside step run →
  engine containment → step FAILED → run terminal FAILED (I11/I12 of the
  invariants doc).
- Ollama keeps default `"ollama"` bearer (non-secret, local server).

## 7. Compatibility matrix

| Surface | Before | After |
|---------|--------|-------|
| CLI `autopipe run/validate` | loader validates | + secret-param rejection at same choke |
| Library `Pipeline(config).run()` | no check | + `PipelineConfig` validator (model-level) |
| YAML load | same | same |
| Dashboard admission | wraps loader | inherits rejection; 400, persists nothing |
| Executor / env credentials | env only | unchanged |
| Shipped examples/seeds | no secret params (rg audit) | unaffected |
| Existing user configs with inline keys | persisted silently | **rejected at load — intentional breaking change** (they never worked through `LLMStep` anyway; `LLMStep` has no `api_key` param) |

## 8. Migration strategy

No DB migration (nothing schema-level changes in this design; Phase B already
dropped `users.api_key`). Config migration: reject-and-tell — the error
message names the step and param key so operators move the value to env.

## 9. Test strategy

1. **Deny-list units** (`tests/unit/core/test_loader.py`): flat key, nested
   key, case/underscore variants, suffix forms (`auth_token`), non-empty
   values rejected; empty/None values allowed; benign lookalikes
   (`max_tokens`, `tokenize`) allowed; error message contains key name, not
   value.
2. **Provenance sentinel** (backend): env carries `SENTINEL_KEY=sentinel…`;
   `build_provenance` output contains no `sentinel` substring.
3. **Persistence sentinel** (backend): full admit→Run-row→finalize flow with
   sentinel in env; assert `sentinel.encode()` absent from the SQLite file
   bytes (covers Run.config + provenance + events + metric rows in one grep).
4. **Admission witness**: secret-param config → `RunAdmissionError`, no Run.
5. Existing: `test_llm_client.py` (global mutation), `test_credentials`
   (env-only, message hygiene), `test_users_api_key_column_removed`.

NOT TESTED / ceilings: T-G value-shape smuggling; multi-tenant per-run
credentials (single-tenant server env by design); T8 rotation of live
constructed clients; prompt/response content logging by third-party SDKs.

## 10. Self-review (hard questions)

1. **Bypass via key name?** `authorization_header` normalizes to
   `authorizationheader` — exact list misses it; suffix list misses it.
   → residual T-G-class gap; acceptable? Partially: add `authorization` as
   *substring* only for `authorization`? Ponytail call: keep exact+suffix;
   document. A hostile config author is out of trust anyway (they can't get
   material in without the operator putting it in the config source).
   Rejected: substring matching breaks `max_tokens`/`tokenizer`.
2. **Could the deny check live in admission only?** No — library/YAML would
   bypass it. Model-level validator = every `PipelineConfig` path (I12-E).
3. **Does rejecting (vs scrubbing) break valid pipelines?** rg audit: zero
   shipped configs use deny-listed param names. Breaking only the unsafe.
4. **Explicit `api_key=` still legal — doesn't that violate I12-A?** No:
   explicit args exist in-process (tests, library) and cannot reach durable
   state; the serialization boundary is the invariant, not the constructor.
5. **Does provenance sentinel cover WS?** WS payloads derive from Run rows +
   step logs; sentinel DB grep + no-emission-site audit cover the union; a
   live WS capture harness is not warranted (ceiling).
6. **Depth limit 10 — DoS?** Attacker sends 10⁴-deep params: walk stops at
   10 and *rejects* (fail-closed), constant work per branch up to depth,
   bounded by config body size limit already enforced by the API.
7. **Rotation ceiling (T8)**: `LLMStep` caches `self.client` per step
   instance → per run. Rotation applies next run. Documented, not fixed —
   per-run re-resolution is enough at current scale.
8. **Why not remove `AutoPipeGlobalConfig` entirely?** Out of I12 scope
   beyond the `api_key` slot (dead-schema cleanup is a separate debt item);
   removing the slot removes the credential footgun, which is the I12 risk.
9. **Ollama `"ollama"` default** — is a constant non-secret "key"
   acceptable? Yes: local server, value is public documentation convention;
   treating it as material would fail closed every local setup for no gain.
10. **I12-H status PARTIAL — is that honest?** Yes: no emission site exists,
    but no test *forces* a log-capture assertion on the LLM path; the
    sentinel DB test covers persistence, not stdout. Listed as remaining gap.

## 11. Remaining risks (post-implementation)

- I12-H log-capture witness absent (PARTIAL by design of this phase).
- T-G value-shape smuggling (accepted, §10.1).
- Third-party SDK may log request metadata to their own logs — outside our
  boundary; instance-scoping limits blast radius within our process.
- `AutoPipeGlobalConfig` dead-schema debt (no `api_key` slot anymore).
