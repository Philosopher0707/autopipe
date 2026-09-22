"""Invariant I8: VALID means execution-ready.

Every config the repository ships — `examples/*.yaml`, `examples/*.py` that
expose a module-level `pipeline`, and the template emitted by `autopipe create`
— must load through the same path `autopipe run` uses.

Before this test existed, three of the four shipped examples were reported VALID
by `autopipe validate` yet failed to load, because validation only checked that
step classes were *importable*, not that they were *constructible with the
parameters given*.
"""

import json
from pathlib import Path

import pytest
import yaml

from autopipe.core.loader import load_pipeline_from_config
from autopipe.schemas.models import PipelineConfig

EXAMPLES = sorted((Path(__file__).resolve().parents[2] / "examples").glob("*.yaml"))
PY_EXAMPLES = sorted((Path(__file__).resolve().parents[2] / "examples").glob("*.py"))
# world_class_pipeline_demo.py is a step-by-step driver script, not a
# pipeline module: it never builds a Pipeline object end-to-end.
LOADABLE_PY = [p for p in PY_EXAMPLES if p.name != "world_class_pipeline_demo.py"]


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_shipped_example_loads_and_validates(path: Path):
    """Every shipped YAML example must be constructible, not merely importable."""
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    # The full load path: schema validation, alias resolution, the step-type
    # allowlist, constructor arity, binding attachment and the dependency graph.
    pipeline = load_pipeline_from_config(config)
    assert pipeline.name == config["name"]
    assert pipeline.steps, f"{path.name} ships no steps"


def test_every_shipped_example_is_discovered():
    """Guard against the glob silently matching nothing (and skipping the suite)."""
    assert len(EXAMPLES) >= 4, f"expected the shipped examples, found {EXAMPLES}"
    assert len(LOADABLE_PY) >= 3, f"expected loadable .py examples, found {LOADABLE_PY}"


@pytest.mark.parametrize("path", LOADABLE_PY, ids=lambda p: p.name)
def test_shipped_python_example_exposes_a_loadable_pipeline(path: Path):
    """Every shipped pipeline module must expose `pipeline` and load with its
    cycle check — the same path `autopipe run <file>.py` uses."""
    from autopipe.core.runner import load_pipeline_from_module

    pipeline = load_pipeline_from_module(str(path))
    assert pipeline.name
    assert pipeline.steps, f"{path.name} ships no steps"


def test_schema_validation_alone_is_not_execution_readiness():
    """A config can pass the Pydantic schema and still be unconstructible.

    This is the shape of the original defect: schema-valid, importable, and yet
    impossible to instantiate.
    """
    config = {
        "name": "schema-valid-but-unbuildable",
        "steps": [
            {"name": "load", "type": "data_loader", "params": {"dataset": "iris"}},
        ],
    }
    # Schema validation passes...
    PipelineConfig.model_validate(config)
    # ...but the real loader takes `source`, not `dataset`, so loading must fail.
    with pytest.raises(ValueError, match="dataset"):
        load_pipeline_from_config(config)


def test_create_template_output_is_execution_ready(tmp_path, monkeypatch):
    """`autopipe create` must emit a config that validates and loads."""
    from click.testing import CliRunner

    from autopipe.cli import cli

    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(cli, ["create", "generated"])
    assert result.exit_code == 0, result.output

    emitted = tmp_path / "generated.yaml"
    assert emitted.exists(), "create must write the pipeline file"

    config = yaml.safe_load(emitted.read_text(encoding="utf-8"))
    pipeline = load_pipeline_from_config(config)
    assert pipeline.steps


def test_validate_rejects_a_cyclic_dependency_graph(tmp_path):
    """A cycle is schema-valid and buildable; only plan resolution catches it."""
    from click.testing import CliRunner

    from autopipe.cli import cli

    cyclic = tmp_path / "cyclic.yaml"
    cyclic.write_text(
        "name: cyclic\n"
        "steps:\n"
        "  - name: a\n"
        "    type: print\n"
        "    depends_on: [b]\n"
        "  - name: b\n"
        "    type: print\n"
        "    depends_on: [a]\n",
        encoding="utf-8",
    )
    result = CliRunner().invoke(cli, ["validate", str(cyclic)])
    assert result.exit_code != 0, result.output


