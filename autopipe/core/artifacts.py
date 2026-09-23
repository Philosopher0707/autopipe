"""Run-path file production and dataset input recorders (Phases B/C).

Producers call these from the worker thread running the pipeline:

- ``record_produced_file(path)`` — a file this run wrote (artifact registration)
- ``record_dataset_input(entry)`` — a dataset this run consumed (input identity)

The dashboard runner drains both lists after execution and persists them —
the engine itself never touches this module (execution-only boundary) and
core never imports the dashboard.
"""

import contextvars
import hashlib
from typing import Any, Dict, List, Optional

_produced: contextvars.ContextVar[Optional[List[str]]] = contextvars.ContextVar(
    "produced_files", default=None
)
_datasets: contextvars.ContextVar[Optional[List[Dict[str, Any]]]] = contextvars.ContextVar(
    "dataset_inputs", default=None
)


def sha256_file(path: str) -> str:
    """SHA-256 of a file's raw bytes — the canonical content address.

    Deterministic by construction: exact byte sequence, no text decoding, no
    normalization, lowercase hex. Two paths with identical bytes hash the
    same; any byte difference (newline, encoding, metadata byte) changes the
    hash. Raises the underlying OSError (FileNotFoundError, IsADirectoryError,
    PermissionError) if the file cannot be read — callers fail closed instead
    of recording a hash they did not compute. Re-exported by
    ``app.db.models`` for the Artifact hook.
    """
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def record_dataset_input(entry: Dict[str, Any]) -> None:
    """Append a dataset this loader just consumed to the current thread's list."""
    lst = _datasets.get()
    if lst is None:
        lst = []
        _datasets.set(lst)
    lst.append(dict(entry))


def drain_dataset_inputs() -> List[Dict[str, Any]]:
    """Return and clear the current thread's dataset-input list."""
    lst = _datasets.get()
    _datasets.set(None)
    return [dict(e) for e in lst] if lst else []
