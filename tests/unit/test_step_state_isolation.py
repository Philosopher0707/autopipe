"""Per-run state must not leak between runs on a reused step.

The engine already rebinds ``step.run_rng`` on every run — the behavioural
baseline asserts a reused step gets no stale stream — so reusing a step across
runs is a supported scenario. Two pieces of per-run state were not reset:

``PyTorchTrainerStep`` kept ``best_val_loss``, ``best_weights`` and
``history``. A second run on the same instance therefore could not record its
own best loss, and at the end it loaded the *previous run's* weights into the
returned model. That is the worst shape of bug in this library: a wrong model,
returned silently, with no error anywhere.

``Step.metrics`` accumulates, because ``log_metrics`` updates a dict that is
only ever created in ``__init__``.

The dashboard is not exposed to this: ``core/loader.py`` constructs a fresh
instance per load, and the executor loads per run.
"""

import numpy as np
import pytest

torch = pytest.importorskip("torch")
from torch import nn  # noqa: E402

from autopipe.core.execution import (  # noqa: E402
    ExecutionContext,
    ExecutionEngine,
    RunRng,
)
from autopipe.core.pipeline import Pipeline  # noqa: E402
from autopipe.core.step import Step  # noqa: E402
from autopipe.steps.deep_learning import PyTorchTrainerStep  # noqa: E402


def _builder():
    torch.manual_seed(0)
    return nn.Sequential(nn.Linear(4, 16), nn.ReLU(), nn.Linear(16, 2))


@pytest.fixture
def data():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(300, 4)).astype(np.float32)
    y = (X[:, 0] > 0).astype(np.int64)
    return X, y


@pytest.fixture
def noise():
    rng = np.random.default_rng(1)
    X = rng.normal(size=(300, 4)).astype(np.float32)
    y = rng.integers(0, 2, 300).astype(np.int64)  # nothing learnable
    return X, y


def _trainer(epochs=5):
    return PyTorchTrainerStep(
        "dl",
        model_builder=_builder,
        epochs=epochs,
        batch_size=32,
        validation_split=0.2,
        learning_rate=0.001,
    )


class TestTrainerStateIsPerRun:
    def test_second_run_does_not_return_the_first_runs_weights(self, data, noise):
        """The defect: run 2 returned run 1's trained model.

        Run 2 cannot beat run 1's loss on unlearnable data, so the carried-over
        ``best_weights`` won, and the step loaded them at the end.
        """
        X1, y1 = data
        X2, y2 = noise
        step = _trainer()

        step.run(X_train=X1, y_train=y1, task="classification")
        first_best = step.best_val_loss
        first_weights = {k: v.clone() for k, v in step.best_weights.items()}

        step.run(X_train=X2, y_train=y2, task="classification")

        assert step.best_val_loss != pytest.approx(first_best), (
            "best_val_loss was not reset, so run 2 never recorded its own best"
        )
        unchanged = all(torch.equal(first_weights[k], step.best_weights[k]) for k in first_weights)
        assert not unchanged, "run 2 is still holding run 1's best weights"

    def test_history_does_not_accumulate_across_runs(self, data):
        X, y = data
        step = _trainer(epochs=5)
        first = step.run(X_train=X, y_train=y, task="classification")
        second = step.run(X_train=X, y_train=y, task="classification")

        assert len(first["history"]["val_loss"]) == 5
        assert len(second["history"]["val_loss"]) == 5, "history accumulated across runs"
        assert second["history"]["val_loss"] == first["history"]["val_loss"], (
            "the same seed and data must reproduce the same curve"
        )

    def test_total_epochs_metric_is_per_run(self, data):
        X, y = data
        step = _trainer(epochs=4)
        step.run(X_train=X, y_train=y, task="classification")
        step.run(X_train=X, y_train=y, task="classification")
        assert step.metrics["total_epochs"] == 4

    def test_second_run_reports_its_own_final_loss(self, data):
        X, y = data
        step = _trainer(epochs=4)
        step.run(X_train=X, y_train=y, task="classification")
        second = step.run(X_train=X, y_train=y, task="classification")
        assert step.metrics["final_train_loss"] == pytest.approx(
            second["history"]["train_loss"][-1]
        )

    def test_fresh_instances_still_agree_with_reused_ones(self, data):
        """The fix must not change single-run behaviour."""
        X, y = data
        reused = _trainer(epochs=4)
        reused.run(X_train=X, y_train=y, task="classification")
        second = reused.run(X_train=X, y_train=y, task="classification")

        fresh = _trainer(epochs=4)
        first = fresh.run(X_train=X, y_train=y, task="classification")

        assert second["history"]["val_loss"] == pytest.approx(first["history"]["val_loss"])


class TestStepMetricsDoNotAccumulate:
    def test_engine_resets_metrics_between_runs(self):
        """``log_metrics`` updates a dict created only in ``__init__``."""

        class Counting(Step):
            def run(self, tag=None, **kwargs):
                self.log_metrics(**{f"seen_{tag}": 1})
                return tag

        step = Counting("c")
        pipeline = Pipeline("p").add_step(step)
        engine = ExecutionEngine()

        engine.execute(
            pipeline,
            ExecutionContext(run_id="r1", pipeline_name="p", initial_inputs={"tag": "first"}),
        )
        engine.execute(
            pipeline,
            ExecutionContext(run_id="r2", pipeline_name="p", initial_inputs={"tag": "second"}),
        )

        # Each run logs a differently named key: with one shared key,
        # dict.update overwrites and the accumulation stays hidden.
        assert step.metrics == {"seen_second": 1}, f"metrics carried across runs: {step.metrics}"

    def test_step_metrics_accumulate_within_one_run(self):
        """The reset clears once per run, not once per step invocation."""

        class Counter(Step):
            def run(self, **kwargs):
                self.log_metrics(count=self.metrics.get("count", 0) + 1)
                return self.metrics["count"]

        step = Counter("c")
        pipeline = Pipeline("p").add_step(step)
        result = ExecutionEngine().execute(
            pipeline, ExecutionContext(run_id="r", pipeline_name="p")
        )
        assert step.metrics == {"count": 1}
        # Run-level metrics are namespaced {step}_{metric} by _aggregate_metrics.
        assert result.metrics["c_count"] == 1

    def test_metrics_from_a_failed_step_do_not_survive(self):
        class Flaky(Step):
            def run(self, **kwargs):
                self.log_metrics(attempt=1)
                if kwargs.get("explode"):
                    raise RuntimeError("boom")
                return 1

        step = Flaky("f")
        pipeline = Pipeline("p").add_step(step)
        engine = ExecutionEngine()

        engine.execute(pipeline, ExecutionContext(run_id="ok", pipeline_name="p"))
        engine.execute(
            pipeline,
            ExecutionContext(run_id="bad", pipeline_name="p", initial_inputs={"explode": True}),
        )
        assert step.metrics == {"attempt": 1}, f"a failed run left metrics behind: {step.metrics}"


class TestTrainerReproducibility:
    def test_same_seed_reproduces_the_curve(self, data):
        """The seed still governs what it can: initialisation and shuffling."""
        X, y = data
        torch.manual_seed(3)
        step = _trainer(epochs=4)
        step.run_rng = RunRng.from_seed(11)
        first = step.run(X_train=X, y_train=y, task="classification")

        torch.manual_seed(3)
        step2 = _trainer(epochs=4)
        step2.run_rng = RunRng.from_seed(11)
        second = step2.run(X_train=X, y_train=y, task="classification")

        assert first["history"]["train_loss"] == pytest.approx(second["history"]["train_loss"])
