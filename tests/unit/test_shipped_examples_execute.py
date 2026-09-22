"""Invariant I8: VALID means execution-ready.

Every YAML config the repository ships — `examples/` and the template emitted by
`autopipe create` — must load through the same path `autopipe run` uses.

Before this test existed, three of the four shipped examples were reported VALID
by `autopipe validate` yet failed to load, because validation only checked that
step classes were *importable*, not that they were *constructible with the
parameters given*.
"""

from pathlib import Path

import pytest
import yaml

from autopipe.core.loader import load_pipeline_from_config
from autopipe.schemas.models import PipelineConfig

EXAMPLES = sorted((Path(__file__).resolve().parents[2] / "examples").glob("*.yaml"))


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
