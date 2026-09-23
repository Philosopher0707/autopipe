"""Canonical execution engine.

**This module is the one execution semantic.** The CLI, the library API, the
dashboard worker and any future distributed worker all delegate here; none of
them may re-implement dependency resolution, input binding, output propagation,
step lifecycle, cancellation, or terminal-state selection.

Why this module exists
----------------------
The repository previously contained two execution loops: ``Pipeline.run`` in the
core, and a hand-written loop in the dashboard executor
(``app/executor/runner.py``). They disagreed on named input bindings — the
dashboard loop dropped them and passed ``{step_name: value}`` where the core
passed ``{param: value}`` — and the dashboard loop never assigned
``step.output``. The same YAML pipeline therefore meant two different things
depending on how it was launched. That class of divergence is what this module
makes structurally impossible.

Design boundary
---------------
* The engine performs **execution only**. It never touches a database.
* Everything the outside world needs to observe is published as an
  :class:`ExecutionEvent` to an :class:`EventSink`.
* The engine always returns an :class:`ExecutionResult` with a terminal state;
  it never lets an exception escape and never leaves the caller guessing.
* Callers that want exception semantics (``Pipeline.run``) re-raise
  :attr:`ExecutionResult.exception` themselves. Callers that want persistence
  (the dashboard) subscribe a sink. The engine is neutral between them.

Invariants established here
---------------------------
* **I1** Every execution path uses this engine.
* **I2** Input binding semantics are identical everywhere.
* **I3** Step output semantics are identical everywhere.
* **I4** Execution lifecycle has one authoritative owner (this engine).
* **I11** No worker exception can strand a Run (the engine never propagates).
* **I12** Every execution reaches a terminal state.
* **I13** Cancellation is observable (terminal state + event).
"""

from __future__ import annotations

import enum
import logging
import random
import threading
import time
import traceback
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    runtime_checkable,
)

import numpy as np

from autopipe.core.run_state import RunState, StepState
from autopipe.exceptions import AutoPipeError

logger = logging.getLogger(__name__)

#: Version of the execution semantic. Bump when the meaning of an execution
#: result changes; recorded in provenance so a result can be attributed to the
#: engine that produced it.
ENGINE_VERSION = "1.0"


class ExecutionError(AutoPipeError):
    """Base class for execution-time failures raised by the engine."""


class CancellationError(ExecutionError):
    """Raised internally when a cancellation token has been triggered.

    Carries a terminal :class:`RunState` of ``CANCELLED`` rather than ``FAILED``,
    so callers can distinguish "the user stopped this" from "this broke".
    """


class InputBindingError(ExecutionError):
    """Raised when a step's declared inputs cannot be resolved.

    Subclasses :class:`~autopipe.exceptions.AutoPipeError`, which is what the
    previous inline implementation raised, so existing ``except AutoPipeError``
    handlers keep working.
    """


class PipelineLoadError(ExecutionError):
    """Raised when a pipeline configuration cannot be turned into executable steps."""


@dataclass
class RunRng:
    """Run-local RNG streams bound onto steps by the engine.

    Replaces process-global seeding: worker runs execute on threads in one
    process, so ``random.seed()`` / ``np.random.seed()`` at run start would
    cross-contaminate concurrent runs. Steps read ``self.run_rng`` (declared on
    :class:`~autopipe.core.step.Step`); when the run declared no seed the
    engine binds ``None`` and the step falls back to its own default.
    """

    seed: int
    py: random.Random
    np: np.random.Generator

    @classmethod
    def from_seed(cls, seed: int) -> RunRng:
        """Create both streams from one integer seed."""
        return cls(seed=seed, py=random.Random(seed), np=np.random.default_rng(seed))


