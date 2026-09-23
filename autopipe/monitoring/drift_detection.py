"""Data Drift Detection module for ML monitoring.

Monitors:
- Statistical drift (distribution changes)
- Feature drift (covariate shift)
- Target drift (concept drift)
- Prediction drift
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from scipy import stats

from autopipe.core.artifacts import record_produced_file
from autopipe.core.step import Step

logger = logging.getLogger(__name__)


def benjamini_hochberg(p_values: List[float]) -> List[float]:
    """Benjamini-Hochberg FDR-adjusted p-values (step-up procedure).

    Returns adjusted p-values in the ORIGINAL order; monotone-enforced so the
    result is a valid step-up adjustment (never below the raw p-value).
    """
    n = len(p_values)
    if n == 0:
        return []
    order = sorted(range(n), key=lambda i: p_values[i])
    ranked = [p_values[i] for i in order]
    adjusted_sorted = [min(1.0, p * n / (rank + 1)) for rank, p in enumerate(ranked)]
    # Enforce monotonicity from largest to smallest
    for k in range(n - 2, -1, -1):
        adjusted_sorted[k] = min(adjusted_sorted[k], adjusted_sorted[k + 1])
    result = [0.0] * n
    for idx_in_order, original_idx in enumerate(order):
        result[original_idx] = adjusted_sorted[idx_in_order]
    return result


@dataclass
class DriftReport:
    """Drift detection report."""

    timestamp: datetime
    feature_name: str
    drift_detected: bool
    metric_name: str
    metric_value: float
    threshold: float
    p_value: Optional[float] = None
    adjusted_p_value: Optional[float] = None
    reference_stats: Optional[Dict] = None
    current_stats: Optional[Dict] = None

    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "feature_name": self.feature_name,
            "drift_detected": self.drift_detected,
            "metric_name": self.metric_name,
            "metric_value": self.metric_value,
            "threshold": self.threshold,
            "p_value": self.p_value,
            "adjusted_p_value": self.adjusted_p_value,
            "reference_stats": self.reference_stats,
            "current_stats": self.current_stats,
        }


class StatisticalDriftDetectorStep(Step):
    """Statistical drift detection using various tests.

    Supported tests:
    - KS test (Kolmogorov-Smirnov) for continuous features
    - Chi-square test for categorical features
    - PSI (Population Stability Index)
    - Wasserstein distance
    """

    def __init__(
        self,
        name: str,
        method: str = "ks",
        threshold: float = 0.05,
        categorical_features: Optional[List[str]] = None,
        **kwargs,
    ):
        """
        Args:
            method: Drift detection method ('ks', 'chi2', 'psi', 'wasserstein')
            threshold: Significance threshold (p-value or PSI threshold)
            categorical_features: List of categorical feature names
        """
        super().__init__(name, **kwargs)
        self.method = method
        self.threshold = threshold
        self.multiple_testing: str = kwargs.get("multiple_testing", "bh")
        self.categorical_features = categorical_features or []
        self.drift_reports: List[DriftReport] = []

    def run(
        self,
        reference_data: pd.DataFrame,
        current_data: pd.DataFrame,
        feature_names: Optional[List[str]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Detect drift between reference and current data.

        Args:
            reference_data: Baseline/reference data
            current_data: Current data to compare
            feature_names: Specific features to check (None = all)

        Returns:
            Dictionary with drift detection results
        """
        if feature_names is None:
            feature_names = reference_data.columns.tolist()

        self.drift_reports = []
        drift_detected_count = 0

        for feature in feature_names:
            if feature not in reference_data.columns or feature not in current_data.columns:
                continue

            ref_col = reference_data[feature].dropna()
            cur_col = current_data[feature].dropna()

            is_categorical = feature in self.categorical_features or ref_col.dtype == "object"

            if is_categorical:
                report = self._detect_categorical_drift(ref_col, cur_col, feature)
            else:
                report = self._detect_numeric_drift(ref_col, cur_col, feature)

            self.drift_reports.append(report)

        # Family-wise control across features: BH on all p-valued reports so
        # testing 50 features at alpha=0.05 does not manufacture ~3 false hits.
        if self.multiple_testing == "bh":
            bh_flags = self._apply_bh_correction(self.drift_reports)
        else:
            bh_flags = {id(r): r.drift_detected for r in self.drift_reports}

        for report in self.drift_reports:
            report.drift_detected = (
                bh_flags.get(id(report), report.drift_detected)
                if (report.p_value is not None and self.multiple_testing == "bh")
                else report.drift_detected
            )
            if report.drift_detected:
                drift_detected_count += 1
                logger.warning(
                    f"Drift detected in feature '{feature_names[0] if False else report.feature_name}': "
                    f"{report.metric_name}={report.metric_value:.4f}"
                    + (
                        f" (BH-adjusted p={report.adjusted_p_value:.4g})"
                        if report.adjusted_p_value is not None
                        else ""
                    )
                )

        # Summary
        total_features = len(feature_names)
        drift_ratio = drift_detected_count / total_features if total_features > 0 else 0

        self.log_metrics(
            total_features_checked=total_features,
            features_with_drift=drift_detected_count,
            drift_ratio=drift_ratio,
            drift_detected=drift_ratio > 0.1,  # Alarm if >10% features drifted
        )

        return {
            "drift_reports": self.drift_reports,
            "drift_detected_count": drift_detected_count,
            "total_features": total_features,
            "drift_ratio": drift_ratio,
            "method": self.method,
        }

    def _detect_numeric_drift(
        self, ref: pd.Series, cur: pd.Series, feature_name: str
    ) -> DriftReport:
        """Detect drift in numeric feature."""
        if self.method == "ks":
            statistic, p_value = stats.ks_2samp(ref, cur)
            drift = p_value < self.threshold
            metric_name = "ks_statistic"
            metric_value = statistic

        elif self.method == "wasserstein":
            from scipy.stats import wasserstein_distance

            distance = wasserstein_distance(ref, cur)
            # Normalize by std of reference
            distance_normalized = distance / ref.std() if ref.std() > 0 else distance
            drift = distance_normalized > self.threshold
            metric_name = "wasserstein_normalized"
            metric_value = distance_normalized
            p_value = None

        elif self.method == "psi":
            psi_value = self._compute_psi(ref, cur)
            drift = psi_value > self.threshold
            metric_name = "psi"
            metric_value = psi_value
            p_value = None

        else:
            raise ValueError(f"Unknown method: {self.method}")

        return DriftReport(
            timestamp=datetime.now(),
            feature_name=feature_name,
            drift_detected=drift,
            metric_name=metric_name,
            metric_value=metric_value,
            threshold=self.threshold,
            p_value=p_value if "p_value" in locals() else None,
            reference_stats={"mean": ref.mean(), "std": ref.std(), "n": len(ref)},
            current_stats={"mean": cur.mean(), "std": cur.std(), "n": len(cur)},
        )

    def _detect_categorical_drift(
        self, ref: pd.Series, cur: pd.Series, feature_name: str
    ) -> DriftReport:
        """Detect drift in categorical feature."""
        # Chi-square test
        ref_counts = ref.value_counts(normalize=True).sort_index()
        cur_counts = cur.value_counts(normalize=True).sort_index()

        # Align categories on RAW counts; chi-square needs observed counts vs
        # expected counts under the reference distribution.
        all_categories = sorted(set(ref_counts.index) | set(cur_counts.index), key=str)
        ref_props = pd.Series(
            [ref_counts.get(c, 0.0) for c in all_categories], index=all_categories
        )
        cur_counts_raw = pd.Series(
            [cur.value_counts().get(c, 0) for c in all_categories], index=all_categories
        )

        # Cells with zero expected count make chi-square undefined; drop them
        # (they contribute no information about distributional change).
        expected_counts = ref_props * len(cur)
        mask = expected_counts > 0
        if mask.sum() < 2 or (int(mask.sum()) != len(all_categories) and mask.sum() < 2):
            p_value = None
            drift = False
        elif (mask).all():
            _chi2, p_value = stats.chisquare(
                cur_counts_raw[mask].to_numpy(), expected_counts[mask].to_numpy()
            )
            drift = p_value < self.threshold
        else:
            # Some zero-expected cells dropped; renormalize expectation
            _chi2, p_value = stats.chisquare(
                cur_counts_raw[mask].to_numpy(),
                (expected_counts[mask] / expected_counts[mask].sum() * len(cur)).to_numpy(),
            )
            drift = p_value < self.threshold

        # Compute total variation distance on proportions
        tv_distance = float(np.abs(ref_props - cur_counts_raw / max(len(cur), 1)).sum() / 2)

        return DriftReport(
            timestamp=datetime.now(),
            feature_name=feature_name,
            drift_detected=tv_distance > 0.2 or drift,  # Use TV distance for practicality
            metric_name="total_variation_distance",
            metric_value=tv_distance,
            threshold=0.2,
            p_value=p_value,
            reference_stats={"categories": len(ref_counts), "n": len(ref)},
            current_stats={"categories": len(cur_counts), "n": len(cur)},
        )

    def _compute_psi(self, expected: pd.Series, actual: pd.Series, buckets: int = 10) -> float:
        """Population Stability Index over EXPECTED-quantile bins.

        The previous implementation rescaled each series to its own min/max,
        which erased location/scale shifts entirely — identical distributions
        and fully shifted ones produced the same PSI. Bins are now deciles of
        the REFERENCE distribution with infinite outer edges so current values
        beyond the reference range land in the edge bins instead of being
        clipped away by a shared range.
        """
        exp = np.asarray(expected, dtype=float)
        act = np.asarray(actual, dtype=float)
        if exp.size == 0 or act.size == 0:
            return 0.0

        quantiles = np.linspace(0, 1, buckets + 1)[1:-1]
        edges = np.unique(np.quantile(exp, quantiles))
        edges = np.concatenate(([-np.inf], edges, [np.inf]))

        eps = 1e-6
        expected_percents = np.clip(np.histogram(exp, edges)[0] / exp.size, eps, None)
        actual_percents = np.clip(np.histogram(act, edges)[0] / act.size, eps, None)

        return float(
            np.sum(
                (expected_percents - actual_percents) * np.log(expected_percents / actual_percents)
            )
        )

    @staticmethod
    def _apply_bh_correction(reports: List["DriftReport"]) -> dict:
        """Apply Benjamini-Hochberg across reports carrying raw p-values.

        Returns {id(report): drift_detected} for those reports only.
        """
        with_p = [(r, r.p_value) for r in reports if r.p_value is not None]
        if not with_p:
            return {}
        adjusted = benjamini_hochberg([p for _, p in with_p])
        flags: dict = {}
        alpha = None
        for (report, _raw), adj in zip(with_p, adjusted, strict=True):
            report.adjusted_p_value = adj
            if alpha is None:
                # BH rejects when adjusted p <= the family alpha; each report
                # carries the configured threshold.
                alpha = report.threshold
            flags[id(report)] = bool(adj <= (report.threshold or 0.05))
        return flags

    def visualize(self, **kwargs):
        """Visualize drift detection results."""
        if not self.drift_reports:
            return

        import matplotlib.pyplot as plt

        # Prepare data
        features = [r.feature_name for r in self.drift_reports]
        metrics = [r.metric_value for r in self.drift_reports]
        drifts = [r.drift_detected for r in self.drift_reports]

        # Sort by metric value
        sorted_indices = np.argsort(metrics)[::-1]
        features = [features[i] for i in sorted_indices]
        metrics = [metrics[i] for i in sorted_indices]
        drifts = [drifts[i] for i in sorted_indices]

        # Plot
        _fig, ax = plt.subplots(figsize=(12, max(6, len(features) * 0.3)))

        colors = ["red" if d else "green" for d in drifts]
        y_pos = np.arange(len(features))

        ax.barh(y_pos, metrics, color=colors, alpha=0.7)
        ax.set_yticks(y_pos)
        ax.set_yticklabels(features)
        ax.axvline(
            self.threshold, color="black", linestyle="--", label=f"Threshold={self.threshold}"
        )
        ax.set_xlabel(f"{self.method.upper()} Value")
        ax.set_ylabel("Feature")
        ax.set_title(f"{self.name} - Drift Detection Results")
        ax.legend()
        ax.invert_yaxis()

        plt.tight_layout()
        path = f"{self.name}_drift_detection.png"
        plt.savefig(path, dpi=150, bbox_inches="tight")
        plt.close()
        record_produced_file(path)


