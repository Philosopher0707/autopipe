"""Run-path file production recorder (Phase B artifact registration).

Producers (ChartGenerator, step visualize/save sites) call
``record_produced_file(path)`` from the worker thread running the pipeline.
The dashboard runner drains the list after execution and registers
Artifact rows — the engine itself never touches this (execution-only
boundary) and core never imports the dashboard.
"""

import contextvars
from typing import List, Optional

_produced: contextvars.ContextVar[Optional[List[str]]] = contextvars.ContextVar(
    "produced_files", default=None
)


def record_produced_file(path: str) -> None:
    """Append a file this producer just wrote to the current thread's list."""
    lst = _produced.get()
    if lst is None:
        lst = []
        _produced.set(lst)
    lst.append(str(path))


def drain_produced_files() -> List[str]:
    """Return and clear the current thread's produced-file list."""
    lst = _produced.get()
    _produced.set(None)
    return list(lst) if lst else []
