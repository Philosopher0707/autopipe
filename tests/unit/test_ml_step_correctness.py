"""ML step correctness regressions — silent-wrong-answer class defects.

Each test pins a behaviour that previously produced a plausible but WRONG
result with no error: a model trained on the held-out test split, a declared
run seed that did not govern model randomness, drift reported as absent when
it was present, and cross-validation configuration silently discarded.

The bar for this file is not "the step runs" but "the step computes the thing
it claims to compute".
"""

import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import RandomForestClassifier

from autopipe.core.execution import ExecutionContext, ExecutionEngine, RunRng
from autopipe.core.pipeline import Pipeline
from autopipe.core.step import Step
from autopipe.steps.cross_validation import (
    CrossValidationStep,
    DataSplitterStep,
    StratifiedGroupKFoldStep,
)
from autopipe.steps.evaluation import DriftDetectionStep
from autopipe.steps.training import HyperparameterTunerStep, SklearnTrainerStep


@pytest.fixture
def frame():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(400, 4))
    y = (X[:, 0] + rng.normal(scale=0.3, size=400) > 0).astype(int)
    df = pd.DataFrame(X, columns=[f"f{i}" for i in range(4)])
    df["target"] = y
    return df


def _bind_rng(step, seed):
    """Attach a run RNG exactly the way the engine does before run()."""
    step.run_rng = RunRng.from_seed(seed)
    return step


# --------------------------------------------------------------------------
# F1 — input sniffing must not train on the held-out split
# --------------------------------------------------------------------------


class TestTrainerPicksTrainingData:
    def test_splits_dict_wins_over_raw_frame(self, frame):
        """A raw frame in kwargs must not clobber the declared train split.

        Regression: the sniffing loop had no `break` and the bare-DataFrame
        branch lacked the `y_train is None` guard, so a later raw frame
        overwrote the splits dict and trained on all rows including test.
        """
        splits = DataSplitterStep("split").run(data=frame, target_column="target")
        trainer = SklearnTrainerStep(
            "train",
            model_class=RandomForestClassifier,
            model_params={"n_estimators": 5, "max_depth": 2},
            target_column="target",
        )
        # Deliberately pass the full frame too — the leak vector.
        trainer.run(splits=splits, raw=frame)

        assert trainer.metrics["training_samples"] == len(splits["train"])
        assert trainer.metrics["training_samples"] < len(frame)

    def test_selection_is_order_independent(self, frame):
        """Which input is chosen must not depend on kwargs ordering."""
        splits = DataSplitterStep("split").run(data=frame, target_column="target")

        first = SklearnTrainerStep(
            "a",
            model_class=RandomForestClassifier,
            model_params={"n_estimators": 5},
            target_column="target",
        )
        first.run(splits=splits, raw=frame)

        second = SklearnTrainerStep(
            "b",
            model_class=RandomForestClassifier,
            model_params={"n_estimators": 5},
            target_column="target",
        )
        second.run(raw=frame, splits=splits)

        assert first.metrics["training_samples"] == second.metrics["training_samples"]

    def test_explicit_xy_tuple_still_wins(self, frame):
        """The documented (X, y) contract is preserved."""
        X = frame.drop(columns=["target"]).values
        y = frame["target"].values
        trainer = SklearnTrainerStep(
            "t", model_class=RandomForestClassifier, model_params={"n_estimators": 5}
        )
        trainer.run(data=(X, y))
        assert trainer.metrics["training_samples"] == len(y)

    def test_no_leak_through_the_real_engine(self, frame):
        """End-to-end: a trainer depending on both splitter and raw frame."""

        class Raw(Step):
            def run(self, **kwargs):
                return kwargs["data"]

        p = Pipeline("leak").add_step(Raw("raw"))
        p.add_step(DataSplitterStep("split"))
        p.add_step(
            SklearnTrainerStep(
                "train",
                model_class=RandomForestClassifier,
                model_params={"n_estimators": 5},
                depends_on=["split", "raw"],
                target_column="target",
            )
        )
        res = ExecutionEngine().execute(
            p,
            ExecutionContext(run_id="leak", pipeline_name="leak", initial_inputs={"data": frame}),
        )
        assert res.state.value == "success"
        trained = res.step("train").metrics["training_samples"]
        splits = res.step("split").output
        assert trained == len(splits["train"])
        # val and test rows must both be excluded
        assert trained == len(frame) - len(splits["val"]) - len(splits["test"])
        assert trained < len(frame), "test rows leaked into training"


