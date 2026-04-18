"""Tests for autopipe.core.loader module."""

import pytest
from autopipe.core.loader import import_class, load_step_from_config, load_pipeline_from_config
from autopipe.core.steps import PrintStep, DataLoaderStep, VisualizationStep
from autopipe.core.pipeline import Pipeline


class TestImportClass:
    def test_import_valid_class(self):
        cls = import_class("autopipe.core.steps.PrintStep")
        assert cls is PrintStep

    def test_import_invalid_module(self):
        with pytest.raises(ValueError, match="Failed to import"):
            import_class("nonexistent_module.SomeClass")

    def test_import_invalid_attribute(self):
        with pytest.raises(ValueError, match="not found in module"):
            import_class("autopipe.core.steps.NonexistentStep")


class TestLoadStepFromConfig:
    def test_load_print_step_by_alias(self):
        step = load_step_from_config({"name": "hello", "type": "print", "params": {"message": "hi"}})
        assert isinstance(step, PrintStep)
        assert step.name == "hello"

    def test_load_print_step_by_full_path(self):
        step = load_step_from_config({
            "name": "hello",
            "type": "autopipe.core.steps.PrintStep",
            "params": {"message": "hi"},
        })
        assert isinstance(step, PrintStep)

    def test_load_step_with_depends_on(self):
        step = load_step_from_config({
            "name": "step_b",
            "type": "print",
            "params": {"message": "b"},
            "depends_on": ["step_a"],
        })
        assert step.depends_on == ["step_a"]

    def test_load_step_missing_name_raises(self):
        with pytest.raises(KeyError):
            load_step_from_config({"type": "print"})

    def test_load_step_unknown_type_raises(self):
        with pytest.raises(ValueError):
            load_step_from_config({"name": "bad", "type": "nonexistent_step_type"})


class TestLoadPipelineFromConfig:
    def test_load_simple_pipeline(self):
        config = {
            "name": "test_pipe",
            "steps": [
                {"name": "load", "type": "data_loader", "params": {"source": "iris.csv", "format": "csv"}},
                {"name": "print", "type": "print", "params": {"message": "done"}, "depends_on": ["load"]},
            ],
        }
        pipeline = load_pipeline_from_config(config)
        assert isinstance(pipeline, Pipeline)
        assert pipeline.name == "test_pipe"
        assert len(pipeline.steps) == 2

    def test_load_empty_pipeline(self):
        config = {"name": "empty", "steps": []}
        pipeline = load_pipeline_from_config(config)
        assert pipeline.name == "empty"
        assert len(pipeline.steps) == 0

    def test_load_pipeline_default_name(self):
        config = {"steps": [{"name": "s1", "type": "print"}]}
        pipeline = load_pipeline_from_config(config)
        assert pipeline.name == "default_pipeline"