def test_both_loaders_reject_a_cyclic_graph_at_load_time():
    """Plan resolution lives in the loader itself, not in a wrapper callers skip.

    The cycle is invisible to the Pydantic schema and to step construction;
    only ordering catches it. Both entry points must therefore reject it.
    """
    from autopipe.core.loader import load_executable_pipeline, load_pipeline_from_config

    cyclic = {
        "name": "cyclic",
        "steps": [
            {"name": "a", "type": "print", "depends_on": ["b"]},
            {"name": "b", "type": "print", "depends_on": ["a"]},
        ],
    }
    with pytest.raises(ValueError, match="cycle"):
        load_pipeline_from_config(cyclic)
    with pytest.raises(ValueError, match="cycle"):
        load_executable_pipeline(cyclic)


def test_load_executable_pipeline_resolves_the_plan():
    """Admission must leave the pipeline ready to run, order included."""
    from autopipe.core.loader import load_executable_pipeline

    pipeline = load_executable_pipeline(
        {
            "name": "ordered",
            "steps": [
                {"name": "b", "type": "print", "depends_on": ["a"]},
                {"name": "a", "type": "print"},
            ],
        }
    )
    assert pipeline.execution_order == ["a", "b"]


def test_validate_rejects_a_config_that_cannot_be_constructed(tmp_path):
    """Regression: `autopipe validate` must not report VALID for an unbuildable config."""
    from click.testing import CliRunner

    from autopipe.cli import cli

    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "name: bad\n"
        "steps:\n"
        "  - name: load\n"
        # The real loader takes `source`, not `dataset` — importable, unbuildable.
        "    type: data_loader\n"
        "    params:\n"
        "      dataset: iris\n",
        encoding="utf-8",
    )
    result = CliRunner().invoke(cli, ["validate", str(bad)])
    assert result.exit_code != 0, result.output


def test_validate_accepts_a_python_pipeline():
    """`autopipe validate` handles .py via the same loader `run` uses."""
    from click.testing import CliRunner

    from autopipe.cli import cli

    py_file = Path(__file__).resolve().parents[2] / "examples" / "example_pipeline.py"
    result = CliRunner().invoke(cli, ["validate", str(py_file)])
    assert result.exit_code == 0, result.output


def test_dashboard_pipeline_runs_end_to_end():
    """The shipped print-only example must actually execute, not merely load."""
    path = Path(__file__).resolve().parents[2] / "examples" / "test_dashboard_pipeline.yaml"
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    pipeline = load_pipeline_from_config(config)
    results = pipeline.run()
    assert set(results) == {"load_data", "process", "save"}


def test_usage_example_pipeline_runs_end_to_end():
    """The usage example's module-level pipeline must run with its own data."""
    from autopipe.core.runner import load_pipeline_from_module

    path = Path(__file__).resolve().parents[2] / "examples" / "pipeline_usage_example.py"
    pipeline = load_pipeline_from_module(str(path))

    import importlib.util

    spec = importlib.util.spec_from_file_location("usage_example_mod", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    results = pipeline.run(initial_inputs={"data": mod.make_example_data()})
    # initial_inputs are pre-seeded into outputs, alongside the step results.
    assert set(results) == {"data", "validate", "split", "train"}
    assert results["train"] is not None


def test_run_output_flag_writes_json(tmp_path):
    """`autopipe run --output` dumps results as JSON (was a declared no-op)."""
    from click.testing import CliRunner

    from autopipe.cli import cli

    src = Path(__file__).resolve().parents[2] / "examples" / "test_dashboard_pipeline.yaml"
    out = tmp_path / "results.json"
    result = CliRunner().invoke(cli, ["run", str(src), "--output", str(out)])
    assert result.exit_code == 0, result.output
    data = json.loads(out.read_text(encoding="utf-8"))
    assert set(data) == {"load_data", "process", "save"}


def test_run_rejects_removed_flags():
    """Flags that never did anything are gone — click must reject them."""
    from click.testing import CliRunner

    from autopipe.cli import cli

    src = Path(__file__).resolve().parents[2] / "examples" / "test_dashboard_pipeline.yaml"
    runner = CliRunner()
    for args in (["--step", "load_data"], ["--parallel"], ["--cache"], ["--no-cache"]):
        result = runner.invoke(cli, ["run", str(src), *args])
        assert result.exit_code != 0, f"{args} must be rejected: {result.output}"
