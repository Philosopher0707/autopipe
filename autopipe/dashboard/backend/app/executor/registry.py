"""Thread-safe registry for active pipeline runs.

Tracks running pipeline executions so they can be cancelled externally.
"""

import threading

_active_runs: dict[str, threading.Event] = {}
_lock = threading.Lock()


def register_run(run_id: str) -> threading.Event:
    """Register a run as active. Returns a cancellation event."""
    cancel_event = threading.Event()
    with _lock:
        _active_runs[run_id] = cancel_event
    return cancel_event


def cancel_run(run_id: str) -> bool:
    """Signal a run for cancellation. Returns True if the run was found."""
    with _lock:
        event = _active_runs.get(run_id)
        if event is None:
            return False
        event.set()
    return True


def unregister_run(run_id: str) -> None:
    """Remove a run from the registry after completion or failure."""
    with _lock:
        _active_runs.pop(run_id, None)


def is_cancelled(run_id: str) -> bool:
    """Check if a run has been flagged for cancellation."""
    with _lock:
        event = _active_runs.get(run_id)
    return event is not None and event.is_set()


def get_active_run_ids() -> list[str]:
    """Return IDs of currently active runs."""
    with _lock:
        return list(_active_runs.keys())