class CancellationToken:
    """Cooperative, thread-safe cancellation signal.

    The engine checks this at every step boundary, which is the guaranteed
    cancellation granularity. A long-running step may additionally poll
    ``self.cancellation_token`` (set by the engine before invocation) to abort
    mid-step; that is an optimisation, not the contract.
    """

    __slots__ = ("_event",)

    def __init__(self, event: threading.Event | None = None) -> None:
        """Create a token, optionally backed by an existing ``threading.Event``.

        Accepting an external event lets a caller that already owns a
        cancellation signal (the dashboard's run registry) share it with the
        engine instead of polling two flags.
        """
        self._event = event if event is not None else threading.Event()

    def cancel(self) -> None:
        """Request cancellation. Idempotent and safe from any thread."""
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        """True once :meth:`cancel` has been called."""
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        """Raise :class:`CancellationError` if cancellation was requested."""
        if self._event.is_set():
            raise CancellationError("Execution cancelled")


class EventKind(str, enum.Enum):
    """Kinds of execution event published by the engine."""

    RUN_STARTED = "run.started"
    RUN_FINISHED = "run.finished"
    STEP_STARTED = "step.started"
    STEP_FINISHED = "step.finished"
    STEP_SKIPPED = "step.skipped"
    VISUALIZATION_FAILED = "step.visualization_failed"


