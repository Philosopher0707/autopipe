# WebSocket Contract

Status: VERIFIED by `backend/tests/test_websocket_contract.py` and
`frontend/src/api/endpoints/__tests__/websocket.test.ts`.

## Envelope

Every message the backend sends is exactly:

```json
{"type": "<event>", "data": { ... }, "timestamp": "<ISO-8601>"}
```

- All payload fields live inside `data`. No payload keys at top level.
- Clients dispatch on `type` only.
- Routing across channels (`run:{id}`, `dashboard`) is server-side; the
  message body is identical on every channel that receives it.

## Channels

| Channel     | Clients                      | Events |
|-------------|------------------------------|--------|
| `run:{id}`  | RunDetail page (per-run WS)  | `run.status`, `run.log`, `run.metric` |
| `dashboard` | Dashboard WS (when connected)| `run.status`, `drift.alert`, `model.promoted`, `dashboard.*` |

Authentication: `?token=<access JWT>` query parameter; close code `1008`
on failure (parity with REST: token must decode AND belong to an active
DB user — see `authenticate_websocket`).

## Event types

| `type`            | `data` fields |
|-------------------|---------------|
| `run.status`      | `run_id`, `status`, plus optional summary fields (e.g. `metrics`) |
| `run.log`         | `run_id`, `step_id`, `level`, `message` |
| `run.metric`      | `run_id`, `step_id`, `metric_name`, `value`, `step_number` |
| `drift.alert`     | `alert_id`, `feature_name`, `severity`, `message` |
| `model.promoted`  | `model_id`, `version`, `from_stage`, `to_stage` |
| `dashboard.*`     | arbitrary payload (producer-defined) |

Producers: `app/api/v1/endpoints/websocket.py::broadcast_*` (the only
writers). The frontend's `WSEventType` union must stay in lockstep with
this table — add an event here first.

## Client rules

- `parseWSMessage` rejects malformed frames (no `type`, bad JSON, non-object)
  and defaults missing `data` to `{}` — handlers must never see `undefined.data`.
- Unknown `type` values are dispatched to zero handlers (no-op), not errors.
- Live `drift.alert` push is currently unwired on both ends; polling
  (`GET` drift endpoints) is the read path until a consumer subscribes.
