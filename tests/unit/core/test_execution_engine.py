"""Contract tests for the canonical execution engine.

Covers the behavioural invariants the engine exists to establish:

* **I1/I4** — one execution semantic, owned in one place.
* **I2** — input binding is identical for every caller.
* **I3** — ``step.output`` is assigned on every successful step.
* **I11/I12** — the engine never propagates an exception and always returns a
  terminal state.
* **I13** — cancellation is observable.
"""

from autopipe.core.execution import (
    CallbackEventSink,
    CancellationToken,
    ExecutionContext,
    ExecutionEngine,
    InputBindingError,
    NullEventSink,
    RecordingEventSink,
    resolve_step_inputs,
)
from autopipe.core.execution import EventKind as K
from autopipe.core.pipeline import Pipeline
from autopipe.core.run_state import RunState, StepState
from autopipe.core.step import Step


class RecordingStep(Step):
    """A step that records the kwargs it received and returns a scripted value."""

    def __init__(
        self,
        name: str,
        result: object = None,
        raises: BaseException | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(name, **kwargs)  # type: ignore[arg-type]
        self.calls: list[dict] = []
        self._result = name if result is None else result
        self._raises = raises

    def run(self, **kwargs: object) -> object:
        """Record the call, then raise or return as scripted."""
        self.calls.append(dict(kwargs))
        if self._raises is not None:
            raise self._raises
        return self._result


class CancellingStep(RecordingStep):
    """A step that cooperatively cancels mid-execution."""

    def run(self, **kwargs: object) -> object:
        """Request cancellation via the injected token, then cooperate with it."""
        self.calls.append(dict(kwargs))
        assert self.cancellation_token is not None, "engine must inject the token"
        self.cancellation_token.cancel()
        self.cancellation_token.raise_if_cancelled()
        return "unreachable"


def _run(pipeline: Pipeline, **ctx: object) -> tuple:
    """Execute and return ``(result, sink)`` with a recording sink attached."""
    sink = RecordingEventSink()
    context = ExecutionContext(
        run_id="run-test",
        pipeline_name=pipeline.name,
        sink=sink,
        **ctx,  # type: ignore[arg-type]
    )
    return ExecutionEngine().execute(pipeline, context), sink


class TestBindingSemantics:
    """Invariant I2 — one binding semantic, everywhere."""

    def test_named_bindings_are_keyed_by_parameter_name(self):
        pipeline = Pipeline("bind")
        src = RecordingStep("src", result="VALUE")
        sink = RecordingStep("sink", depends_on=["src"])
        sink.input_bindings = {"payload": "src"}
        pipeline.add_step(src)
        pipeline.add_step(sink)

        result, _ = _run(pipeline)

        assert result.ok
        assert sink.calls == [{"payload": "VALUE"}], "binding must use the param name"

    def test_legacy_depends_on_is_keyed_by_step_name(self):
        pipeline = Pipeline("legacy")
        src = RecordingStep("src", result="VALUE")
        sink = RecordingStep("sink", depends_on=["src"])
        pipeline.add_step(src)
        pipeline.add_step(sink)

        result, _ = _run(pipeline)

        assert result.ok
        assert sink.calls == [{"src": "VALUE"}], "legacy behaviour must be step-name keyed"

    def test_initial_inputs_reach_root_steps(self):
        pipeline = Pipeline("roots")
        first = RecordingStep("first")
        pipeline.add_step(first)

        result, _ = _run(pipeline, initial_inputs={"data": 42})

        assert result.ok
        assert first.calls == [{"data": 42}]
        assert result.outputs == {"data": 42, "first": "first"}

    def test_named_binding_beats_depends_on(self):
        pipeline = Pipeline("precedence")
        a = RecordingStep("a", result="A")
        b = RecordingStep("b", result="B", depends_on=["a"])
        consumer = RecordingStep("consumer", depends_on=["a", "b"])
        consumer.input_bindings = {"only": "b"}
        for step in (a, b, consumer):
            pipeline.add_step(step)

        result, _ = _run(pipeline)

        assert result.ok
        assert consumer.calls == [{"only": "B"}], "bindings must win over depends_on"

    def test_unresolvable_binding_fails_the_run_with_a_typed_error(self):
        pipeline = Pipeline("dangling")
        solo = RecordingStep("solo")
        solo.input_bindings = {"x": "does_not_exist"}
        pipeline.add_step(solo)

        result, _ = _run(pipeline)

        assert result.state is RunState.FAILED
        assert isinstance(result.exception, InputBindingError)
        assert "does_not_exist" in (result.error or "")
        assert result.step("solo").state == StepState.FAILED.value

    def test_resolve_step_inputs_is_the_single_implementation(self):
        step = RecordingStep("s")
        step.input_bindings = {"p": "up"}
        assert resolve_step_inputs(step, {"up": 1}, None) == {"p": 1}

        step.input_bindings = {}
        step.depends_on = ["up"]
        assert resolve_step_inputs(step, {"up": 1}, None) == {"up": 1}

        step.depends_on = []
        assert resolve_step_inputs(step, {}, {"i": 2}) == {"i": 2}


class TestLifecycle:
    """Terminal-state selection and step bookkeeping."""

    def test_empty_pipeline_succeeds_with_no_steps(self):
        result, _ = _run(Pipeline("empty"))

        assert result.state is RunState.SUCCESS
        assert result.outputs == {}
        assert result.steps == []
        assert result.is_terminal

    def test_success_assigns_step_output_attribute(self):
        pipeline = Pipeline("out")
        src = RecordingStep("src", result="PRODUCED")
        pipeline.add_step(src)

        result, _ = _run(pipeline)

        assert result.ok
        assert src.output == "PRODUCED", "invariant I3: step.output always assigned"
        assert result.step("src").output == "PRODUCED"

    def test_step_failure_yields_failed_result_with_the_original_exception(self):
        boom = ValueError("step exploded")
        pipeline = Pipeline("fail")
        pipeline.add_step(RecordingStep("bad", raises=boom))

        result, _ = _run(pipeline)

        assert result.state is RunState.FAILED
        assert result.exception is boom, "the original exception must be preserved"
        assert result.error_type == "ValueError"
        assert "step exploded" in (result.error or "")
        assert result.failed_step is not None
        assert result.failed_step.name == "bad"

    def test_downstream_steps_are_skipped_after_a_failure(self):
        pipeline = Pipeline("skip-after-fail")
        pipeline.add_step(RecordingStep("a"))
        pipeline.add_step(RecordingStep("bad", raises=RuntimeError("nope"), depends_on=["a"]))
        later = RecordingStep("c", depends_on=["bad"])
        pipeline.add_step(later)

        result, _ = _run(pipeline)

        assert result.state is RunState.FAILED
        assert result.step("a").state == StepState.SUCCESS.value
        assert result.step("bad").state == StepState.FAILED.value
        assert result.step("c").state == StepState.SKIPPED.value
        assert later.calls == [], "a skipped step must not be invoked"

    def test_invalid_dependency_graph_fails_instead_of_running_partially(self):
        pipeline = Pipeline("cycle")
        pipeline.add_step(RecordingStep("a", depends_on=["b"]))
        pipeline.add_step(RecordingStep("b", depends_on=["a"]))

        result, _ = _run(pipeline)

        assert result.state is RunState.FAILED
        assert isinstance(result.exception, ValueError)
        assert result.steps == [], "nothing may execute when the plan is invalid"

    def test_run_metrics_are_namespaced_by_step(self):
        pipeline = Pipeline("metrics")

        class MetricStep(RecordingStep):
            def run(self, **kwargs: object) -> object:
                self.metrics = {"accuracy": 0.9, "f1": 0.8}
                return "m"

        pipeline.add_step(MetricStep("train"))
        result, _ = _run(pipeline)

        assert result.metrics == {"train_accuracy": 0.9, "train_f1": 0.8}
        assert result.step("train").metrics == {"accuracy": 0.9, "f1": 0.8}


class TestCancellation:
    """Invariant I13 — cancellation produces an observable CANCELLED run."""

    def test_cancellation_before_the_first_step_skips_everything(self):
        pipeline = Pipeline("cancel")
        first = RecordingStep("a")
        pipeline.add_step(first)
        token = CancellationToken()
        token.cancel()

        result, sink = _run(pipeline, cancellation=token)

        assert result.state is RunState.CANCELLED
        assert result.step("a").state == StepState.SKIPPED.value
        assert first.calls == []
        skipped = sink.of_kind(K.STEP_SKIPPED)
        assert skipped and skipped[0].data["reason"] == "cancelled"

    def test_cancellation_stops_the_loop_at_a_step_boundary(self):
        pipeline = Pipeline("mid-cancel")
        token = CancellationToken()

        class IntrospectingStep(RecordingStep):
            def run(self, **kwargs: object) -> object:
                self.calls.append(dict(kwargs))
                token.cancel()  # cancel while running
                return "done"

        pipeline.add_step(IntrospectingStep("a"))
        later = RecordingStep("b", depends_on=["a"])
        pipeline.add_step(later)

        result, _ = _run(pipeline, cancellation=token)

        assert result.state is RunState.CANCELLED
        assert result.step("a").state == StepState.SUCCESS.value
        assert result.step("b").state == StepState.SKIPPED.value
        assert later.calls == []

    def test_in_step_cancellation_is_skipped_not_failed(self):
        pipeline = Pipeline("in-step")
        pipeline.add_step(CancellingStep("a"))

        result, _ = _run(pipeline)

        assert result.state is RunState.CANCELLED
        assert result.step("a").state == StepState.SKIPPED.value
        assert result.error is None, "cancellation is not an error"

    def test_failure_outranks_cancellation(self):
        # A run that broke must not be able to report itself as merely stopped:
        # that would mask a real defect.
        pipeline = Pipeline("fail")
        pipeline.add_step(RecordingStep("bad", raises=RuntimeError("broke")))

        result, _ = _run(pipeline)
        assert result.state is RunState.FAILED

        # Failure *and* a later cancellation: the failure is the fact, the
        # cancellation only explains why we stopped early.
        token = CancellationToken()

        class FailThenCancel(RecordingStep):
            def run(self, **kwargs: object) -> object:
                self.calls.append(dict(kwargs))
                token.cancel()
                raise RuntimeError("broke while cancelling")

        pipeline2 = Pipeline("fail-and-cancel")
        pipeline2.add_step(FailThenCancel("bad"))
        pipeline2.add_step(RecordingStep("never", depends_on=["bad"]))

        result2, _ = _run(pipeline2, cancellation=token)
        assert result2.state is RunState.FAILED, "failure must outrank cancellation"
        assert result2.step("never").state == StepState.SKIPPED.value

    def test_cancelling_before_a_failing_step_yields_cancelled(self):
        # The converse: nothing broke, the user just stopped it first.
        token = CancellationToken()
        token.cancel()
        pipeline = Pipeline("pre-cancel")
        pipeline.add_step(RecordingStep("bad", raises=RuntimeError("never invoked")))

        result, _ = _run(pipeline, cancellation=token)

        assert result.state is RunState.CANCELLED
        assert result.error is None


class TestEventsAndObservability:
    """The engine reports everything through one ordered event stream."""

    def test_run_started_publishes_the_resolved_plan(self):
        pipeline = Pipeline("plan")
        pipeline.add_step(RecordingStep("a"))
        pipeline.add_step(RecordingStep("b", depends_on=["a"]))

        _, sink = _run(pipeline)

        started = sink.of_kind(K.RUN_STARTED)
        assert len(started) == 1
        assert started[0].data["execution_order"] == ["a", "b"]
        assert started[0].data["plan_resolved"] is True

    def test_unresolvable_plan_is_reported_as_unresolved(self):
        pipeline = Pipeline("bad-plan")
        pipeline.add_step(RecordingStep("a", depends_on=["ghost"]))

        _, sink = _run(pipeline)

        started = sink.of_kind(K.RUN_STARTED)
        assert started[0].data["plan_resolved"] is False
        assert started[0].data["execution_order"] == []

    def test_events_are_monotonically_sequenced(self):
        pipeline = Pipeline("seq")
        pipeline.add_step(RecordingStep("a"))
        pipeline.add_step(RecordingStep("b", depends_on=["a"]))

        result, sink = _run(pipeline)

        assert [event.sequence for event in sink.events] == list(range(len(sink.events)))
        assert [event.kind for event in sink.events] == [
            K.RUN_STARTED,
            K.STEP_STARTED,
            K.STEP_FINISHED,
            K.STEP_STARTED,
            K.STEP_FINISHED,
            K.RUN_FINISHED,
        ]
        assert sink.events[-1].state == result.state.value

    def test_visualization_failure_is_non_fatal_but_recorded(self):
        pipeline = Pipeline("viz")

        class BadVisualizer(RecordingStep):
            def visualize(self, **kwargs: object) -> None:
                raise RuntimeError("no plot for you")

        pipeline.add_step(BadVisualizer("vizstep"))

        result, sink = _run(pipeline)

        assert result.state is RunState.SUCCESS, "visualization must not fail the run"
        failures = sink.of_kind(K.VISUALIZATION_FAILED)
        assert len(failures) == 1
        assert "no plot for you" in (failures[0].error or "")

    def test_visualization_can_be_disabled(self):
        pipeline = Pipeline("no-viz")
        calls: list[int] = []

        class CountingVisualizer(RecordingStep):
            def visualize(self, **kwargs: object) -> None:
                calls.append(1)

        pipeline.add_step(CountingVisualizer("v"))

        _run(pipeline, visualize=False)
        assert calls == []


class TestContainment:
    """Invariants I11/I12 — the engine never propagates, always terminates."""

    def test_engine_never_raises_when_a_step_raises_base_exception(self):
        class Boom(BaseException):
            """Not an Exception subclass: the harshest containment case."""

        pipeline = Pipeline("base-exception")
        pipeline.add_step(RecordingStep("bad", raises=Boom("hard crash")))

        result, _ = _run(pipeline)  # must not raise

        assert result.state is RunState.FAILED
        assert result.error_type == "Boom"

    def test_engine_reaches_a_terminal_state_for_every_outcome(self):
        ok = Pipeline("ok")
        ok.add_step(RecordingStep("s"))
        broken = Pipeline("broken")
        broken.add_step(RecordingStep("x", raises=KeyError("k")))
        cyclic = Pipeline("cyclic")
        cyclic.add_step(RecordingStep("a", depends_on=["b"]))
        cyclic.add_step(RecordingStep("b", depends_on=["a"]))
        cancelled_token = CancellationToken()
        cancelled_token.cancel()
        cancelled = Pipeline("cancelled")
        cancelled.add_step(RecordingStep("s"))

        cases = [(Pipeline("empty"), {}), (ok, {}), (broken, {}), (cyclic, {})]
        for pipeline, kwargs in cases:
            result, _ = _run(pipeline, **kwargs)
            assert result.is_terminal, f"{pipeline.name} must reach a terminal state"

        cancelled_result, _ = _run(cancelled, cancellation=cancelled_token)
        assert cancelled_result.state is RunState.CANCELLED

    def test_broken_sink_is_recorded_but_never_fatal(self):
        class ExplodingSink:
            def emit(self, event: object) -> None:
                raise RuntimeError("sink down")

        pipeline = Pipeline("sink-fail")
        pipeline.add_step(RecordingStep("a"))
        context = ExecutionContext(run_id="r", pipeline_name="sink-fail", sink=ExplodingSink())

        result = ExecutionEngine().execute(pipeline, context)

        assert result.state is RunState.SUCCESS, "observability must not decide execution"
        assert result.sink_errors, "but the broken observer must be recorded"
        assert "sink down" in result.sink_errors[0]

    def test_result_round_trips_to_dict_without_output_payloads(self):
        pipeline = Pipeline("serialise")
        pipeline.add_step(RecordingStep("a", result={"big": "payload"}))

        result, _ = _run(pipeline)
        payload = result.to_dict()

        assert payload["state"] == "success"
        assert payload["engine_version"]
        assert payload["steps"][0]["name"] == "a"
        assert "output" not in payload["steps"][0], "outputs are not JSON-safe in general"

    def test_context_defaults_are_explicit_not_global(self):
        context = ExecutionContext(run_id="r", pipeline_name="p")

        assert isinstance(context.sink, NullEventSink)
        assert context.cancellation.is_cancelled is False
        assert context.capture_traceback is True
        assert context.visualize is True

    def test_callback_sink_receives_the_stream(self):
        seen: list = []
        pipeline = Pipeline("callback")
        pipeline.add_step(RecordingStep("a"))
        context = ExecutionContext(
            run_id="r", pipeline_name="callback", sink=CallbackEventSink(seen.append)
        )

        ExecutionEngine().execute(pipeline, context)

        assert seen and seen[0].kind is K.RUN_STARTED
        assert seen[-1].kind is K.RUN_FINISHED