# --------------------------------------------------------------------------
# F8 — target column must be explicit, not positional
# --------------------------------------------------------------------------


class TestTargetColumn:
    def test_named_target_column_is_honoured(self, frame):
        """target_column wins regardless of column position."""
        trainer = SklearnTrainerStep(
            "t",
            model_class=RandomForestClassifier,
            model_params={"n_estimators": 5},
            target_column="target",
        )
        model = trainer.run(data=frame[["target"] + [f"f{i}" for i in range(4)]])
        assert model.n_features_in_ == 4
        assert set(model.classes_) <= {0, 1}

    def test_missing_target_column_is_an_error(self, frame):
        trainer = SklearnTrainerStep("t", model_class=RandomForestClassifier, target_column="nope")
        with pytest.raises(ValueError, match="nope"):
            trainer.run(data=frame)


# --------------------------------------------------------------------------
# F2 — the declared run seed must govern model randomness
# --------------------------------------------------------------------------


class TestSeedReachesTraining:
    def test_same_seed_same_model(self, frame):
        preds = []
        for _ in range(2):
            trainer = _bind_rng(
                SklearnTrainerStep(
                    "t",
                    model_class=RandomForestClassifier,
                    model_params={"n_estimators": 15, "max_depth": 3},
                ),
                1234,
            )
            preds.append(trainer.run(data=frame).predict(frame.drop(columns=["target"]).values))
        assert np.array_equal(preds[0], preds[1]), "same seed gave different models"

    def test_different_seed_changes_model(self, frame):
        preds = []
        for seed in (1, 2):
            trainer = _bind_rng(
                SklearnTrainerStep(
                    "t",
                    model_class=RandomForestClassifier,
                    model_params={"n_estimators": 15, "max_depth": 3},
                ),
                seed,
            )
            preds.append(trainer.run(data=frame).predict(frame.drop(columns=["target"]).values))
        assert not np.array_equal(preds[0], preds[1]), "run seed had no effect on training"

    def test_explicit_random_state_is_not_clobbered(self, frame):
        trainer = _bind_rng(
            SklearnTrainerStep(
                "t",
                model_class=RandomForestClassifier,
                model_params={"n_estimators": 5, "random_state": 7},
            ),
            99,
        )
        model = trainer.run(data=frame)
        assert model.random_state == 7

    def test_unseeded_run_stays_deterministic(self, frame):
        """No run_rng bound: the step's documented default still applies."""
        preds = []
        for _ in range(2):
            trainer = SklearnTrainerStep(
                "t",
                model_class=RandomForestClassifier,
                model_params={"n_estimators": 15, "max_depth": 3},
            )
            preds.append(trainer.run(data=frame).predict(frame.drop(columns=["target"]).values))
        assert np.array_equal(preds[0], preds[1])

    def test_cv_split_follows_run_seed(self):
        X = np.random.default_rng(0).normal(size=(200, 3))
        y = (X[:, 0] > 0).astype(int)
        scores = []
        for _ in range(2):
            cv = _bind_rng(CrossValidationStep("cv"), 4242)
            res = cv.run(
                model_builder=lambda: RandomForestClassifier(n_estimators=5, random_state=0),
                X=X,
                y=y,
            )
            scores.append(res["mean_val_score"])
        assert scores[0] == scores[1]

    def test_random_search_is_seeded(self):
        X = np.random.default_rng(0).normal(size=(200, 3))
        y = (X[:, 0] > 0).astype(int)
        found = set()
        for _ in range(3):
            tuner = _bind_rng(
                HyperparameterTunerStep(
                    "t",
                    model_class=RandomForestClassifier,
                    param_grid={"max_depth": [2, 3, 4, 5, 6, 7, 8]},
                    search_strategy="random",
                    n_iter=3,
                    cv=3,
                    n_jobs=1,
                ),
                77,
            )
            tuner.run(data=(X, y))
            found.add(tuple(sorted(tuner.best_params_.items())))
        assert len(found) == 1, "unseeded parameter sampling produced different results"

    def test_tuned_estimator_itself_is_seeded(self):
        X = np.random.default_rng(0).normal(size=(200, 3))
        y = (X[:, 0] > 0).astype(int)
        fitted = []
        for _ in range(2):
            tuner = _bind_rng(
                HyperparameterTunerStep(
                    "t",
                    model_class=RandomForestClassifier,
                    param_grid={"max_depth": [3, 5]},
                    cv=3,
                    n_jobs=1,
                ),
                77,
            )
            fitted.append(tuner.run(data=(X, y)).predict(X))
        assert np.array_equal(fitted[0], fitted[1])

    def test_estimator_without_random_state_param_is_tolerated(self):
        """A stateless estimator must not blow up on the seeding path."""
        from sklearn.linear_model import LinearRegression

        X = np.random.default_rng(0).normal(size=(200, 3))
        y = (X[:, 0] > 0).astype(int)
        tuner = _bind_rng(
            HyperparameterTunerStep(
                "t",
                model_class=LinearRegression,
                param_grid={"fit_intercept": [True, False]},
                cv=3,
                n_jobs=1,
            ),
            77,
        )
        assert tuner.run(data=(X, y)) is not None


