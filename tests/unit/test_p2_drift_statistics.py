"""P2: drift statistics rewrite — decile PSI, BH correction, honest ECE."""

import numpy as np
import pandas as pd
import pytest

from autopipe.monitoring.drift_detection import (
    StatisticalDriftDetectorStep,
    benjamini_hochberg,
)


class TestDecilePSI:
    def test_identical_distributions_low_psi(self):
        rng = np.random.default_rng(0)
        ref = pd.Series(rng.normal(0, 1, 5000))
        cur = pd.Series(rng.normal(0, 1, 5000))
        step = StatisticalDriftDetectorStep(name="d", method="psi")
        assert step._compute_psi(ref, cur) < 0.05

    def test_shifted_distribution_high_psi(self):
        """Pure mean shift MUST produce large PSI (old code erased shifts)."""
        rng = np.random.default_rng(0)
        ref = pd.Series(rng.normal(0, 1, 5000))
        shifted = pd.Series(rng.normal(3, 1, 5000))
        step = StatisticalDriftDetectorStep(name="d", method="psi")
        psi = step._compute_psi(ref, shifted)
        assert psi > 2.0, f"location shift undetectable: psi={psi}"

    def test_out_of_range_values_land_in_edge_bins(self):
        """Current values beyond reference range must count, not vanish."""
        ref = pd.Series(np.linspace(0, 1, 1000))
        beyond = pd.Series(np.full(1000, 5.0))  # entirely above reference max
        step = StatisticalDriftDetectorStep(name="d", method="psi")
        psi = step._compute_psi(ref, beyond)
        assert psi > 5.0, "out-of-range mass was clipped away"

    def test_psi_nonnegative(self):
        rng = np.random.default_rng(1)
        step = StatisticalDriftDetectorStep(name="d", method="psi")
        for _ in range(10):
            a = pd.Series(rng.normal(0, 1, 300))
            b = pd.Series(rng.normal(0.4, 1.2, 300))
            assert step._compute_psi(a, b) >= 0


class TestBenjaminiHochberg:
    def test_known_toy_example(self):
        raw = [0.001, 0.008, 0.039, 0.041, 0.042, 0.06, 0.074, 0.205, 0.212, 0.216]
        adj = benjamini_hochberg(raw)
        # Largest k with p(k) <= q*k/n is k=2 at q=0.05 (0.008 <= 0.010);
        # step-up rejects exactly those two.
        rejected = [a <= 0.05 for a in adj]
        assert rejected == [True, True] + [False] * 8
        assert adj[0] == pytest.approx(0.001 * 10 / 1)

    def test_monotone_and_never_below_raw(self):
        rng = np.random.default_rng(3)
        raw = list(rng.uniform(0, 1, 40))
        adj = benjamini_hochberg(raw)
        assert all(a >= p for a, p in zip(adj, raw, strict=True))
        assert adj == sorted(adj, reverse=True) or all(
            adj[i] <= adj[i + 1] for i in range(len(adj) - 1) if raw[i] <= raw[i + 1]
        )
        assert all(0 <= a <= 1 for a in adj)

    def test_empty_and_single(self):
        assert benjamini_hochberg([]) == []
        assert benjamini_hochberg([0.03]) == [0.03]


class TestFamilyWiseControl:
    def test_bh_controls_false_discovery_across_features(self):
        """20 null features + 1 real shift at alpha=0.05 flags only the signal."""
        rng = np.random.default_rng(11)
        cols = {f"null_{i}": rng.normal(0, 1, 400) for i in range(20)}
        cols["signal"] = np.concatenate([rng.normal(0, 1, 200), rng.normal(2, 1, 200)])
        ref_df = pd.DataFrame({k: v[:200] for k, v in cols.items()})
        cur_df = pd.DataFrame({k: v[200:] for k, v in cols.items()})

        detector = StatisticalDriftDetectorStep(name="bh", method="ks", threshold=0.05)
        result = detector.run(reference_data=ref_df, current_data=cur_df)

        flagged = [r.feature_name for r in result["drift_reports"] if r.drift_detected]
        assert "signal" in flagged
        assert len(flagged) <= 3, f"FDR uncontrolled: flagged {flagged}"


class TestCategoricalChiSquare:
    def test_zero_expected_cells_do_not_crash(self):
        rng = np.random.default_rng(5)
        ref = pd.Series(rng.choice(["a", "b", "c"], 300))
        cur = pd.Series(rng.choice(["a", "b"], 300))  # category absent now
        step = StatisticalDriftDetectorStep(name="cat", method="ks")
        report = step._detect_categorical_drift(ref, cur, "feat")
        assert report.p_value is None or np.isfinite(report.p_value)


class TestCalibrationECE:
    def test_ece_bins_align_when_some_are_empty(self):
        """Probabilities clustered near 1 leave low bins empty; ECE must not misalign."""
        from autopipe.steps.evaluation import EvaluationResult, ModelEvaluatorStep

        rng = np.random.default_rng(9)
        n = 400
        y_true = rng.integers(0, 2, n).astype(float)
        probs = np.column_stack([1 - np.linspace(0.55, 0.99, n), np.linspace(0.55, 0.99, n)])

        step = ModelEvaluatorStep(name="ev", metrics=["accuracy"])
        step.result = EvaluationResult()
        step.result.probabilities = probs
        step.result.predictions = (probs[:, 1] >= 0.5).astype(int)
        step._calculate_calibration(y_true)
        ece = step.result.calibration_error

        # Recompute honestly with single binning
        prob_pos = probs[:, 1]
        idx = np.clip((prob_pos * 10).astype(int), 0, 9)
        expected = 0.0
        for b in range(10):
            m = idx == b
            if m.any():
                expected += m.sum() / n * abs(y_true[m].mean() - prob_pos[m].mean())
        assert ece == pytest.approx(expected)
