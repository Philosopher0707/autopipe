"""ModelEvaluatorStep must score the column it claims to score.

Defects found sweeping the modules this branch had not touched:

- ``positive_label`` was accepted, stored, and never read. The binary path
  assumed probability column 1 is the positive class, which only holds when
  ``model.classes_ == [0, 1]``.
- Calibration indexed ``probabilities[arange(n), y_true]`` with the raw label,
  crashing whenever classes were not 0..n-1 (labels like {0, 2}).
- Calibration's ``a_B`` used ``mean(y_true)``: it raises on string labels, and
  for non-[0, 1] labels it averages a 0-2 quantity against a 0-1 confidence.
- ``error_by_class`` keyed on ``int(cls)``, crashing on string labels.
- Permutation importance and RFE / SelectFromModel pinned ``random_state=42``.
"""

import numpy as np
import pytest
from sklearn.ensemble import RandomForestClassifier

from autopipe.core.execution import RunRng
from autopipe.steps.data import FeatureSelectionStep
from autopipe.steps.evaluation import ExplainabilityStep, ModelEvaluatorStep


@pytest.fixture
def features():
    return np.random.default_rng(0).normal(size=(200, 3))


def _fit(features, y):
    return RandomForestClassifier(n_estimators=20, random_state=0).fit(features, y)


class TestPositiveColumn:
    def test_binary_column_one_is_unchanged(self, features):
        """The common [0, 1] case must behave exactly as before."""
        y = np.array([0, 1] * 100)
        ev = ModelEvaluatorStep("ev")
        ev.run(model=_fit(features, y), X_test=features, y_test=y)
        assert set(np.unique(ev.result.predictions)) <= {0, 1}
        assert ev.result.metrics["accuracy"] > 0.8

    def test_predictions_use_the_models_own_labels(self, features):
        """With classes [0, 2] a predicted 1 would be meaningless."""
        y = np.array([0, 2] * 100)
        ev = ModelEvaluatorStep("ev")
        ev.run(model=_fit(features, y), X_test=features, y_test=y)
        assert set(np.unique(ev.result.predictions)) <= {0, 2}, (
            "predictions must be the model's labels, not 0/1"
        )

    def test_positive_label_is_honoured(self, features):
        """With classes [0, 2], positive_label=2 must pick column 1."""
        y = np.array([0, 2] * 100)
        ev = ModelEvaluatorStep("ev", positive_label=2)
        ev.run(model=_fit(features, y), X_test=features, y_test=y)
        assert ev.result.metrics["recall"] > 0.8, "positive_label=2 was not honoured"

    def test_roc_auc_uses_the_positive_column(self, features):
        """Flipping the positive class must change roc_auc, not be ignored."""
        y = np.array([0, 2] * 100)
        model = _fit(features, y)
        correct = ModelEvaluatorStep("ev", positive_label=2)
        correct.run(model=model, X_test=features, y_test=y)
        inverted = ModelEvaluatorStep("ev", positive_label=0)
        inverted.run(model=model, X_test=features, y_test=y)
        assert correct.result.roc_auc > inverted.result.roc_auc


class TestLabelDtypes:
    @pytest.mark.parametrize(
        "y",
        [
            np.array([0, 1] * 100),
            np.array([0, 2] * 100),  # gap: class 1 absent
            np.array(["no", "yes"] * 100),
            np.array([1.0, 2.0] * 100),
        ],
        ids=["binary", "gap-in-labels", "strings", "floats"],
    )
    def test_evaluation_does_not_crash(self, features, y):
        ev = ModelEvaluatorStep("ev")
        ev.run(model=_fit(features, y), X_test=features, y_test=y)
        assert ev.result.metrics["accuracy"] is not None
        assert ev.result.calibration_error is not None

    def test_multiclass_does_not_crash_calibration(self, features):
        y = np.random.default_rng(1).integers(0, 3, 200)
        ev = ModelEvaluatorStep("ev")
        ev.run(model=_fit(features, y), X_test=features, y_test=y)
        assert ev.result.calibration_error is not None

    def test_error_by_class_keeps_string_labels(self, features):
        y = np.array(["no", "yes"] * 100)
        ev = ModelEvaluatorStep("ev")
        ev.run(model=_fit(features, y), X_test=features, y_test=y)
        assert set(ev.result.error_analysis["error_by_class"]) == {"no", "yes"}


