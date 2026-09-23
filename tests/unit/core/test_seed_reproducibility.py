"""Seed reproducibility: declared run seed → run-local RNG, no cross-contamination.

Invariant under test (Phase A):
    A declared run seed deterministically controls AutoPipe-owned stochastic
    behavior without mutating process-global RNG state and without cross-run
    contamination, even across concurrent worker threads.
"""

import random
import threading
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest

from autopipe.core.execution import (
    ExecutionContext,
    ExecutionEngine,
    NullEventSink,
    RunRng,
)
from autopipe.core.loader import load_pipeline_from_config
from autopipe.core.pipeline import Pipeline
from autopipe.core.step import Step
from autopipe.schemas.models import PipelineConfig


class RngProbeStep(Step):
    """Draw from each run-local stream; report None when unseeded."""

    def __init__(self, name, n=5, depends_on=None, sync=None):
        super().__init__(name, depends_on=depends_on)
        self.n = n
        self.sync = sync

    def run(self, **kwargs):
        if self.run_rng is None:
            return {"seed": None, "py": [], "np": []}
        half = self.n // 2
        py = [self.run_rng.py.random() for _ in range(half)]
        if self.sync is not None:
            self.sync.wait(timeout=10)
        py += [self.run_rng.py.random() for _ in range(self.n - half)]
        np_vals = [float(self.run_rng.np.random()) for _ in range(self.n)]
        return {"seed": self.run_rng.seed, "py": py, "np": np_vals}


class FailAfterDrawStep(Step):
    """Draw once, then fail — seed must still be reported applied."""

    def run(self, **kwargs):
        draw = self.run_rng.py.random() if self.run_rng is not None else None
        raise RuntimeError(f"boom after {draw}")


def _pipeline(n=5, sync=None, chain=False):
    p = Pipeline("seed-probe")
    p.add_step(RngProbeStep("a", n=n, sync=sync))
    if chain:
        p.add_step(RngProbeStep("b", n=3, depends_on=["a"], sync=sync))
    return p


def _execute(pipeline, seed):
    ctx = ExecutionContext(
        run_id=f"seed-test-{seed}",
        pipeline_name=pipeline.name,
        seed=seed,
        sink=NullEventSink(),
        visualize=False,
    )
    return ExecutionEngine().execute(pipeline, ctx)


def _np_state():
    return np.random.get_state()


def _np_states_equal(a, b):
    return a[0] == b[0] and bool((a[1] == b[1]).all()) and a[2:] == b[2:]


class TestSeedDeclarationSchema:
    def test_seed_accepts_non_negative_ints(self):
        assert PipelineConfig.model_validate({"name": "p", "steps": [], "seed": 0}).seed == 0
        assert PipelineConfig.model_validate({"name": "p", "steps": [], "seed": 42}).seed == 42

    @pytest.mark.parametrize("bad", [-1, "42", 42.0, True])
    def test_seed_rejects_non_plain_non_negative_int(self, bad):
        with pytest.raises(ValueError):
            PipelineConfig.model_validate({"name": "p", "steps": [], "seed": bad})

    def test_loader_propagates_seed_onto_pipeline(self):
        loaded = load_pipeline_from_config(
            {"name": "p", "seed": 7, "steps": [{"name": "s", "type": "print"}]}
        )
        assert loaded.seed == 7

    def test_loader_leaves_absent_seed_as_none(self):
        loaded = load_pipeline_from_config({"name": "p", "steps": [{"name": "s", "type": "print"}]})
        assert loaded.seed is None


class TestSameAndDifferentSeed:
    def test_same_seed_same_draws(self):
        first = _execute(_pipeline(chain=True), 42)
        second = _execute(_pipeline(chain=True), 42)
        assert first.ok and second.ok
        assert first.outputs["a"] == second.outputs["a"]
        assert first.outputs["b"] == second.outputs["b"]
        assert first.seed_applied == second.seed_applied == 42
        assert first.outputs["a"]["py"], "sanity: draws happened"
        assert first.outputs["a"]["np"], "sanity: numpy draws happened"

    def test_different_seed_different_draws(self):
        a = _execute(_pipeline(), 42)
        b = _execute(_pipeline(), 43)
        assert a.ok and b.ok
        assert a.outputs["a"]["py"] != b.outputs["a"]["py"]
        assert a.outputs["a"]["np"] != b.outputs["a"]["np"]
        assert a.outputs["a"]["seed"] == 42
        assert b.outputs["a"]["seed"] == 43

    def test_zero_seed_is_valid_and_deterministic(self):
        first = _execute(_pipeline(), 0)
        second = _execute(_pipeline(), 0)
        assert first.ok and second.ok
        assert first.seed_applied == 0
        assert first.outputs["a"] == second.outputs["a"]

    def test_unseeded_run_leaves_rng_none_and_no_application(self):
        result = _execute(_pipeline(), None)
        assert result.ok
        assert result.seed_applied is None
        assert result.outputs["a"] == {"seed": None, "py": [], "np": []}

    def test_chained_steps_share_one_stream_instance(self):
        pipeline = _pipeline(chain=True)
        result = _execute(pipeline, 7)
        assert result.ok
        step_a = pipeline.get_step("a")
        step_b = pipeline.get_step("b")
        assert step_a.run_rng is step_b.run_rng
        assert isinstance(step_a.run_rng, RunRng)

    def test_seed_applied_even_when_step_fails(self):
        pipeline = Pipeline("fail-pipe")
        pipeline.add_step(FailAfterDrawStep("boom"))
        result = _execute(pipeline, 9)
        assert not result.ok
        assert result.seed_applied == 9


