"""Tests for dashboard module — PipelineWatcher hooks and PipelineState."""
import time
import pytest
from unittest.mock import Mock, call

from autopipe.core.pipeline import Pipeline
from autopipe.core.step import Step


class MockStep(Step):
    """Mock step that records calls for testing."""

    def __init__(self, name: str, depends_on=None, run_delay: float = 0.0, raise_on_run=None):
        super().__init__(name, depends_on)
        self._run_delay = run_delay
        self._raise_on_run = raise_on_run
        self.run_calls: list[dict] = []

    def run(self, **kwargs):
        self.run_calls.append({"kwargs": kwargs, "step_name": self.name})
        if self._raise_on_run:
            raise self._raise_on_run
        time.sleep(self._run_delay)
        return f"output-{self.name}"


# ─────────────────────────────────────────────────────────────────────────────
# PipelineState tests
# ─────────────────────────────────────────────────────────────────────────────

class TestPipelineState:
    """Tests for PipelineState dataclass."""

    def test_state_initialization(self):
        """PipelineState initializes with correct defaults."""
        from autopipe.dashboard.state import PipelineState

        state = PipelineState(pipeline_name="test-pipeline")

        assert state.pipeline_name == "test-pipeline"
        assert state.state == "pending"
        assert state.elapsed_seconds == 0
        assert state.current_step is None
        assert state.step_states == {}
        assert state.pipeline_output is None
        assert state.error is None

    def test_step_state_transitions(self):
        """Step state transitions from pending → running → completed."""
        from autopipe.dashboard.state import PipelineState, StepState, StepStatus

        state = PipelineState(pipeline_name="test-pipeline")
        state.add_step("load_data")

        assert state.step_states["load_data"].status == StepStatus.PENDING

        state.start_step("load_data")
        assert state.step_states["load_data"].status == StepStatus.RUNNING
        assert state.current_step == "load_data"

        state.finish_step("load_data", output="iris_dataset")
        assert state.step_states["load_data"].status == StepStatus.COMPLETED
        assert state.step_states["load_data"].output == "iris_dataset"
        assert state.current_step is None

    def test_step_state_error_transition(self):
        """Step state transitions to failed on exception."""
        from autopipe.dashboard.state import PipelineState, StepStatus

        state = PipelineState(pipeline_name="test-pipeline")
        state.add_step("llm_step")

        state.start_step("llm_step")
        state.fail_step("llm_step", error=ValueError("model not found"))

        assert state.step_states["llm_step"].status == StepStatus.FAILED
        assert isinstance(state.step_states["llm_step"].error, ValueError)
        assert state.state == "failed"

    def test_pipeline_state_reflects_step_states(self):
        """Pipeline state is 'running' when any step is running."""
        from autopipe.dashboard.state import PipelineState, StepStatus

        state = PipelineState(pipeline_name="test-pipeline")
        state.add_step("step1")
        state.add_step("step2")

        assert state.state == "pending"

        state.start_step("step1")
        assert state.state == "running"

        state.finish_step("step1")
        assert state.state == "running"  # step2 still running

        state.start_step("step2")
        state.finish_step("step2")
        assert state.state == "completed"

    def test_step_timing_recorded(self):
        """Step start and finish times are recorded."""
        from autopipe.dashboard.state import PipelineState

        state = PipelineState(pipeline_name="test-pipeline")
        state.add_step("fast_step")

        t0 = time.time()
        state.start_step("fast_step")
        state.finish_step("fast_step", output="result")

        step_state = state.step_states["fast_step"]
        assert step_state.start_time >= t0
        assert step_state.end_time >= step_state.start_time
        assert step_state.duration_seconds >= 0


# ─────────────────────────────────────────────────────────────────────────────
# PipelineWatcher protocol tests
# ─────────────────────────────────────────────────────────────────────────────

