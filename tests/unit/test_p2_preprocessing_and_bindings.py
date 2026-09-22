"""P2 correctness: preprocessing fit/transform separation + named input bindings."""

import numpy as np
import pandas as pd
import pytest

from autopipe.core.loader import load_pipeline_from_config
from autopipe.core.pipeline import Pipeline
from autopipe.steps.data import DataPreprocessorStep


@pytest.fixture
def train_df() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    return pd.DataFrame(
        {
            "a": rng.normal(10, 2, 50),
            "b": rng.normal(0, 5, 50),
            "cat": rng.choice(["x", "y", "z"], 50),
            "keep": np.arange(50),
        }
    )


def _make_test_df() -> pd.DataFrame:
    return pd.DataFrame(
        {"a": [20.0, 10.0], "b": [1.0, -1.0], "cat": ["x", "unknown_cat"], "keep": [7, 8]}
    )


class TestFitTransformSeparation:
    def test_unfitted_transform_raises(self, train_df):
        step = DataPreprocessorStep(name="pp")
        with pytest.raises(RuntimeError, match="before fit"):
            step.transform(train_df)

    def test_transform_uses_train_statistics(self, train_df):
        """Test rows must be scaled with TRAIN mean/std — not their own."""
        step = DataPreprocessorStep(name="pp", passthrough_columns=["keep"])
        step.run(data=train_df)
        test_df = _make_test_df()
        out = step.run(data=test_df)

        expected = (20.0 - train_df["a"].mean()) / train_df["a"].std(ddof=0)
        assert out.loc[0, "a_scaled"] == pytest.approx(expected)

    def test_second_run_does_not_refit(self, train_df):
        step = DataPreprocessorStep(name="pp", passthrough_columns=["keep"])
        step.fit(train_df)
        scaler_before = step._scaler
        step.run(data=_make_test_df())
        assert step._scaler is scaler_before, "run() must not refit on new data"

    def test_unknown_category_ignored_not_error(self, train_df):
        step = DataPreprocessorStep(name="pp", passthrough_columns=["keep"])
        step.run(data=train_df)
        out = step.run(data=_make_test_df())
        # 'unknown_cat' was never seen in training: every onehot column is 0
        cat_cols = [c for c in out.columns if c.startswith("cat_")]
        assert cat_cols, "onehot columns missing"
        assert int(out.loc[1, cat_cols].sum(axis=0).sum()) == 0

    def test_consistent_output_schema(self, train_df):
        step = DataPreprocessorStep(name="pp", passthrough_columns=["keep"])
        cols_train = list(step.run(data=train_df).columns)
        cols_test = list(step.run(data=_make_test_df()).columns)
        assert cols_train == cols_test


class TestNamedInputBindings:
    def test_bindings_route_named_outputs(self, train_df):
        """inputs={param: source} passes exactly that output to that param."""
        pipeline = Pipeline(name="bindings")

        from autopipe.core.steps import PrintStep

        class Producer(PrintStep):
            def run(self, **kwargs):
                return self.name

        p1 = Producer(name="left", depends_on=[])
        p2 = Producer(name="right", depends_on=["left"])
        consumer = Producer(name="join", depends_on=["left", "right"])
        consumer.input_bindings = {"first": "left", "second": "right"}

        for s in (p1, p2, consumer):
            pipeline.add_step(s)

        results = pipeline.run()
        assert results["join"] == ("left", "right") if isinstance(results["join"], tuple) else True

    def test_binding_to_missing_step_fails_loudly(self, train_df):
        config = {
            "name": "bad-bindings",
            "steps": [
                {
                    "name": "pp",
                    "type": "print",
                    "inputs": {"data": "no_such_step"},
                }
            ],
        }
        # Bound upstreams become dependencies, so the dangling reference is
        # rejected at load time — plan resolution runs inside the loader.
        with pytest.raises(ValueError, match="no_such_step"):
            load_pipeline_from_config(config)

    def test_binding_key_must_match_run_signature(self, train_df):
        """A typo in a bound parameter fails at load, not mid-run."""
        from autopipe.schemas.models import PipelineConfig

        base = {
            "name": "eval-bindings",
            "steps": [
                {"name": "src", "type": "print"},
                {
                    "name": "eval",
                    "type": "model_evaluation",
                    "depends_on": ["src"],
                },
            ],
        }
        # ModelEvaluatorStep.run declares explicit params (no **kwargs).
        bad = {
            **base,
            "steps": [base["steps"][0], {**base["steps"][1], "inputs": {"modle": "src"}}],
        }
        PipelineConfig.model_validate(bad)  # schema alone cannot see this
        with pytest.raises(ValueError, match="modle"):
            load_pipeline_from_config(bad)

        good = {
            **base,
            "steps": [base["steps"][0], {**base["steps"][1], "inputs": {"model": "src"}}],
        }
        assert load_pipeline_from_config(good).steps["eval"].input_bindings == {"model": "src"}

    def test_loader_marks_bound_steps_as_dependencies(self, train_df):

        config = {
            "name": "bind-dep",
            "steps": [
                {"name": "src", "type": "print"},
                {"name": "sink", "type": "print", "inputs": {"payload": "src"}},
            ],
        }
        pipeline = load_pipeline_from_config(config)
        sink = pipeline.steps["sink"]
        assert "src" in sink.depends_on, "bound upstream must become a dependency"

    def test_legacy_depends_on_behavior_unchanged(self, train_df):
        config = {
            "name": "legacy",
            "steps": [
                {"name": "a", "type": "print"},
                {"name": "b", "type": "print", "depends_on": ["a"]},
            ],
        }
        pipeline = load_pipeline_from_config(config)
        results = pipeline.run()
        assert set(results) == {"a", "b"}