def _calibrated_problem():
    rng = np.random.default_rng(0)
    n = 4000
    feats = rng.normal(size=(n, 3))
    p = rng.uniform(0.05, 0.95, size=n)
    y = (rng.uniform(size=n) < p).astype(int)  # labels drawn from p
    return feats, p, y


class TestCalibration:
    def test_calibrated_model_scores_near_zero(self):
        """a_B is the observed positive rate, so a calibrated model is ~0.

        Guards the opposite error too: comparing thresholded predictions
        instead reports ~0.23 for this same perfectly calibrated model.
        """
        feats, p, y = _calibrated_problem()

        class Honest:
            classes_ = np.array([0, 1])

            def predict_proba(self, _X):
                return np.column_stack([1 - p, p])

        ev = ModelEvaluatorStep("ev")
        ev.run(model=Honest(), X_test=feats, y_test=y)
        assert ev.result.calibration_error < 0.05, (
            f"a calibrated model reported ECE {ev.result.calibration_error}"
        )

    def test_overconfident_model_scores_high(self):
        """The other direction: ECE must rise when confidence outruns truth."""
        feats, p, y = _calibrated_problem()

        class Overconfident:
            classes_ = np.array([0, 1])

            def predict_proba(self, _X):
                sharpened = np.clip(0.5 + 3 * (p - 0.5), 0.01, 0.99)
                return np.column_stack([1 - sharpened, sharpened])

        ev = ModelEvaluatorStep("ev")
        ev.run(model=Overconfident(), X_test=feats, y_test=y)
        assert ev.result.calibration_error > 0.1, (
            f"overconfidence reported ECE {ev.result.calibration_error}"
        )


class TestSeedReachesFeatureSteps:
    def test_permutation_importance_follows_run_seed(self, features):
        """Pinning it at 42 meant a declared seed did not govern XAI."""
        y = (features[:, 0] > 0).astype(int)
        model = _fit(features, y)
        out = []
        for seed in (1, 2):
            step = ExplainabilityStep("xai", method="permutation", plot=False)
            step.run_rng = RunRng.from_seed(seed)
            out.append(step.run(model=model, X=features, y=y)["importance"])
        assert list(out[0]) == list(out[1])
        assert out[0] != out[1], "permutation importance ignored the run seed"

    @pytest.mark.parametrize("method", ["rfe", "model_based"])
    def test_feature_selection_passes_run_seed_to_its_estimator(self, method):
        """RFE / SelectFromModel were pinned at random_state=42.

        Asserted on the estimator, not the selected columns: whether the
        chosen subset changes depends on the data; whether the seed arrived
        does not.
        """
        import pandas as pd

        rng = np.random.default_rng(0)
        n = 200
        signal = rng.normal(size=n)
        frame = pd.DataFrame(
            {
                "strong": signal,
                "weak": signal + rng.normal(scale=3.0, size=n),
                "noise_a": rng.normal(size=n),
                "noise_b": rng.normal(size=n),
                "noise_c": rng.normal(size=n),
            }
        )
        target = pd.Series((signal > 0).astype(int), name="target")

        seeds = []
        for seed in (7, 8):
            step = FeatureSelectionStep("fs", method=method, k=2)
            step.run_rng = RunRng.from_seed(seed)
            step.run(data=frame, target=target)
            seeds.append(step._selector.estimator.random_state)
        assert seeds == [7, 8], f"{method} pinned its estimator seed to a constant"

    def test_unseeded_feature_selection_stays_deterministic(self):
        import pandas as pd

        rng = np.random.default_rng(0)
        frame = pd.DataFrame(rng.normal(size=(150, 4)), columns=list("abcd"))
        target = pd.Series((frame["a"] > 0).astype(int))
        picks = [
            FeatureSelectionStep("fs", method="rfe", k=2).run(data=frame, target=target)
            for _ in range(2)
        ]
        assert list(picks[0].columns) == list(picks[1].columns)