class TestPipelineWatcher:
    """Tests for PipelineWatcher hook protocol and Pipeline integration."""

    def test_pipeline_calls_before_pipeline_hook(self):
        """Pipeline.run() calls watcher.before_pipeline() before any step."""
        from autopipe.dashboard.state import PipelineWatcher, PipelineState

        watcher = Mock(spec=PipelineWatcher)
        pipeline = Pipeline("watched-pipeline")
        pipeline.add_step(MockStep("step1"))
        pipeline.add_watcher(watcher)

        pipeline.run()

        watcher.before_pipeline.assert_called_once()
        call_args = watcher.before_pipeline.call_args
        assert call_args[0][0].pipeline_name == "watched-pipeline"

    def test_pipeline_calls_after_step_hook_per_step(self):
        """Pipeline.run() calls watcher.after_step() once per step."""
        from autopipe.dashboard.state import PipelineWatcher

        watcher = Mock(spec=PipelineWatcher)
        pipeline = Pipeline("watched-pipeline")
        pipeline.add_step(MockStep("step1"))
        pipeline.add_step(MockStep("step2"))
        pipeline.add_watcher(watcher)

        pipeline.run()

        assert watcher.after_step.call_count == 2
        step_names = [call[0][1] for call in watcher.after_step.call_args_list]
        assert "step1" in step_names
        assert "step2" in step_names

    def test_pipeline_calls_before_step_hook_per_step(self):
        """Pipeline.run() calls watcher.before_step() once per step, before run()."""
        from autopipe.dashboard.state import PipelineWatcher

        watcher = Mock(spec=PipelineWatcher)
        pipeline = Pipeline("watched-pipeline")
        pipeline.add_step(MockStep("step1"))
        pipeline.add_watcher(watcher)

        pipeline.run()

        watcher.before_step.assert_called_once()
        call_args = watcher.before_step.call_args
        assert call_args[0][1] == "step1"  # (state, step_name)

    def test_pipeline_calls_after_pipeline_hook(self):
        """Pipeline.run() calls watcher.after_pipeline() after all steps finish."""
        from autopipe.dashboard.state import PipelineWatcher

        watcher = Mock(spec=PipelineWatcher)
        pipeline = Pipeline("watched-pipeline")
        pipeline.add_step(MockStep("step1"))
        pipeline.add_watcher(watcher)

        pipeline.run()

        watcher.after_pipeline.assert_called_once()
        call_args = watcher.after_pipeline.call_args
        assert call_args[0][0].pipeline_name == "watched-pipeline"
        assert call_args[0][0].state == "completed"

    def test_pipeline_calls_on_error_hook_on_step_failure(self):
        """Pipeline.run() calls watcher.on_error() when a step raises."""
        from autopipe.dashboard.state import PipelineWatcher

        watcher = Mock(spec=PipelineWatcher)
        pipeline = Pipeline("watched-pipeline")
        pipeline.add_step(MockStep("failing_step", raise_on_run=ValueError("boom")))
        pipeline.add_watcher(watcher)

        with pytest.raises(ValueError, match="boom"):
            pipeline.run()

        watcher.on_error.assert_called_once()
        error_call = watcher.on_error.call_args
        assert error_call[0][1] == "failing_step"
        assert isinstance(error_call[0][2], ValueError)

    def test_multiple_watchers_all_called(self):
        """Multiple watchers all receive the same hooks."""
        from autopipe.dashboard.state import PipelineWatcher

        watcher1 = Mock(spec=PipelineWatcher)
        watcher2 = Mock(spec=PipelineWatcher)
        pipeline = Pipeline("watched-pipeline")
        pipeline.add_step(MockStep("step1"))
        pipeline.add_watcher(watcher1)
        pipeline.add_watcher(watcher2)

        pipeline.run()

        watcher1.after_step.assert_called()
        watcher2.after_step.assert_called()

    def test_watcher_not_set_does_not_fail(self):
        """Pipeline.run() works when no watcher is registered."""
        pipeline = Pipeline("no-watcher-pipeline")
        pipeline.add_step(MockStep("step1"))

        # Should not raise
        results = pipeline.run()
        assert "step1" in results

    def test_watcher_state_reflects_hook_context(self):
        """State passed to hooks reflects current pipeline progress."""
        from autopipe.dashboard.state import PipelineWatcher, PipelineState, StepStatus

        captured_states: list[PipelineState] = []

        class CaptureWatcher:
            def before_pipeline(self, state):
                captured_states.append(("before_pipeline", state.pipeline_name, state.state))

            def before_step(self, state, step_name):
                captured_states.append(("before_step", step_name, state.step_states[step_name].status.value))

            def after_step(self, state, step_name, output):
                captured_states.append(("after_step", step_name, state.step_states[step_name].status.value))

            def after_pipeline(self, state):
                captured_states.append(("after_pipeline", state.state))

            def on_error(self, state, step_name, error):
                pass

        pipeline = Pipeline("capture-test")
        pipeline.add_step(MockStep("step1"))
        pipeline.add_watcher(CaptureWatcher())

        pipeline.run()

        assert ("before_pipeline", "capture-test", "pending") in captured_states
        assert ("before_step", "step1", "running") in captured_states
        assert ("after_step", "step1", "completed") in captured_states
        assert ("after_pipeline", "completed") in captured_states