# --------------------------------------------------------------------------
# F5/F6 — cross-validation must honour its own configuration
# --------------------------------------------------------------------------


class TestCrossValidationConfig:
    def test_constructor_groups_are_used(self):
        X = np.random.default_rng(0).normal(size=(200, 3))
        y = (X[:, 0] > 0).astype(int)
        groups = np.arange(200) // 10
        cv = CrossValidationStep("cv", strategy="group", groups=groups)
        res = cv.run(
            model_builder=lambda: RandomForestClassifier(n_estimators=5, random_state=0),
            X=X,
            y=y,
        )
        assert len(res["fold_results"]) == 5

    def test_group_folds_do_not_split_a_group(self):
        X = np.random.default_rng(0).normal(size=(200, 3))
        y = (X[:, 0] > 0).astype(int)
        groups = np.arange(200) // 10
        cv = CrossValidationStep("cv", strategy="group", groups=groups)
        splitter = cv.get_cv_splitter(y)
        for train_idx, val_idx in splitter.split(X, y, cv.groups):
            assert not set(groups[train_idx]) & set(groups[val_idx])

    def test_every_requested_metric_is_computed(self):
        X = np.random.default_rng(0).normal(size=(200, 3))
        y = (X[:, 0] > 0).astype(int)
        cv = CrossValidationStep("cv", metrics=["accuracy", "f1"])
        res = cv.run(
            model_builder=lambda: RandomForestClassifier(n_estimators=5, random_state=0),
            X=X,
            y=y,
        )
        fold = res["fold_results"][0]
        assert "accuracy" in fold["val_scores"]
        assert "f1" in fold["val_scores"]
        assert "mean_val_accuracy" in res

    def test_primary_metric_still_populates_legacy_keys(self):
        """Back-compat: train_score/val_score keep meaning metrics[0]."""
        X = np.random.default_rng(0).normal(size=(200, 3))
        y = (X[:, 0] > 0).astype(int)
        cv = CrossValidationStep("cv", metrics=["f1", "accuracy"])
        res = cv.run(
            model_builder=lambda: RandomForestClassifier(n_estimators=5, random_state=0),
            X=X,
            y=y,
        )
        fold = res["fold_results"][0]
        assert fold["val_score"] == fold["val_scores"]["f1"]


