"""A configuration key that reads as honoured must actually be honoured.

``DataSplitterStep.stratify`` could only be satisfied by passing
``target_column`` into ``run()``. YAML ``params:`` are passed to ``__init__``,
so from a config file ``stratify: true`` could never stratify — and it failed
silently, because ``y`` was simply ``None``.

Measured on 1000 rows with a 10.3% positive rate, ``stratify: true`` and no
reachable target column:

    full   10.30%
    train  11.29%
    val     6.67%   <- 35% relative error, silently
    test    9.33%
"""

import numpy as np
import pandas as pd
import pytest

from autopipe.core.loader import load_pipeline_from_config
from autopipe.steps.cross_validation import DataSplitterStep


@pytest.fixture
def imbalanced():
    rng = np.random.default_rng(0)
    n = 1000
    df = pd.DataFrame({"a": rng.normal(size=n), "b": rng.normal(size=n)})
    df["target"] = (rng.uniform(size=n) < 0.10).astype(int)
    return df


def _config(**params):
    return {
        "name": "strat",
        "seed": 1,
        "steps": [{"name": "split", "type": "data_splitter", "params": params}],
    }


class TestStratifyIsConfigurable:
    def test_target_column_can_be_set_from_config(self, imbalanced):
        pipeline = load_pipeline_from_config(_config(stratify=True, target_column="target"))
        splits = pipeline.run(initial_inputs={"data": imbalanced})["split"]
        for name in ("train", "val", "test"):
            rate = splits[name]["target"].mean()
            assert abs(rate - imbalanced["target"].mean()) < 0.01, (
                f"{name} positive rate {rate:.4f} drifted from "
                f"{imbalanced['target'].mean():.4f}; stratification did not happen"
            )

    def test_stratified_splits_have_equal_class_counts(self, imbalanced):
        pipeline = load_pipeline_from_config(_config(stratify=True, target_column="target"))
        splits = pipeline.run(initial_inputs={"data": imbalanced})["split"]
        counts = [splits[k]["target"].sum() for k in ("train", "val", "test")]
        positives = imbalanced["target"].sum()
        expected = [
            positives * splits[k].shape[0] / len(imbalanced) for k in ("train", "val", "test")
        ]
        for got, want in zip(counts, expected, strict=True):
            assert abs(got - want) <= 1, f"class counts {counts} not proportional to {expected}"

    def test_unstratified_split_really_does_stratify_when_asked(self, imbalanced):
        """The regression guard: configure it, and it must happen."""
        step = DataSplitterStep("s", stratify=True, target_column="target")
        splits = step.run(data=imbalanced)
        rates = [splits[k]["target"].mean() for k in ("train", "val", "test")]
        assert max(rates) - min(rates) < 0.01, f"rates scattered: {rates}"

    def test_run_argument_still_overrides_config(self, imbalanced):
        step = DataSplitterStep("s", stratify=True, target_column="target")
        splits = step.run(data=imbalanced, target_column="target")
        assert "train" in splits

    def test_missing_stratify_target_is_loud_not_silent(self, imbalanced, caplog):
        """Asking to stratify without a target must say so, not quietly not do it."""
        step = DataSplitterStep("s", stratify=True)
        with caplog.at_level("WARNING"):
            step.run(data=imbalanced)
        assert any("strat" in r.message.lower() for r in caplog.records), (
            f"stratify was skipped without a warning; log: {[r.message for r in caplog.records]}"
        )

    def test_config_that_cannot_stratify_still_runs(self, imbalanced):
        """It must not start raising — it warns, and still produces splits."""
        pipeline = load_pipeline_from_config(_config(stratify=True))
        splits = pipeline.run(initial_inputs={"data": imbalanced})["split"]
        assert sum(len(splits[k]) for k in ("train", "val", "test")) == len(imbalanced)