@dataclass(frozen=True)
class ExecutionEvent:
    """An immutable, ordered observation about an execution.

    ``sequence`` is monotonic per run and is the ordering authority — consumers
    must not rely on wall-clock timestamps to order events.
    """

    kind: EventKind
    run_id: str
    sequence: int
    timestamp: float
    step_name: Optional[str] = None
    state: Optional[str] = None
    data: Mapping[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    error_type: Optional[str] = None


@runtime_checkable
class EventSink(Protocol):
    """A destination for :class:`ExecutionEvent`s."""

    def emit(self, event: ExecutionEvent) -> None:
        """Publish one event."""
        ...


class NullEventSink:
    """Discards every event. The default, so the engine needs no wiring."""

    def emit(self, event: ExecutionEvent) -> None:
        """Discard the event."""


class CallbackEventSink:
    """Adapts a plain callable to the :class:`EventSink` protocol."""

    __slots__ = ("_callback",)

    def __init__(self, callback: Callable[[ExecutionEvent], None]) -> None:
        self._callback = callback

    def emit(self, event: ExecutionEvent) -> None:
        """Forward the event to the wrapped callback."""
        self._callback(event)


class CompositeEventSink:
    """Fans an event out to several sinks.

    A failing child never prevents the remaining children from receiving the
    event: one broken observer must not blind the others. The failure is raised
    only if *every* child failed, so the engine's error accounting can record
    "observability is broken" rather than hiding it.
    """

    __slots__ = ("_sinks",)

    def __init__(self, sinks: Sequence[EventSink]) -> None:
        self._sinks = list(sinks)

    def emit(self, event: ExecutionEvent) -> None:
        """Fan the event out; raise only if all sinks failed."""
        failures: List[BaseException] = []
        for sink in self._sinks:
            try:
                sink.emit(event)
            except BaseException as exc:
                failures.append(exc)
        if failures and len(failures) == len(self._sinks):
            raise failures[0]


class RecordingEventSink:
    """Collects events in memory. Used by contract tests and diagnostics."""

    __slots__ = ("events",)

    def __init__(self) -> None:
        self.events: List[ExecutionEvent] = []

    def emit(self, event: ExecutionEvent) -> None:
        """Append the event to :attr:`events`."""
        self.events.append(event)

    def of_kind(self, kind: EventKind) -> List[ExecutionEvent]:
        """Return only the events of a given kind, in order."""
        return [event for event in self.events if event.kind is kind]


@dataclass
class StepOutcome:
    """The record of one step's execution."""

    name: str
    state: str
    output: Any = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    error_type: Optional[str] = None
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    duration_seconds: Optional[float] = None
    traceback: Optional[str] = None

    @property
    def ok(self) -> bool:
        """True when the step completed successfully."""
        return self.state == StepState.SUCCESS.value

    def to_dict(self) -> Dict[str, Any]:
        """Serialise without the (potentially huge) output payload."""
        return {
            "name": self.name,
            "state": self.state,
            "metrics": dict(self.metrics),
            "error": self.error,
            "error_type": self.error_type,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class ExecutionResult:
    """The terminal, complete outcome of one execution.

    Always produced — the engine converts any escaping exception into a
    ``FAILED`` result, so callers never have to handle "the engine blew up".
    """

    run_id: str
    pipeline_name: str
    state: RunState
    outputs: Dict[str, Any] = field(default_factory=dict)
    steps: List[StepOutcome] = field(default_factory=list)
    started_at: float = 0.0
    finished_at: float = 0.0
    duration_seconds: float = 0.0
    metrics: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    error_type: Optional[str] = None
    traceback: Optional[str] = None
    exception: Optional[BaseException] = field(default=None, repr=False)
    sink_errors: List[str] = field(default_factory=list)
    engine_version: str = ENGINE_VERSION
    #: The seed the engine actually initialized run-local RNG from, or None
    #: when the run declared none (or never reached the engine). Distinct from
    #: the config's *declared* seed, which provenance records at Run creation.
    seed_applied: Optional[int] = None

    @property
    def ok(self) -> bool:
        """True when the run completed successfully."""
        return self.state is RunState.SUCCESS

    @property
    def is_terminal(self) -> bool:
        """True for SUCCESS/FAILED/CANCELLED."""
        return self.state.is_terminal

    def step(self, name: str) -> Optional[StepOutcome]:
        """Return the outcome for a named step, if it ran."""
        for outcome in self.steps:
            if outcome.name == name:
                return outcome
        return None

    @property
    def failed_step(self) -> Optional[StepOutcome]:
        """The first step that failed, if any."""
        for outcome in self.steps:
            if outcome.state == StepState.FAILED.value:
                return outcome
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Serialise the result, excluding non-JSON-safe payloads."""
        return {
            "run_id": self.run_id,
            "pipeline_name": self.pipeline_name,
            "state": self.state.value,
            "steps": [outcome.to_dict() for outcome in self.steps],
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_seconds": self.duration_seconds,
            "metrics": dict(self.metrics),
            "error": self.error,
            "error_type": self.error_type,
            "sink_errors": list(self.sink_errors),
            "engine_version": self.engine_version,
        }


@dataclass
class ExecutionContext:
    """Explicit, injected execution dependencies.

    Replaces hidden module-level globals. Everything the engine needs to know
    about *where* it is running arrives through this object, so a caller or test
    can build a context without monkeypatching module state.
    """

    run_id: str
    pipeline_name: str
    initial_inputs: Optional[Dict[str, Any]] = None
    #: Declared run seed; when present and a plain non-negative int, the
    #: engine creates one :class:`RunRng` and binds it to every step.
    seed: Optional[int] = None
    cancellation: CancellationToken = field(default_factory=CancellationToken)
    sink: EventSink = field(default_factory=NullEventSink)
    #: Free-form execution metadata (provenance, request origin, ...).
    metadata: Dict[str, Any] = field(default_factory=dict)
    #: Capture formatted tracebacks for failures. Off for hot paths/tests.
    capture_traceback: bool = True
    #: Invoke ``Step.visualize`` after each step (non-fatal on failure).
    visualize: bool = True


def resolve_step_inputs(
    step: Any,
    outputs: Mapping[str, Any],
    initial_inputs: Optional[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Resolve the kwargs a step's ``run()`` will receive.

    **The canonical binding semantic (invariant I2).** Precedence:

    1. **Named bindings win.** When ``step.input_bindings`` is non-empty, each
       ``run()`` parameter receives exactly the output of the step it names.
       Every referenced step must have produced an output.
    2. **Positional ``depends_on``.** Otherwise every dependency that has an
       output contributes ``{dependency_name: output}``.
    3. **Initial inputs.** Otherwise the pipeline's ``initial_inputs`` pass
       through verbatim.

    Args:
        step: The step to bind inputs for.
        outputs: Outputs produced so far, keyed by step name.
        initial_inputs: The pipeline's initial inputs, if any.

    Returns:
        The kwargs mapping for ``step.run(**kwargs)``.

    Raises:
        InputBindingError: if a named binding references a step with no output.
    """
    bindings = getattr(step, "input_bindings", None)
    if bindings:
        missing = sorted({source for source in bindings.values() if source not in outputs})
        if missing:
            raise InputBindingError(
                f"Step '{getattr(step, 'name', '?')}' binds inputs to "
                f"unexecuted/unknown steps: {missing}"
            )
        return {param: outputs[source] for param, source in bindings.items()}

    depends_on = getattr(step, "depends_on", None) or []
    if depends_on:
        return {dep: outputs[dep] for dep in depends_on if dep in outputs}

    return dict(initial_inputs or {})


@dataclass
class _Progress:
    """Mutable per-run progress, threaded explicitly through the engine loop.

    Exists so the loop helpers can mutate run progress without reaching into
    closure variables, which keeps each helper independently testable.
    """

    outputs: Dict[str, Any]
    run_failed: bool = False
    captured: Optional[BaseException] = None


class _EventBus:
    """Sequences and publishes events for one run.

    Owns the per-run monotonic sequence counter and isolates observer failures so
    a broken sink can never abort execution — but the failure is *recorded*
    (:attr:`failures`) rather than swallowed, per the no-silent-failures rule.
    """

    __slots__ = ("_run_id", "_sequence", "_sink", "failures")

    def __init__(self, run_id: str, sink: EventSink) -> None:
        self._run_id = run_id
        self._sequence = 0
        self._sink = sink
        self.failures: List[str] = []

    @property
    def sequence(self) -> int:
        """Number of events emitted so far."""
        return self._sequence

    def emit(
        self,
        kind: EventKind,
        *,
        step_name: Optional[str] = None,
        state: Optional[str] = None,
        data: Optional[Mapping[str, Any]] = None,
        error: Optional[str] = None,
        error_type: Optional[str] = None,
    ) -> None:
        """Publish one event. Never raises."""
        event = ExecutionEvent(
            kind=kind,
            run_id=self._run_id,
            sequence=self._sequence,
            timestamp=time.time(),
            step_name=step_name,
            state=state,
            data=dict(data or {}),
            error=error,
            error_type=error_type,
        )
        self._sequence += 1
        try:
            self._sink.emit(event)
        except BaseException as exc:
            label = f"{kind.value}: {type(exc).__name__}: {exc}"
            self.failures.append(label)
            logger.warning("Event sink failed (%s) for run %s", label, self._run_id)


class ExecutionEngine:
    """The one execution semantic.

    Stateless and reusable: all per-run state lives in the supplied
    :class:`ExecutionContext` and in the returned :class:`ExecutionResult`, so a
    single engine instance safely serves concurrent runs (the dashboard shares
    one). There is no module-level mutable state here by design.
    """

    def __init__(self, *, engine_version: str = ENGINE_VERSION) -> None:
        self.engine_version = engine_version

    def execute(self, pipeline: Any, context: ExecutionContext) -> ExecutionResult:
        """Execute ``pipeline`` under ``context``; always return a terminal result.

        This method never raises. Any failure — including a bug in the engine
        itself — becomes a ``FAILED`` :class:`ExecutionResult`, because the
        alternative (an exception escaping into a daemon thread) is precisely the
        failure mode that used to strand runs (invariant I11).

        Args:
            pipeline: A :class:`~autopipe.core.pipeline.Pipeline`, or any object
                exposing ``name``, ``steps`` and ``execution_order``.
            context: The injected execution dependencies.

        Returns:
            An :class:`ExecutionResult` whose ``state`` is terminal.
        """
        started_at = time.time()
        result = ExecutionResult(
            run_id=context.run_id,
            pipeline_name=str(getattr(pipeline, "name", context.pipeline_name)),
            state=RunState.PENDING,
            started_at=started_at,
            engine_version=self.engine_version,
        )
        bus = _EventBus(run_id=context.run_id, sink=context.sink)

        progress = _Progress(outputs=dict(context.initial_inputs or {}))
        result.outputs = progress.outputs

        try:
            # Seed application happens before plan resolution: an engine that
            # ran with a declared seed has applied it even if the plan or a
            # step later fails. Defensive type check mirrors the schema's
            # plain-int rule (no bool, no coercion).
            if type(context.seed) is int and context.seed >= 0:
                run_rng: Optional[RunRng] = RunRng.from_seed(context.seed)
                result.seed_applied = context.seed
            else:
                run_rng = None
            execution_order = self._resolve_order(pipeline, result, progress, bus, context)
            if execution_order is not None:
                for step in pipeline.steps.values():
                    self._bind_cancellation(step, context.cancellation)
                    self._bind_rng(step, run_rng)
                self._run_steps(pipeline, execution_order, progress, context, result, bus)
        except BaseException as exc:
            progress.captured = exc
            if result.error is None:
                result.error = f"{type(exc).__name__}: {exc}"
                result.error_type = type(exc).__name__
                result.traceback = self._format_traceback(context)

        try:
            result.exception = progress.captured
            result.outputs = progress.outputs
            result.sink_errors = bus.failures
            result.metrics = self._aggregate_metrics(result)
            result.finished_at = time.time()
            result.duration_seconds = result.finished_at - result.started_at

            # Terminal selection. A failure outranks a cancellation: a run that
            # already broke must not be able to report itself as merely
            # "stopped", because that would mask a real defect (no-silent-failures).
            if progress.run_failed:
                result.state = RunState.FAILED
            elif context.cancellation.is_cancelled:
                result.state = RunState.CANCELLED
            else:
                result.state = RunState.SUCCESS

            bus.emit(
                EventKind.RUN_FINISHED,
                state=result.state.value,
                data={"duration_seconds": result.duration_seconds, "metrics": result.metrics},
                error=result.error,
                error_type=result.error_type,
            )
        except BaseException as exc:
            # Post-processing bug (metrics aggregation, terminal selection):
            # execute() still never raises — degrade to a FAILED terminal result.
            if result.error is None:
                result.error = f"{type(exc).__name__}: {exc}"
                result.error_type = type(exc).__name__
            result.exception = result.exception or exc
            result.state = RunState.FAILED
            result.finished_at = result.finished_at or time.time()
            result.duration_seconds = result.finished_at - result.started_at
            bus.emit(
                EventKind.RUN_FINISHED,
                state=result.state.value,
                data={"duration_seconds": result.duration_seconds},
                error=result.error,
                error_type=result.error_type,
            )
        return result

    # -- internal -----------------------------------------------------------

    def _format_traceback(self, context: ExecutionContext) -> Optional[str]:
        """Return a formatted traceback, or None when capture is disabled."""
        return traceback.format_exc() if context.capture_traceback else None

    def _bind_cancellation(self, step: Any, token: CancellationToken) -> None:
        """Expose the cancellation token to a step for optional in-step polling.

        Deliberately *not* injected through ``run(**kwargs)``: steps consume
        kwargs as a duck-typed data bag, so adding a control object there would
        corrupt input semantics. The attribute is declared on ``Step``.
        """
        try:
            step.cancellation_token = token
        except AttributeError:  # pragma: no cover - slots-based stand-ins
            logger.debug("Step %r does not accept a cancellation token", step)

    def _bind_rng(self, step: Any, run_rng: Optional[RunRng]) -> None:
        """Expose the run-local RNG to a step for seed-scoped randomness.

        Always writes, including ``None`` for unseeded runs, so a step reused
        across a seeded and an unseeded run cannot keep a stale stream.
        """
        try:
            step.run_rng = run_rng
        except AttributeError:  # pragma: no cover - slots-based stand-ins
            logger.debug("Step %r does not accept a run RNG", step)

    def _resolve_order(
        self,
        pipeline: Any,
        result: ExecutionResult,
        progress: _Progress,
        bus: _EventBus,
        context: ExecutionContext,
    ) -> Optional[List[str]]:
        """Resolve execution order and announce the plan.

        Returns ``None`` — after recording the failure on ``progress`` and
        emitting ``RUN_STARTED`` with ``plan_resolved: False`` — when the
        dependency graph is invalid. A sentinel is used rather than an exception
        so the failure stays on the ordinary result path.
        """
        try:
            order = list(pipeline.execution_order)
        except Exception as exc:
            result.error = f"{type(exc).__name__}: {exc}"
            result.error_type = type(exc).__name__
            result.traceback = self._format_traceback(context)
            progress.run_failed = True
            progress.captured = exc
            bus.emit(
                EventKind.RUN_STARTED,
                state=RunState.RUNNING.value,
                data={"execution_order": [], "plan_resolved": False},
                error=result.error,
                error_type=result.error_type,
            )
            return None

        bus.emit(
            EventKind.RUN_STARTED,
            state=RunState.RUNNING.value,
            data={
                "execution_order": order,
                "step_types": {name: type(pipeline.steps[name]).__name__ for name in order},
                "plan_resolved": True,
            },
        )
        return order

    def _run_steps(
        self,
        pipeline: Any,
        execution_order: List[str],
        progress: _Progress,
        context: ExecutionContext,
        result: ExecutionResult,
        bus: _EventBus,
    ) -> None:
        """Execute every step in order, recording outcomes as we go."""
        for step_name in execution_order:
            if progress.run_failed:
                result.steps.append(self._skip(step_name, "upstream_failure", bus))
                continue
            if context.cancellation.is_cancelled:
                result.steps.append(self._skip(step_name, "cancelled", bus))
                continue

            step = pipeline.steps[step_name]
            try:
                inputs = resolve_step_inputs(step, progress.outputs, context.initial_inputs)
            except InputBindingError as exc:
                outcome = self._binding_failure(step_name, exc, context, bus)
                result.steps.append(outcome)
                progress.run_failed = True
                progress.captured = exc
                result.error = outcome.error
                result.error_type = outcome.error_type
                result.traceback = outcome.traceback
                continue

            outcome, exception = self._run_step(step, inputs, context, bus)
            result.steps.append(outcome)
            if outcome.ok:
                progress.outputs[step_name] = outcome.output
            elif outcome.state == StepState.SKIPPED.value:
                # In-step cooperative cancellation: not a failure, just stopped.
                logger.info("Step %s stopped early by cancellation", step_name)
            else:
                progress.run_failed = True
                if progress.captured is None:
                    progress.captured = exception
                    # The run-level error names the step that broke: "which step
                    # failed" is the first thing an operator asks.
                    result.error = f"Step '{step_name}' failed: {outcome.error}"
                    result.error_type = outcome.error_type
                    result.traceback = outcome.traceback

    def _skip(self, step_name: str, reason: str, bus: _EventBus) -> StepOutcome:
        """Record a step that will not run, with the reason why."""
        outcome = StepOutcome(name=step_name, state=StepState.SKIPPED.value)
        bus.emit(
            EventKind.STEP_SKIPPED,
            step_name=step_name,
            state=StepState.SKIPPED.value,
            data={"reason": reason},
        )
        return outcome

    def _binding_failure(
        self, step_name: str, exc: Exception, context: ExecutionContext, bus: _EventBus
    ) -> StepOutcome:
        """Record a step whose declared inputs could not be resolved."""
        outcome = StepOutcome(
            name=step_name,
            state=StepState.FAILED.value,
            error=f"{type(exc).__name__}: {exc}",
            error_type=type(exc).__name__,
            traceback=self._format_traceback(context),
        )
        bus.emit(
            EventKind.STEP_FINISHED,
            step_name=step_name,
            state=outcome.state,
            error=outcome.error,
            error_type=outcome.error_type,
        )
        return outcome

    @staticmethod
    def _timed_outcome(
        *,
        step_name: str,
        state: str,
        started_at: float,
        output: Any = None,
        error: Optional[str] = None,
        error_type: Optional[str] = None,
        traceback_text: Optional[str] = None,
        metrics: Optional[Dict[str, Any]] = None,
    ) -> StepOutcome:
        """Build a :class:`StepOutcome` with timing filled in."""
        finished_at = time.time()
        return StepOutcome(
            name=step_name,
            state=state,
            output=output,
            metrics=dict(metrics or {}),
            error=error,
            error_type=error_type,
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=finished_at - started_at,
            traceback=traceback_text,
        )

    def _run_step(
        self,
        step: Any,
        inputs: Dict[str, Any],
        context: ExecutionContext,
        bus: _EventBus,
    ) -> tuple[StepOutcome, Optional[BaseException]]:
        """Invoke one step, converting any failure into a recorded outcome.

        Never raises. The exception, if any, is *returned* so the caller can both
        persist a FAILED state and — where the public API requires it — re-raise.
        """
        name = str(getattr(step, "name", "?"))
        started_at = time.time()
        bus.emit(EventKind.STEP_STARTED, step_name=name, state=StepState.RUNNING.value)
        logger.info("Running step %s", name)

        try:
            output = step.run(**inputs)
        except CancellationError:
            outcome = self._timed_outcome(
                step_name=name, state=StepState.SKIPPED.value, started_at=started_at
            )
            bus.emit(
                EventKind.STEP_SKIPPED,
                step_name=name,
                state=StepState.SKIPPED.value,
                data={"reason": "cancelled_in_step"},
            )
            return outcome, None
        except BaseException as exc:
            outcome = self._timed_outcome(
                step_name=name,
                state=StepState.FAILED.value,
                started_at=started_at,
                error=f"{type(exc).__name__}: {exc}",
                error_type=type(exc).__name__,
                traceback_text=self._format_traceback(context),
            )
            bus.emit(
                EventKind.STEP_FINISHED,
                step_name=name,
                state=StepState.FAILED.value,
                error=outcome.error,
                error_type=outcome.error_type,
            )
            return outcome, exc

        # Success path: every path assigns step.output (invariant I3).
        try:
            step.output = output
        except AttributeError:  # pragma: no cover - exotic stand-ins
            logger.debug("Step %r does not accept an output attribute", name)

        if context.visualize:
            self._visualize_step(step, inputs, name, bus)

        outcome = self._timed_outcome(
            step_name=name, state=StepState.SUCCESS.value, started_at=started_at, output=output
        )
        outcome.metrics = dict(getattr(step, "metrics", None) or {})
        bus.emit(
            EventKind.STEP_FINISHED,
            step_name=name,
            state=StepState.SUCCESS.value,
            data={"metrics": outcome.metrics, "duration_seconds": outcome.duration_seconds},
        )
        return outcome, None

    def _visualize_step(self, step: Any, inputs: Dict[str, Any], name: str, bus: _EventBus) -> None:
        """Run step visualization. Failure is non-fatal but never silent."""
        try:
            step.visualize(**inputs)
        except BaseException as exc:
            logger.warning("Visualization failed for step %s: %s", name, exc)
            bus.emit(
                EventKind.VISUALIZATION_FAILED,
                step_name=name,
                error=f"{type(exc).__name__}: {exc}",
                error_type=type(exc).__name__,
            )

    @staticmethod
    def _aggregate_metrics(result: ExecutionResult) -> Dict[str, Any]:
        """Fold step metrics into run metrics, namespacing by step.

        The namespacing rule is preserved from the previous dashboard
        implementation so existing metric keys do not change: ``{step}_{metric}``,
        unless the metric is already named after its step.
        """
        metrics: Dict[str, Any] = {}
        for outcome in result.steps:
            for key, value in outcome.metrics.items():
                metrics[f"{outcome.name}_{key}" if key != outcome.name else key] = value
        return metrics


__all__ = [
    "ENGINE_VERSION",
    "CallbackEventSink",
    "CancellationError",
    "CancellationToken",
    "CompositeEventSink",
    "EventKind",
    "EventSink",
    "ExecutionContext",
    "ExecutionEngine",
    "ExecutionError",
    "ExecutionEvent",
    "ExecutionResult",
    "InputBindingError",
    "NullEventSink",
    "PipelineLoadError",
    "RecordingEventSink",
    "RunRng",
    "StepOutcome",
    "resolve_step_inputs",
]
