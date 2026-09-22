"""Thread-safe registry for active pipeline runs.

Tracks running pipeline executions so they can be cancelled externally.
"""

import threading

_active_runs: dict[str, threading.Event] = {}
# Cancels that arrived before the executor thread registered the run. Without
# this, a PATCH /runs/{id} that lands between the API commit and register_run
# is lost: signal_cancel returns False, no event is ever set, and the thread
# runs the pipeline to completion against a row the API already wrote CANCELLED.
_pending_cancels: set[str] = set()
_lock = threading.Lock()


def register_run(run_id: str) -> threading.Event:
    """Register a run as active. Returns a cancellation event.

    If a cancel for this run arrived before registration, the returned event
    is already set.
    """
    cancel_event = threading.Event()
    with _lock:
        _active_runs[run_id] = cancel_event
        if run_id in _pending_cancels:
            _pending_cancels.discard(run_id)
            cancel_event.set()
    return cancel_event


def cancel_run(run_id: str) -> bool:
    """Signal a run for cancellation.

    Returns True when the run is currently registered and its event was set.
    A miss is still queued so ``register_run`` can apply it; the return value
    reports only whether the run was active *now*.
    """
    with _lock:
        event = _active_runs.get(run_id)
        if event is None:
            _pending_cancels.add(run_id)
            return False
        event.set()
    return True


def unregister_run(run_id: str) -> None:
    """Remove a run from the registry after completion or failure."""
    with _lock:
        _active_runs.pop(run_id, None)
        _pending_cancels.discard(run_id)


def is_cancelled(run_id: str) -> bool:
    """Check if a run has been flagged for cancellation."""
    with _lock:
        event = _active_runs.get(run_id)
    return event is not None and event.is_set()


def get_active_run_ids() -> list[str]:
    """Return IDs of currently active runs."""
    with _lock:
        return list(_active_runs.keys())
