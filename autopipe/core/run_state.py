"""Canonical execution-lifecycle state machine.

Single source of truth for *what states an execution can be in* and *which
transitions between them are legal*. Every layer that records or derives
execution state — the core engine, the CLI, the dashboard executor, and any
future worker — imports its states and transitions from here.

Why this module exists
----------------------
Before it, the lifecycle was implicit: the dashboard worker assigned
``RunStatus`` directly on ORM objects, the startup sweep rewrote rows, and
nothing rejected illegal moves. Two consequences were observable:

* a terminal run could silently regress because nothing said "no",
* "did this run ever finish?" had to be answered by reading several code paths.

Invariants established here
---------------------------
* **I5** Run state has one authoritative mutation path: :func:`ensure_transition`.
* **I6** Terminal Run states cannot silently regress.
* **I12** Every Run reaches a terminal state (:attr:`RunState.is_terminal`).

The only sanctioned way to move *out of* a terminal state is an explicit
recovery/administrative override, requested via ``allow_recovery=True`` so that
every such call site is greppable in review.
"""

from __future__ import annotations

import enum
from typing import Dict, FrozenSet, Mapping, Optional, cast

from autopipe.exceptions import StateTransitionError


class RunState(str, enum.Enum):
    """Lifecycle states of a pipeline Run.

    String values are the wire/DB representation and are intentionally identical
    to the dashboard's pre-existing ``RunStatus`` values, so this module can be
    adopted without a schema or data migration.
    """

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        """True when no further execution may occur in this state."""
        return self in TERMINAL_RUN_STATES

    @classmethod
    def values(cls) -> FrozenSet[str]:
        """All legal wire values."""
        return frozenset(member.value for member in cls)


class StepState(str, enum.Enum):
    """Lifecycle states of a single Step within a Run.

    There is deliberately no ``CANCELLED`` step state: when a run is cancelled,
    not-yet-started steps are ``SKIPPED``. That is the canonical semantic and it
    is asserted by the contract tests.
    """

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"

    @property
    def is_terminal(self) -> bool:
        """True when the step will not transition again."""
        return self in TERMINAL_STEP_STATES

    @classmethod
    def values(cls) -> FrozenSet[str]:
        """All legal wire values."""
        return frozenset(member.value for member in cls)


#: Run states from which execution has finished for good.
TERMINAL_RUN_STATES: FrozenSet[RunState] = frozenset(
    {RunState.SUCCESS, RunState.FAILED, RunState.CANCELLED}
)

#: Step states from which a step will not transition again.
TERMINAL_STEP_STATES: FrozenSet[StepState] = frozenset(
    {StepState.SUCCESS, StepState.FAILED, StepState.SKIPPED}
)

#: Legal Run transitions. Terminal states map to the empty set: a terminal run
#: can only be moved by an explicit recovery override.
RUN_TRANSITIONS: Dict[RunState, FrozenSet[RunState]] = {
    RunState.PENDING: frozenset({RunState.RUNNING, RunState.FAILED, RunState.CANCELLED}),
    RunState.RUNNING: frozenset({RunState.SUCCESS, RunState.FAILED, RunState.CANCELLED}),
    RunState.SUCCESS: frozenset(),
    RunState.FAILED: frozenset(),
    RunState.CANCELLED: frozenset(),
}

#: Legal Step transitions.
#:
#: ``PENDING -> FAILED`` and ``PENDING -> SKIPPED`` are legal because a step can
#: be finalized without its "started" write having landed (crash recovery, or a
#: failure inside the lifecycle bookkeeping itself). ``RUNNING -> SKIPPED`` is
#: legal for the same reason: an interrupted step must always be finalizable.
STEP_TRANSITIONS: Dict[StepState, FrozenSet[StepState]] = {
    StepState.PENDING: frozenset({StepState.RUNNING, StepState.SKIPPED, StepState.FAILED}),
    StepState.RUNNING: frozenset({StepState.SUCCESS, StepState.FAILED, StepState.SKIPPED}),
    StepState.SUCCESS: frozenset(),
    StepState.FAILED: frozenset(),
    StepState.SKIPPED: frozenset(),
}

