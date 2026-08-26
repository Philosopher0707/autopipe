"""Smoke tests: every advertised public name must import and Steps must instantiate.

These tests exist because `autopipe.tracking` / `autopipe.experiments`
silently failed to import (phantom __init__ imports) and several exported
Step classes could not be instantiated (abstract `run` left unimplemented).
"""

import inspect

import pytest

import autopipe


def _iter_public_names():
    yield from autopipe.__all__


def test_all_exports_resolve():
    """Every name in __all__ must be resolvable via the lazy dispatcher."""
    missing = []
    for name in _iter_public_names():
        try:
            getattr(autopipe, name)
        except Exception as e:  # pragma: no cover - reported per-name
            missing.append(f"{name}: {type(e).__name__}: {e}")
    assert not missing, "Unresolvable exports: " + "; ".join(missing)


def test_broken_packages_import():
    """Regression: this package previously raised ModuleNotFoundError.

    (tracking/caching/observability were deleted as orphaned subsystems in
    the structural hardening pass — they had zero non-test consumers.)
    """
    import autopipe.experiments  # noqa: F401


@pytest.mark.parametrize(
    ("module_path", "class_name"),
    [
        ("autopipe.core.steps", "PrintStep"),
        ("autopipe.core.steps", "LLMStep"),
        ("autopipe.core.steps", "VisualizationStep"),
        ("autopipe.core.steps", "FeatureEngineeringStep"),
        ("autopipe.steps.data", "DataLoaderStep"),
        ("autopipe.steps.evaluation", "ModelEvaluatorStep"),
        ("autopipe.steps.cross_validation", "CrossValidationStep"),
        ("autopipe.monitoring.drift_detection", "StatisticalDriftDetectorStep"),
        ("autopipe.tuning.optuna_search", "OptunaSearchStep"),
    ],
)
def test_steps_instantiate(module_path: str, class_name: str):
    """Exported Step subclasses must be concrete (implement run())."""
    import importlib

    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    instance = cls(name="smoke")
    assert isinstance(instance, autopipe.Step)
    # A concrete Step must override run()
    assert (
        not inspect.isfunction(type(instance).run) or type(instance).run is not autopipe.Step.run
    ), f"{class_name} does not implement run()"


def test_loader_allowlist_blocks_arbitrary_imports():
    """YAML step types may only reference trusted autopipe.* roots (RCE guard)."""
    from autopipe.core.loader import import_class

    for malicious in ("os.system", "subprocess.Popen", "builtins.eval", "socket.socket"):
        with pytest.raises(ValueError, match="not allowed"):
            import_class(malicious)


def test_loader_allowlist_permits_builtin_steps():
    from autopipe.core.loader import import_class

    assert import_class("print") is not None
    assert import_class("autopipe.steps.data.DataLoaderStep") is not None