# --------------------------------------------------------------------------
# F7 — stratified group k-fold must accept ordinary label dtypes
# --------------------------------------------------------------------------


class TestStratifiedGroupKFoldLabels:
    def test_string_labels(self):
        X = np.random.default_rng(0).normal(size=(200, 3))
        y = np.where(X[:, 0] > 0, "yes", "no")
        groups = np.arange(200) // 20
        res = StratifiedGroupKFoldStep("sg").run(X=X, y=y, groups=groups)
        assert len(res["folds"]) == 5

    def test_integer_labels_still_work(self):
        X = np.random.default_rng(0).normal(size=(200, 3))
        y = (X[:, 0] > 0).astype(int)
        groups = np.arange(200) // 20
        res = StratifiedGroupKFoldStep("sg").run(X=X, y=y, groups=groups)
        assert len(res["folds"]) == 5

    def test_groups_stay_intact(self):
        X = np.random.default_rng(0).normal(size=(200, 3))
        y = np.where(X[:, 0] > 0, "yes", "no")
        groups = np.arange(200) // 20
        for fold in StratifiedGroupKFoldStep("sg").run(X=X, y=y, groups=groups)["folds"]:
            assert not set(groups[fold["train_idx"]]) & set(groups[fold["val_idx"]])


# --------------------------------------------------------------------------
# F3/F4 — drift must not report "no drift" when it found drift
# --------------------------------------------------------------------------


class TestDriftReporting:
    @pytest.fixture
    def shifted(self):
        rng = np.random.default_rng(0)
        return rng.normal(size=(500, 3)), rng.normal(loc=5.0, size=(500, 3))

    @pytest.mark.parametrize("method", ["ks_test", "wasserstein", "psi"])
    def test_massive_shift_is_reported(self, shifted, method):
        ref, cur = shifted
        step = DriftDetectionStep("d", reference_data=ref, methods=[method])
        out = step.run(current_data=cur)
        assert out["drift_detected"] is True, f"{method} found drift but reported none"

    @pytest.mark.parametrize("method", ["ks_test", "psi"])
    def test_no_shift_is_not_reported(self, method):
        rng = np.random.default_rng(0)
        ref = rng.normal(size=(500, 3))
        cur = rng.normal(size=(500, 3))
        step = DriftDetectionStep("d", reference_data=ref, methods=[method])
        out = step.run(current_data=cur)
        assert out["drift_detected"] is False

    @pytest.mark.xfail(
        reason=(
            "KNOWN DEFECT (unfixed): the wasserstein cutoff is an ABSOLUTE distance, "
            "but the null distance shrinks as O(1/n), so the false-positive rate is a "
            "function of sample size. Measured on two iid N(0,1) samples, the 0.1 "
            "cutoff fires in 97% of trials at n=100, 73% at n=200, 20% at n=500 and "
            "0% at n=5000. Fixing this needs a calibrated statistic plus "
            "multiplicity correction (monitoring.drift_detection already does "
            "Benjamini-Hochberg); it is a statistical decision, not a one-liner."
        ),
        strict=False,
    )
    def test_no_shift_is_not_reported_wasserstein(self):
        rng = np.random.default_rng(0)
        ref = rng.normal(size=(500, 3))
        cur = rng.normal(size=(500, 3))
        step = DriftDetectionStep("d", reference_data=ref, methods=["wasserstein"])
        out = step.run(current_data=cur)
        assert out["drift_detected"] is False

    def test_combined_methods_agree_with_parts(self, shifted):
        ref, cur = shifted
        both = DriftDetectionStep("d", reference_data=ref, methods=["wasserstein", "psi"]).run(
            current_data=cur
        )
        assert both["drift_detected"] is True