class TargetDriftDetectorStep(Step):
    """Detect drift in target variable (concept drift)."""

    def __init__(
        self,
        name: str,
        method: str = "ks",
        threshold: float = 0.05,
        task_type: str = "classification",
        **kwargs,
    ):
        super().__init__(name, **kwargs)
        self.method = method
        self.threshold = threshold
        self.task_type = task_type

    def run(
        self,
        reference_y: np.ndarray,
        current_y: np.ndarray,
        reference_preds: Optional[np.ndarray] = None,
        current_preds: Optional[np.ndarray] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Detect target drift.

        Args:
            reference_y: Reference target values
            current_y: Current target values
            reference_preds: Reference predictions (for model drift)
            current_preds: Current predictions (for model drift)

        Returns:
            Dictionary with drift results
        """
        results = {}

        # Target distribution drift
        if self.task_type == "classification":
            ref_counts = pd.Series(reference_y).value_counts(normalize=True).sort_index()
            cur_counts = pd.Series(current_y).value_counts(normalize=True).sort_index()

            all_classes = set(ref_counts.index) | set(cur_counts.index)
            ref_aligned = np.array([ref_counts.get(c, 0) for c in all_classes])
            cur_aligned = np.array([cur_counts.get(c, 0) for c in all_classes])

            chi2, p_value = stats.chisquare(
                cur_aligned * len(current_y), ref_aligned * len(current_y)
            )
            target_drift = p_value < self.threshold

            results["target_drift"] = {
                "drift_detected": target_drift,
                "p_value": p_value,
                "chi2_statistic": chi2,
            }

            # Class imbalance change
            ref_imbalance = ref_counts.max() / ref_counts.min() if ref_counts.min() > 0 else np.inf
            cur_imbalance = cur_counts.max() / cur_counts.min() if cur_counts.min() > 0 else np.inf

            results["imbalance_change"] = {
                "reference_imbalance_ratio": ref_imbalance,
                "current_imbalance_ratio": cur_imbalance,
                "imbalance_changed": abs(cur_imbalance - ref_imbalance) > 1.0,
            }

        else:  # Regression
            statistic, p_value = stats.ks_2samp(reference_y, current_y)
            target_drift = p_value < self.threshold

            results["target_drift"] = {
                "drift_detected": target_drift,
                "p_value": p_value,
                "ks_statistic": statistic,
                "reference_mean": np.mean(reference_y),
                "reference_std": np.std(reference_y),
                "current_mean": np.mean(current_y),
                "current_std": np.std(current_y),
            }

        # Model drift (if predictions provided)
        if reference_preds is not None and current_preds is not None:
            performance_ref = self._compute_performance(reference_y, reference_preds)
            performance_cur = self._compute_performance(current_y, current_preds)

            results["performance_drift"] = {
                "reference_performance": performance_ref,
                "current_performance": performance_cur,
                "performance_degraded": performance_cur < performance_ref * 0.95,
            }

        self.log_metrics(**results)
        return results

    def _compute_performance(self, y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """Compute performance metric."""
        if self.task_type == "classification":
            from sklearn.metrics import accuracy_score

            return accuracy_score(y_true, y_pred)
        else:
            from sklearn.metrics import r2_score

            return r2_score(y_true, y_pred)


class PredictionDriftMonitorStep(Step):
    """Monitor model predictions over time."""

    def __init__(self, name: str, alert_threshold: float = 0.1, window_size: int = 1000, **kwargs):
        super().__init__(name, **kwargs)
        self.alert_threshold = alert_threshold
        self.window_size = window_size
        self.prediction_history: List[np.ndarray] = []

    def run(
        self,
        predictions: np.ndarray,
        timestamps: Optional[List[datetime]] = None,
        class_names: Optional[List[str]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Monitor prediction drift.

        Args:
            predictions: Model predictions
            timestamps: Prediction timestamps
            class_names: Class names for classification

        Returns:
            Dictionary with monitoring results
        """
        self.prediction_history.append(predictions)

        # Keep only recent history
        total_predictions = sum(len(p) for p in self.prediction_history)
        while total_predictions > self.window_size and len(self.prediction_history) > 1:
            removed = self.prediction_history.pop(0)
            total_predictions -= len(removed)

        all_preds = np.concatenate(self.prediction_history)

        # Compute statistics
        if len(all_preds.shape) == 2 and all_preds.shape[1] > 1:
            # Multi-class probabilities
            avg_probs = np.mean(all_preds, axis=0)
            entropy = -np.sum(avg_probs * np.log(avg_probs + 1e-10))
            confidence = np.max(avg_probs)

            results = {
                "avg_probabilities": avg_probs.tolist(),
                "entropy": entropy,
                "avg_confidence": confidence,
                "prediction_std": np.std(all_preds, axis=0).mean(),
            }
        else:
            # Binary or regression
            results = {
                "mean_prediction": np.mean(all_preds),
                "std_prediction": np.std(all_preds),
                "min_prediction": np.min(all_preds),
                "max_prediction": np.max(all_preds),
            }

        # Detect trend
        if len(self.prediction_history) >= 2:
            recent = self.prediction_history[-1]
            older = (
                self.prediction_history[-2]
                if len(self.prediction_history) >= 2
                else self.prediction_history[0]
            )

            mean_recent = np.mean(recent)
            mean_older = np.mean(older)

            if mean_older != 0:
                pct_change = abs(mean_recent - mean_older) / abs(mean_older)
            else:
                pct_change = abs(mean_recent - mean_older)

            results["prediction_trend_change"] = pct_change
            results["trend_alert"] = pct_change > self.alert_threshold

        self.log_metrics(**results)
        return results

    def visualize(self, **kwargs):
        """Visualize prediction trends."""
        if len(self.prediction_history) < 2:
            return

        import matplotlib.pyplot as plt

        means = [np.mean(p) for p in self.prediction_history]
        stds = [np.std(p) for p in self.prediction_history]

        plt.figure(figsize=(12, 6))
        x = range(len(self.prediction_history))

        plt.plot(x, means, "b-", label="Mean Prediction", linewidth=2)
        plt.fill_between(
            x,
            np.array(means) - np.array(stds),
            np.array(means) + np.array(stds),
            alpha=0.3,
            label="±1 Std Dev",
        )

        plt.xlabel("Time Window")
        plt.ylabel("Prediction")
        plt.title(f"{self.name} - Prediction Trends Over Time")
        plt.legend()
        plt.grid(True, alpha=0.3)

        plt.tight_layout()
        path = f"{self.name}_prediction_trends.png"
        plt.savefig(path, dpi=150, bbox_inches="tight")
        plt.close()
        record_produced_file(path)


class DriftDashboardStep(Step):
    """Comprehensive drift monitoring dashboard."""

    def __init__(self, name: str, reference_data_path: Optional[str] = None, **kwargs):
        super().__init__(name, **kwargs)
        self.reference_data_path = reference_data_path
        self.drift_reports: List[DriftReport] = []

    def run(
        self,
        reference_data: pd.DataFrame,
        current_data: pd.DataFrame,
        reference_predictions: Optional[np.ndarray] = None,
        current_predictions: Optional[np.ndarray] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Run comprehensive drift analysis.

        Args:
            reference_data: Reference/baseline data
            current_data: Current data to compare
            reference_predictions: Reference model predictions
            current_predictions: Current model predictions

        Returns:
            Dictionary with comprehensive drift report
        """
        results = {}

        # 1. Feature drift
        feature_drift = StatisticalDriftDetectorStep(f"{self.name}_features")
        results["feature_drift"] = feature_drift.run(reference_data, current_data)

        # 2. Prediction drift if available
        if reference_predictions is not None and current_predictions is not None:
            pred_monitor = PredictionDriftMonitorStep(f"{self.name}_predictions")
            results["prediction_drift"] = pred_monitor.run(current_predictions)

        # 3. Summary statistics
        results["summary"] = {
            "n_reference_samples": len(reference_data),
            "n_current_samples": len(current_data),
            "n_features": len(reference_data.columns),
            "columns_in_reference": reference_data.columns.tolist(),
            "columns_in_current": current_data.columns.tolist(),
            "missing_in_current": [
                c for c in reference_data.columns if c not in current_data.columns
            ],
            "new_in_current": [c for c in current_data.columns if c not in reference_data.columns],
        }

        self.log_metrics(
            total_drifted_features=results["feature_drift"]["drift_detected_count"],
            drift_ratio=results["feature_drift"]["drift_ratio"],
        )

        return results

    def generate_markdown_report(self, output_path: str):
        """Generate markdown drift report."""
        if not self.output:
            raise ValueError("Step has not been run yet")

        lines = [
            "# Data Drift Report",
            "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Summary",
            "",
            f"- **Reference Samples:** {self.output['summary']['n_reference_samples']:,}",
            f"- **Current Samples:** {self.output['summary']['n_current_samples']:,}",
            f"- **Total Features:** {self.output['summary']['n_features']}",
            "",
            "## Feature Drift Results",
            "",
            f"- **Features with Drift:** {self.output['feature_drift']['drift_detected_count']}",
            f"- **Drift Ratio:** {self.output['feature_drift']['drift_ratio']:.2%}",
            "",
        ]

        if self.output["feature_drift"]["drift_detected_count"] > 0:
            lines.append("### Drifted Features")
            lines.append("")
            lines.append("| Feature | Metric | Value | Threshold | Status |")
            lines.append("|---------|--------|-------|-----------|--------|")

            for report in self.output["feature_drift"]["drift_reports"]:
                if report.drift_detected:
                    status = "🔴 DRIFT"
                    lines.append(
                        f"| {report.feature_name} | {report.metric_name} | "
                        f"{report.metric_value:.4f} | {report.threshold} | {status} |"
                    )
            lines.append("")

        # Save report
        with open(output_path, "w") as f:
            f.write("\n".join(lines))
        record_produced_file(output_path)

        logger.info(f"Drift report saved to {output_path}")