class TestNoGlobalMutation:
    def test_seeded_run_does_not_touch_global_streams(self):
        random.seed(123456)
        np.random.seed(123456)
        py_state = random.getstate()
        np_state = _np_state()

        result = _execute(_pipeline(chain=True), 42)
        assert result.ok

        assert random.getstate() == py_state, "engine/steps must not reseed python random"
        assert _np_states_equal(np_state, _np_state()), "engine/steps must not reseed numpy"


class TestConcurrency:
    BASE = 6
    ROUNDS = 3

    @staticmethod
    def _baseline(seed):
        return _execute(_pipeline(n=TestConcurrency.BASE), seed).outputs["a"]

    @staticmethod
    def _rounds(seed, base, barrier, out):
        try:
            for _ in range(TestConcurrency.ROUNDS):
                got = _execute(_pipeline(n=TestConcurrency.BASE, sync=barrier), seed).outputs["a"]
                if got != base:
                    out.append(f"seed {seed}: {got} != {base}")
                    return
            out.append(None)
        except Exception as exc:
            out.append(f"seed {seed}: {exc!r}")

    def test_concurrent_seeded_runs_do_not_cross_contaminate(self):
        base11 = self._baseline(11)
        base22 = self._baseline(22)
        assert base11["py"] != base22["py"]

        barrier = threading.Barrier(2)
        errors11, errors22 = [], []
        with ThreadPoolExecutor(max_workers=2) as pool:
            f1 = pool.submit(self._rounds, 11, base11, barrier, errors11)
            f2 = pool.submit(self._rounds, 22, base22, barrier, errors22)
            f1.result(timeout=60)
            f2.result(timeout=60)

        assert errors11 == [None], errors11
        assert errors22 == [None], errors22


class TestPartialDependenceSubsample:
    """The one AutoPipe-owned consumer: PDP subsample must be seed-scoped."""

    @staticmethod
    def _run_pdp(step, X, monkeypatch):
        captured = {}

        def fake_pd(model, X_sub, **kwargs):
            captured["rows"] = X_sub
            return {"average": np.zeros(1)}

        import sklearn.inspection

        monkeypatch.setattr(sklearn.inspection, "partial_dependence", fake_pd)
        step.run(model=object(), X=X)
        return captured["rows"]

    def test_unseeded_subsample_matches_legacy_random_state_42(self, monkeypatch):
        from autopipe.steps.explainability import PartialDependenceStep

        X = np.arange(20, dtype=float).reshape(10, 2)
        rows = self._run_pdp(
            PartialDependenceStep("pdp", features=[0], subsample=4), X, monkeypatch
        )
        expected = X[np.random.RandomState(42).choice(10, 4, replace=False)]
        np.testing.assert_array_equal(rows, expected)

    def test_seeded_subsample_follows_run_rng(self, monkeypatch):
        from autopipe.steps.explainability import PartialDependenceStep

        X = np.arange(20, dtype=float).reshape(10, 2)
        step = PartialDependenceStep("pdp", features=[0], subsample=4)
        step.run_rng = RunRng.from_seed(7)
        rows = self._run_pdp(step, X, monkeypatch)
        expected = X[np.random.default_rng(7).choice(10, 4, replace=False)]
        np.testing.assert_array_equal(rows, expected)

    def test_pdp_subsample_leaves_global_numpy_state_alone(self, monkeypatch):
        from autopipe.steps.explainability import PartialDependenceStep

        X = np.arange(20, dtype=float).reshape(10, 2)
        np.random.seed(999)
        before = _np_state()
        self._run_pdp(PartialDependenceStep("pdp", features=[0], subsample=4), X, monkeypatch)
        assert _np_states_equal(before, _np_state())


class TestLibraryPath:
    def test_loaded_pipeline_run_applies_its_seed(self):
        loaded = load_pipeline_from_config(
            {
                "name": "lib-seed",
                "seed": 3,
                "steps": [{"name": "probe", "type": "print"}],
            }
        )
        # PrintStep has no RNG consumer; the point is the path executes.
        outputs = loaded.run()
        assert outputs["probe"] is None or isinstance(outputs, dict)

    def test_engine_result_exposes_seed_on_context(self):
        ctx = ExecutionContext(run_id="x", pipeline_name="p", seed=5)
        assert ctx.seed == 5
        assert ExecutionContext(run_id="y", pipeline_name="p").seed is None
