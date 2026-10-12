"""A declared run seed must reach every stochastic step on the training path.

The first pass at invariant I25 covered three step classes and missed seven
sites: the data split itself, nested CV, bootstrap, stratified group k-fold,
permutation importance, and — separately — the trainer's own cross-validation
path, which still had the NaN-metric defect that I26 fixed in
``CrossValidationStep`` but not here.

A split that ignores the seed means "reproducible" runs are not reproducible,
and a split is the foundation everything downstream is fitted on.
"""

import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import RandomForestClassifier

from autopipe.core.execution import RunRng
from autopipe.steps.cross_validation import (
    BootstrapValidatorStep,
    DataSplitterStep,
    NestedCrossValidationStep,
    StratifiedGroupKFoldStep,
)
from autopipe.steps.explainability import PermutationImportanceStep
from autopipe.steps.training import SklearnTrainerStep


def _features(n=300, cols=4):
    return np.random.default_rng(0).normal(size=(n, cols))


@pytest.fixture
def frame():
    X = _features()
    df = pd.DataFrame(X, columns=[f"f{i}" for i in range(4)])
    df["target"] = (X[:, 0] > 0).astype(int)
    return df


# --------------------------------------------------------------------------
# The trainer's own CV path had the same NaN defect I26 fixed elsewhere
# --------------------------------------------------------------------------


class TestTrainerCrossValidationMetrics:
    def _trainer(self, **kw):
        return SklearnTrainerStep(
            "t",
            model_class=RandomForestClassifier,
            use_cross_validation=True,
            model_params={"n_estimators": 5},
            **kw,
        )

    def test_undefined_fold_does_not_poison_the_mean(self):
        """roc_auc returns NaN when a fold holds one class.

        Averaging it in logged ``cv_val_roc_auc_mean = nan``, which then reaches
        MetricLog as if it were a measurement — and every comparison against a
        NaN is silently false.
        """
        X = _features(n=100, cols=3)
        y = np.array([1, 1] + [0] * 98)  # 2 positives across 5 unstratified folds
        trainer = self._trainer(cv_folds=5, cv_strategy="kfold", scoring=["accuracy", "roc_auc"])
        trainer.run(data=(X, y))

        assert any(np.isnan(s) for s in trainer.cv_results["test_roc_auc"]), (
            "fixture no longer produces an undefined fold"
        )
        non_finite = [
            k for k, v in trainer.metrics.items() if isinstance(v, float) and not np.isfinite(v)
        ]
        assert not non_finite, f"NaN persisted as a measurement: {non_finite}"
        usable = [s for s in trainer.cv_results["test_roc_auc"] if np.isfinite(s)]
        assert trainer.metrics["cv_val_roc_auc_mean"] == pytest.approx(np.mean(usable))
        assert trainer.metrics["cv_val_roc_auc_dropped_folds"] == len(
            trainer.cv_results["test_roc_auc"]
        ) - len(usable)

    def test_undefined_metric_is_omitted_rather_than_recorded(self):
        """No usable fold must mean no key at all.

        ``MetricLog.value`` is NOT NULL, so a None here would abort run
        finalization; a NaN would be a wrong number that looks like a real one.
        """
        X = _features(n=60, cols=3)
        y = np.zeros(60, dtype=int)  # roc_auc undefined on every fold
        trainer = self._trainer(cv_folds=3, scoring=["accuracy", "roc_auc"])
        trainer.run(data=(X, y))

        assert trainer.metrics.get("cv_val_roc_auc_mean") is None
        assert trainer.metrics["cv_val_roc_auc_dropped_folds"] == 3
        assert "cv_val_accuracy_mean" in trainer.metrics, "usable metrics must survive"
        assert all(v is not None for v in trainer.metrics.values())

    def test_healthy_run_reports_no_dropped_folds(self):
        X = _features(n=200, cols=3)
        y = (X[:, 0] > 0).astype(int)
        trainer = self._trainer(cv_folds=4, scoring=["accuracy", "f1"])
        trainer.run(data=(X, y))
        dropped = [k for k in trainer.metrics if "dropped_folds" in k]
        assert not dropped, f"unexpected dropped-fold keys: {dropped}"


# --------------------------------------------------------------------------
# The seed must govern every stochastic decision
# --------------------------------------------------------------------------