_Subject = str


def _coerce(value: object, enum_type: type[enum.Enum]) -> Optional[enum.Enum]:
    """Coerce a wire value, member name, or member into ``enum_type``, else None.

    Accepts the wire value (``"running"``), the member name (``"RUNNING"``), or an
    existing member. Anything else yields ``None`` so callers can raise a single
    consistent error type.
    """
    if value is None:
        return None
    if isinstance(value, enum_type):
        return value
    text = str(value)
    for member in enum_type:
        if member.value == text.lower() or member.name == text.upper():
            return member
    return None


def ensure_transition(
    current: object,
    new: object,
    *,
    allow_recovery: bool = False,
    subject: _Subject = "run",
    context: str | None = None,
) -> RunState | StepState:
    """Validate a lifecycle transition and return the coerced new state.

    This is **the** single mutation gate for execution state (invariant I5).

    Args:
        current: Current state. ``None`` means "no recorded prior state" and is
            always accepted (the first write of a record).
        new: The desired next state.
        allow_recovery: Explicitly permit leaving a terminal state. Reserved for
            documented recovery/administrative paths.
        subject: ``"run"`` or ``"step"`` — selects the transition table.
        context: Optional human-readable context (run id, step name) for errors
            and logs.

    Returns:
        The coerced new state member.

    Raises:
        StateTransitionError: if either state is unrecognised, or the move is
            not permitted by the transition table.
    """
    enum_type: type[enum.Enum]
    transitions: Mapping[enum.Enum, FrozenSet[enum.Enum]]
    if subject == "run":
        enum_type = RunState
        transitions = cast(Mapping[enum.Enum, FrozenSet[enum.Enum]], RUN_TRANSITIONS)
    else:
        enum_type = StepState
        transitions = cast(Mapping[enum.Enum, FrozenSet[enum.Enum]], STEP_TRANSITIONS)

    coerced_new = _coerce(new, enum_type)
    if coerced_new is None:
        raise StateTransitionError(
            f"Unknown {subject} state {new!r}",
            details={"state": str(new), "subject": subject, "context": context},
        )

    if current is None:
        # No recorded prior state: the first write of a record is always allowed.
        return cast(RunState | StepState, coerced_new)

    coerced_current = _coerce(current, enum_type)
    if coerced_current is None:
        # A *recorded* value we cannot interpret is corruption, not "no state".
        raise StateTransitionError(
            f"Unknown current {subject} state {current!r}",
            details={"state": str(current), "subject": subject, "context": context},
        )

    if coerced_current == coerced_new:
        # Idempotent re-assertion. Important in practice: the dashboard
        # re-broadcasts RUNNING while concurrent writers race, and a recovery
        # sweep may re-write a state that is already correct.
        return cast(RunState | StepState, coerced_new)

    allowed = transitions[coerced_current]
    if coerced_new in allowed:
        return cast(RunState | StepState, coerced_new)

    # Only terminal states have an empty `allowed` set, so scoping the recovery
    # override to that case keeps it precise: it bypasses terminality and
    # nothing else.
    if allow_recovery and not allowed:
        return cast(RunState | StepState, coerced_new)

    suffix = f" ({context})" if context else ""
    if not allowed:
        raise StateTransitionError(
            f"Illegal {subject} transition {coerced_current.value} -> "
            f"{coerced_new.value}: state is terminal{suffix}",
            details={
                "subject": subject,
                "current": coerced_current.value,
                "new": coerced_new.value,
                "terminal": True,
                "context": context,
            },
        )

    raise StateTransitionError(
        f"Illegal {subject} transition {coerced_current.value} -> {coerced_new.value}{suffix}",
        details={
            "subject": subject,
            "current": coerced_current.value,
            "new": coerced_new.value,
            "allowed": sorted(state.value for state in allowed),
            "context": context,
        },
    )


__all__ = [
    "RUN_TRANSITIONS",
    "STEP_TRANSITIONS",
    "TERMINAL_RUN_STATES",
    "TERMINAL_STEP_STATES",
    "RunState",
    "StepState",
    "ensure_transition",
]
