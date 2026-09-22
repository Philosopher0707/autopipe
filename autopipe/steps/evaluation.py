"""AutoPipe Evaluation Steps.

Comprehensive model evaluation for ML/DL with
extensive metrics, visualizations, and automated analysis.
"""

import contextlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from autopipe.core.step import Step


@dataclass
class EvaluationResult:
    """Comprehensive evaluation results."""

    metrics: Dict[str, float] = field(default_factory=dict)
    predictions: Optional[np.ndarray] = None
    probabilities: Optional[np.ndarray] = None
    confusion_matrix: Optional[np.ndarray] = None
    classification_report: Optional[str] = None
    roc_auc: Optional[float] = None
    average_precision: Optional[float] = None
    calibration_error: Optional[float] = None
    fairness_metrics: Optional[Dict[str, Dict[str, float]]] = None
    error_analysis: Optional[Dict[str, Any]] = None


class ModelEvaluatorStep(Step):
    """Comprehensive model evaluation step.

    Supports classification, regression, and multi-label tasks
    with extensive metrics and analysis.
    """

    def __init__(
        self,
        name: str,
        depends_on: Optional[list] = None,
        task_type: str = "classification",
        metrics: Optional[List[str]] = None,
        calculate_proba: bool = True,
        threshold: float = 0.5,
        multi_class: str = "ovr",
        positive_label: int = 1,
        fairness_groups: Optional[str] = None,
        calibration_bins: int = 10,
        error_analysis: bool = True,
    ):
        super().__init__(name, depends_on=depends_on)
        self.task_type = task_type
        self.metrics = metrics or []
        self.calculate_proba = calculate_proba
        self.threshold = threshold
        self.multi_class = multi_class
        self.positive_label = positive_label
        self.fairness_groups = fairness_groups
        self.calibration_bins = calibration_bins
        self.error_analysis = error_analysis
        self.result = EvaluationResult()

    def run(
        self,
        model: Any,
        X_test: np.ndarray | pd.DataFrame,
        y_test: np.ndarray | pd.Series,
        groups: Optional[np.ndarray | pd.Series] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> EvaluationResult:
        """Execute model evaluation."""
        from sklearn import metrics as sklearn_metrics

        context = context or {}

        # Get predictions
        if self.task_type == "classification":
            if hasattr(model, "predict_proba") and self.calculate_proba:
                self.result.probabilities = model.predict_proba(X_test)
                if self.result.probabilities.ndim == 2 and self.result.probabilities.shape[1] == 2:
                    self.result.predictions = (
                        self.result.probabilities[:, 1] >= self.threshold
                    ).astype(int)
                else:
                    self.result.predictions = np.argmax(self.result.probabilities, axis=1)
            else:
                self.result.predictions = model.predict(X_test)
        else:
            self.result.predictions = model.predict(X_test)

        # Calculate metrics based on task type
        if self.task_type == "classification":
            self._calculate_classification_metrics(y_test, sklearn_metrics)
        elif self.task_type == "regression":
            self._calculate_regression_metrics(y_test, sklearn_metrics)
        elif self.task_type == "multilabel":
            self._calculate_multilabel_metrics(y_test, sklearn_metrics)

        # Fairness analysis
        if groups is not None or self.fairness_groups:
            self._calculate_fairness_metrics(
                y_test, groups if groups is not None else X_test[self.fairness_groups]
            )

        # Calibration analysis
        if self.task_type == "classification" and self.calculate_proba:
            self._calculate_calibration(y_test)

        # Error analysis
        if self.error_analysis:
            self._perform_error_analysis(y_test)

        context["evaluation"] = {
            "metrics": self.result.metrics,
            "task_type": self.task_type,
        }

        return self.result

    def _calculate_classification_metrics(self, y_true, sklearn_metrics):
        y_pred = self.result.predictions

        self.result.metrics["accuracy"] = sklearn_metrics.accuracy_score(y_true, y_pred)

        with contextlib.suppress(ValueError):
            self.result.metrics["precision"] = sklearn_metrics.precision_score(
                y_true, y_pred, average="weighted", zero_division=0
            )
            self.result.metrics["recall"] = sklearn_metrics.recall_score(
                y_true, y_pred, average="weighted", zero_division=0
            )
            self.result.metrics["f1"] = sklearn_metrics.f1_score(
                y_true, y_pred, average="weighted", zero_division=0
            )

        with contextlib.suppress(ValueError):
            self.result.confusion_matrix = sklearn_metrics.confusion_matrix(y_true, y_pred)

        with contextlib.suppress(ValueError):
            self.result.classification_report = sklearn_metrics.classification_report(
                y_true, y_pred, zero_division=0
            )

        if self.result.probabilities is not None:
            with contextlib.suppress(ValueError):
                if self.result.probabilities.ndim == 2 and self.result.probabilities.shape[1] == 2:
                    self.result.roc_auc = sklearn_metrics.roc_auc_score(
                        y_true, self.result.probabilities[:, 1]
                    )
                    self.result.average_precision = sklearn_metrics.average_precision_score(
                        y_true, self.result.probabilities[:, 1]
                    )
                else:
                    self.result.roc_auc = sklearn_metrics.roc_auc_score(
                        y_true,
                        self.result.probabilities,
                        multi_class=self.multi_class,
                        average="weighted",
                    )

        if self.result.probabilities is not None:
            with contextlib.suppress(ValueError):
                self.result.metrics["log_loss"] = sklearn_metrics.log_loss(
                    y_true, self.result.probabilities
                )

        with contextlib.suppress(ValueError):
            self.result.metrics["balanced_accuracy"] = sklearn_metrics.balanced_accuracy_score(
                y_true, y_pred
            )

        with contextlib.suppress(ValueError):
            self.result.metrics["mcc"] = sklearn_metrics.matthews_corrcoef(y_true, y_pred)

        with contextlib.suppress(ValueError):
            self.result.metrics["cohen_kappa"] = sklearn_metrics.cohen_kappa_score(y_true, y_pred)

    def _calculate_regression_metrics(self, y_true, sklearn_metrics):
        y_pred = self.result.predictions

        self.result.metrics["mse"] = sklearn_metrics.mean_squared_error(y_true, y_pred)
        self.result.metrics["rmse"] = np.sqrt(self.result.metrics["mse"])
        self.result.metrics["mae"] = sklearn_metrics.mean_absolute_error(y_true, y_pred)
        self.result.metrics["r2"] = sklearn_metrics.r2_score(y_true, y_pred)

        try:
            self.result.metrics["mape"] = sklearn_metrics.mean_absolute_percentage_error(
                y_true, y_pred
            )
        except AttributeError:
            self.result.metrics["mape"] = (
                np.mean(np.abs((y_true - y_pred) / (y_true + 1e-10))) * 100
            )

        self.result.metrics["explained_variance"] = sklearn_metrics.explained_variance_score(
            y_true, y_pred
        )
        self.result.metrics["median_ae"] = sklearn_metrics.median_absolute_error(y_true, y_pred)
        self.result.metrics["max_error"] = sklearn_metrics.max_error(y_true, y_pred)

    def _calculate_multilabel_metrics(self, y_true, sklearn_metrics):
        y_pred = self.result.predictions

        self.result.metrics["hamming_loss"] = sklearn_metrics.hamming_loss(y_true, y_pred)
        self.result.metrics["jaccard_score"] = sklearn_metrics.jaccard_score(
            y_true, y_pred, average="samples", zero_division=0
        )
        self.result.metrics["f1_micro"] = sklearn_metrics.f1_score(
            y_true, y_pred, average="micro", zero_division=0
        )
        self.result.metrics["f1_macro"] = sklearn_metrics.f1_score(
            y_true, y_pred, average="macro", zero_division=0
        )
        self.result.metrics["f1_weighted"] = sklearn_metrics.f1_score(
            y_true, y_pred, average="weighted", zero_division=0
        )

    def _calculate_fairness_metrics(self, y_true, groups):
        y_pred = self.result.predictions

        self.result.fairness_metrics = {}
        unique_groups = np.unique(groups)

        for group in unique_groups:
            mask = groups == group
            group_y_true = y_true[mask]
            group_y_pred = y_pred[mask]

            self.result.fairness_metrics[str(group)] = {
                "count": int(np.sum(mask)),
                "accuracy": float(np.mean(group_y_true == group_y_pred)),
            }

            try:
                from sklearn.metrics import f1_score, precision_score, recall_score

                self.result.fairness_metrics[str(group)]["precision"] = float(
                    precision_score(group_y_true, group_y_pred, zero_division=0)
                )
                self.result.fairness_metrics[str(group)]["recall"] = float(
                    recall_score(group_y_true, group_y_pred, zero_division=0)
                )
                self.result.fairness_metrics[str(group)]["f1"] = float(
                    f1_score(group_y_true, group_y_pred, zero_division=0)
                )
            except Exception:
                pass  # nosec B110 — one unusable group must not abort the fairness report

    def _calculate_calibration(self, y_true):
        """Expected Calibration Error over equal-width probability bins.

        The previous version paired sklearn's ``calibration_curve`` output —
        which DROPS empty bins — against a full histogram of all bins,
        silently misaligning counts with accuracies whenever any bin was
        empty. Binning is now done once and reused for both terms.
        """
        if self.result.probabilities.ndim == 2 and self.result.probabilities.shape[1] == 2:
            prob_pos = self.result.probabilities[:, 1]
        else:
            prob_pos = self.result.probabilities[np.arange(len(y_true)), y_true.astype(int)]

        n_bins = self.calibration_bins
        n = len(prob_pos)
        if n == 0:
            self.result.calibration_error = 0.0
            return

        bin_idx = np.clip((prob_pos * n_bins).astype(int), 0, n_bins - 1)
        ece = 0.0
        reliability = []
        for b in range(n_bins):
            mask = bin_idx == b
            count = int(mask.sum())
            if count == 0:
                continue
            confidence = float(prob_pos[mask].mean())
            accuracy = float(np.asarray(y_true)[mask].mean())
            ece += (count / n) * abs(accuracy - confidence)
            reliability.append(
                {"bin": b, "count": count, "confidence": confidence, "accuracy": accuracy}
            )

        self.result.calibration_error = float(ece)
        self.result.metrics["expected_calibration_error"] = float(ece)

    def _perform_error_analysis(self, y_true):
        errors = y_true != self.result.predictions

        self.result.error_analysis = {
            "error_rate": float(np.mean(errors)),
            "error_count": int(np.sum(errors)),
            "error_by_class": {},
        }

        for cls in np.unique(y_true):
            cls_mask = y_true == cls
            cls_errors = errors[cls_mask]
            self.result.error_analysis["error_by_class"][int(cls)] = {
                "error_rate": float(np.mean(cls_errors)),
                "error_count": int(np.sum(cls_errors)),
            }


class ExplainabilityStep(Step):
    """Model explainability using SHAP and LIME."""

    def __init__(
        self,
        name: str,
        depends_on: Optional[list] = None,
        method: str = "shap",
        background_samples: int = 100,
        num_features: int = 10,
        plot: bool = True,
    ):
        super().__init__(name, depends_on=depends_on)
        self.method = method.lower()
        self.background_samples = background_samples
        self.num_features = num_features
        self.plot = plot
        self.explanations = {}

    def run(
        self,
        model: Any,
        X: np.ndarray | pd.DataFrame,
        feature_names: Optional[List[str]] = None,
        y: Optional[np.ndarray] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        context = context or {}

        if self.method == "shap":
            self.explanations = self._shap_explanation(model, X, feature_names)
        elif self.method == "lime":
            self.explanations = self._lime_explanation(model, X, feature_names)
        elif self.method == "permutation":
            self.explanations = self._permutation_importance(model, X, y, feature_names)

        context["explanations"] = self.explanations
        return self.explanations

    def _shap_explanation(self, model, X, feature_names):
        try:
            import shap
        except ImportError:
            return {"error": "shap not installed"}

        if isinstance(X, pd.DataFrame) and feature_names is None:
            feature_names = list(X.columns)

        X_sample = X[: self.background_samples] if len(X) > self.background_samples else X

        if hasattr(model, "predict_proba"):
            explainer = shap.KernelExplainer(model.predict_proba, X_sample)
            shap_values = explainer.shap_values(X[: min(50, len(X))])
        else:
            explainer = shap.KernelExplainer(model.predict, X_sample)
            shap_values = explainer.shap_values(X[: min(50, len(X))])

        return {
            "shap_values": shap_values,
            "feature_names": feature_names,
            "expected_value": explainer.expected_value,
            "method": "shap",
        }

    def _lime_explanation(self, model, X, feature_names):
        try:
            import lime  # noqa: F401  (availability probe)
            from lime.lime_tabular import LimeTabularExplainer
        except ImportError:
            return {"error": "lime not installed"}

        if isinstance(X, pd.DataFrame):
            X = X.values

        explainer = LimeTabularExplainer(
            X[: self.background_samples],
            feature_names=feature_names or [f"feature_{i}" for i in range(X.shape[1])],
            class_names=["class_0", "class_1"],
            discretize_continuous=True,
        )

        explanations = []
        for i in range(min(10, len(X))):
            exp = explainer.explain_instance(
                X[i],
                model.predict_proba if hasattr(model, "predict_proba") else model.predict,
                num_features=self.num_features,
            )
            explanations.append(exp.as_list())

        return {"lime_explanations": explanations, "method": "lime"}

    def _permutation_importance(self, model, X, y, feature_names):
        from sklearn.inspection import permutation_importance

        result = permutation_importance(model, X, y, n_repeats=10, random_state=42)

        if isinstance(X, pd.DataFrame) and feature_names is None:
            feature_names = list(X.columns)
        else:
            feature_names = feature_names or [f"feature_{i}" for i in range(X.shape[1])]

        importance_dict = {
            name: {"importance": float(imp), "std": float(std)}
            for name, imp, std in zip(
                feature_names,
                result.importances_mean,
                result.importances_std,
                strict=False,
            )
        }

        return {"importance": importance_dict, "method": "permutation_importance"}


class DriftDetectionStep(Step):
    """Detect data and concept drift."""

    def __init__(
        self,
        name: str,
        depends_on: Optional[list] = None,
        reference_data: Optional[np.ndarray] = None,
        drift_threshold: float = 0.05,
        methods: Optional[List[str]] = None,
    ):
        super().__init__(name, depends_on=depends_on)
        self.reference_data = reference_data
        self.drift_threshold = drift_threshold
        self.methods = methods or ["ks_test", "wasserstein"]
        self.drift_results = {}

    def run(
        self,
        current_data: np.ndarray,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        context = context or {}

        if self.reference_data is None:
            raise ValueError("Reference data must be provided for drift detection")

        for method in self.methods:
            if method == "ks_test":
                self.drift_results["ks_test"] = self._ks_test(current_data)
            elif method == "wasserstein":
                self.drift_results["wasserstein"] = self._wasserstein_distance(current_data)
            elif method == "psi":
                self.drift_results["psi"] = self._population_stability_index(current_data)

        overall_drift = any(
            result.get("drift_detected", False) for result in self.drift_results.values()
        )

        context["drift_detection"] = {
            "drift_detected": overall_drift,
            "results": self.drift_results,
        }

        return context["drift_detection"]

    def _ks_test(self, current_data):
        from scipy.stats import ks_2samp

        results = {}
        drift_detected = False

        for i in range(self.reference_data.shape[1]):
            statistic, pvalue = ks_2samp(self.reference_data[:, i], current_data[:, i])

            results[f"feature_{i}"] = {
                "statistic": float(statistic),
                "pvalue": float(pvalue),
                "drift": pvalue < self.drift_threshold,
            }

            if pvalue < self.drift_threshold:
                drift_detected = True

        return {"drift_detected": drift_detected, "per_feature": results}

    def _wasserstein_distance(self, current_data):
        from scipy.stats import wasserstein_distance

        results = {}

        for i in range(self.reference_data.shape[1]):
            dist = wasserstein_distance(self.reference_data[:, i], current_data[:, i])

            results[f"feature_{i}"] = {"distance": float(dist), "drift": dist > 0.1}

        return results

    def _population_stability_index(self, current_data):
        """Calculate Population Stability Index."""
        results = {}

        for i in range(self.reference_data.shape[1]):
            ref_hist, bins = np.histogram(self.reference_data[:, i], bins=10)
            curr_hist, _ = np.histogram(current_data[:, i], bins=bins)

            ref_pct = ref_hist / (ref_hist.sum() + 1e-10)
            curr_pct = curr_hist / (curr_hist.sum() + 1e-10)

            psi = np.sum((curr_pct - ref_pct) * np.log((curr_pct + 1e-10) / (ref_pct + 1e-10)))

            results[f"feature_{i}"] = {"psi": float(psi), "drift": psi > 0.25}

        return results