class TestSeedReachesEveryStochasticStep:
    def test_data_splitter_follows_run_seed(self, frame):
        signatures = set()
        for seed in (1, 2, 3):
            step = DataSplitterStep("s")
            step.run_rng = RunRng.from_seed(seed)
            splits = step.run(data=frame, target_column="target")
            signatures.add(tuple(splits["train"].index[:5]))
        assert len(signatures) == 3, "every run seed produced the same split"

    def test_unseeded_splitter_is_still_deterministic(self, frame):
        picks = [
            tuple(DataSplitterStep("s").run(data=frame, target_column="target")["train"].index[:5])
            for _ in range(2)
        ]
        assert picks[0] == picks[1], "an unseeded run must stay reproducible"

    def test_same_seed_splits_identically(self, frame):
        picks = []
        for _ in range(2):
            step = DataSplitterStep("s")
            step.run_rng = RunRng.from_seed(7)
            picks.append(tuple(step.run(data=frame, target_column="target")["train"].index[:5]))
        assert picks[0] == picks[1]

    def test_bootstrap_follows_run_seed(self):
        X = _features(n=120, cols=3)
        y = (X[:, 0] > 0).astype(int)

        # A shallow model on a noisy problem, so out-of-bag scores actually
        # vary: with a deep model on clean data resamples can coincide by chance.
        def weak_model():
            return RandomForestClassifier(n_estimators=5, max_depth=1, random_state=0)

        means = set()
        for seed in (1, 2, 3):
            step = BootstrapValidatorStep("b", n_bootstrap=30)
            step.run_rng = RunRng.from_seed(seed)
            res = step.run(
                model_builder=weak_model,
                X=X,
                y=y,
                metric_fn=lambda a, p: float((a == p).mean()),
            )
            means.add(round(res["mean_score"], 8))
        assert len(means) >= 2, "bootstrap resampling ignored the run seed"

    def test_bootstrap_same_seed_repeats(self):
        X = _features(n=120, cols=3)
        y = (X[:, 0] > 0).astype(int)
        runs = []
        for _ in range(2):
            step = BootstrapValidatorStep("b", n_bootstrap=20)
            step.run_rng = RunRng.from_seed(5)
            res = step.run(
                model_builder=lambda: RandomForestClassifier(n_estimators=5, random_state=0),
                X=X,
                y=y,
                metric_fn=lambda a, p: float((a == p).mean()),
            )
            runs.append(round(res["mean_score"], 8))
        assert runs[0] == runs[1], "the same seed gave different bootstrap results"

    def test_nested_cv_follows_run_seed(self):
        X = _features(n=150, cols=3)
        y = (X[:, 0] > 0).astype(int)
        scores = set()
        for seed in (1, 2):
            step = NestedCrossValidationStep("n", outer_splits=3, inner_splits=2)
            step.run_rng = RunRng.from_seed(seed)
            res = step.run(
                model_builder=lambda **kw: RandomForestClassifier(
                    n_estimators=5, max_depth=kw["max_depth"], random_state=0
                ),
                param_grid={"max_depth": [2, 3]},
                X=X,
                y=y,
            )
            scores.add(tuple(r["best_params"]["max_depth"] for r in res["outer_results"]))
        assert len(scores) > 1, "nested CV folds ignored the run seed"

    def test_stratified_group_kfold_follows_run_seed(self):
        X = _features(n=150, cols=3)
        y = (X[:, 0] > 0).astype(int)
        groups = np.arange(150) // 15
        picks = set()
        for seed in (1, 2):
            step = StratifiedGroupKFoldStep("sg", n_splits=3)
            step.run_rng = RunRng.from_seed(seed)
            res = step.run(X=X, y=y, groups=groups)
            picks.add(tuple(sorted(res["folds"][0]["val_idx"][:5])))
        assert len(picks) > 1, "stratified group k-fold ignored the run seed"

    def test_permutation_importance_step_follows_run_seed(self):
        X = _features(n=120, cols=4)
        y = (X[:, 0] > 0).astype(int)
        model = RandomForestClassifier(n_estimators=10, random_state=0).fit(X, y)
        out = []
        for seed in (1, 2):
            step = PermutationImportanceStep("pi", n_repeats=3)
            step.run_rng = RunRng.from_seed(seed)
            out.append(step.run(model=model, X=X, y=y))
        assert out[0] != out[1], "PermutationImportanceStep ignored the run seed"
