"""Run admission: the single gate deciding whether a config may become a Run.

Why this module exists
----------------------
A Run that is created but never dispatched can never reach a terminal state
(invariants I11/I12). Two endpoints each decided "is this runnable?" differently:

* ``POST /pipelines/{id}/runs`` created the Run unconditionally, then dispatched
  only when the config happened to contain a ``"steps"`` key. A config without
  that key produced a PENDING run that nothing would ever execute.
* ``POST /experiments/{id}/trials`` created and **committed** its runs, and only
  then returned ``501`` for ``simulate=true`` — so an error response left
  orphaned PENDING runs behind.

Both are the same defect: the creation decision and the execution decision were
two separate, inconsistent tests, and an error path could persist side effects.

This module owns the decision exactly once: if ``admit_run_config`` accepts a
config, the caller may create the Run **and must dispatch it**. If it rejects,
the caller creates nothing.
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class RunAdmissionError(Exception):
    """Raised when a configuration may not become a Run.

    Carries a caller-safe message: the API turns this into a 400, because the
    cause is always something the requester supplied.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def admit_run_config(config: Any) -> Dict[str, Any]:
    """Return a copy of ``config`` if it can become an executable Run.

    Admission means *loadable*, not *successful*: the configuration must build a
    pipeline through the canonical loader (schema, alias resolution, the
    step-type allowlist, constructor arity, dependency graph). Whether the steps
    then succeed is a runtime outcome and is not admission's concern.

    Args:
        config: The configuration a caller wants to run.

    Returns:
        A shallow copy of the config, safe to persist on the Run row.

    Raises:
        RunAdmissionError: if the config is missing, is not a mapping, or cannot
            be loaded.
    """
    if config is None:
        raise RunAdmissionError(
            "no pipeline configuration was supplied: store a config on the "
            "pipeline, or pass config_override"
        )
    if not isinstance(config, dict):
        raise RunAdmissionError(
            f"pipeline configuration must be an object, got {type(config).__name__}"
        )

    # Import here so that importing this module never triggers step-library
    # imports (and so tests can patch the loader if they need to).
    from autopipe.core.loader import load_executable_pipeline

    try:
        # Not the plain loader: admission must also resolve the execution plan,
        # because a dependency cycle is only detectable that way. An admitted
        # config is one that can actually run, so the plan is resolved here and
        # not later.
        load_executable_pipeline(config)
    except Exception as exc:
        raise RunAdmissionError(f"{type(exc).__name__}: {exc}") from exc

    return dict(config)


__all__ = ["RunAdmissionError", "admit_run_config"]