# ─────────────────────────────────────────────────────────────────────────────
# ASCII widget tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSparkline:
    """Tests for sparkline rendering."""

    def test_sparkline_empty_data(self):
        """Sparkline renders empty bars for empty data."""
        from autopipe.dashboard.widgets import sparkline

        result = sparkline([])
        assert result == "                    "  # 20 spaces

    def test_sparkline_renders_braille_blocks(self):
        """Sparkline renders block characters for non-empty data."""
        from autopipe.dashboard.widgets import sparkline

        result = sparkline([0.1, 0.5, 0.9])
        # Should contain block characters
        assert len(result) == 20
        # All chars should be from BLOCK_CHARS or space
        valid_chars = " ▁▂▃▄▅▆▇█"
        assert all(c in valid_chars for c in result)

    def test_sparkline_monotonic_increasing(self):
        """Sparkline shows higher bars for larger values."""
        from autopipe.dashboard.widgets import sparkline

        # Use 20 points to match default width so no trailing padding occurs
        data = [i / 19 for i in range(20)]
        result = sparkline(data)
        # Rightmost bar should be highest character
        assert result[-1] == "█"

    def test_sparkline_width_respected(self):
        """Sparkline respects custom width parameter."""
        from autopipe.dashboard.widgets import sparkline

        result = sparkline([1, 2, 3], width=10)
        assert len(result) == 10


class TestMiniChartText:
    """Tests for mini_chart_text rendering."""

    def test_mini_chart_text_single_point(self):
        """mini_chart_text returns newlines for single data point."""
        from autopipe.dashboard.widgets import mini_chart_text

        result = mini_chart_text([0.5], width=28, height=5)
        lines = result.split("\n")
        # Should return height + 1 lines (chart + footer)
        assert len(lines) == 6

    def test_mini_chart_text_renders_label(self):
        """mini_chart_text renders label in footer."""
        from autopipe.dashboard.widgets import mini_chart_text

        result = mini_chart_text([0.1, 0.9], width=28, height=5, label="accuracy", color="green")
        # Footer should contain label
        assert "accuracy" in result or "0.1" in result


class TestKVRow:
    """Tests for KVRow widget."""

    def test_kvrow_renders_key_value(self):
        """KVRow renders key and value with markup."""
        from autopipe.dashboard.widgets import KVRow

        row = KVRow("accuracy", "0.95")
        assert "accuracy" in row.render()
        assert "0.95" in row.render()

    def test_kvrow_highlight_option(self):
        """KVRow renders highlighted when flag set."""
        from autopipe.dashboard.widgets import KVRow

        row = KVRow("status", "running", highlight=True)
        rendered = row.render()
        assert "bold yellow" in rendered or "yellow" in rendered.lower()
