"""Tests for autopipe.core.runner module."""


import pytest

from autopipe.core.runner import load_pipeline_from_module, load_pipeline_from_yaml, run


class TestLoadPipelineFromModule:
    def test_load_valid_module(self, tmp_path):
        module_content = """
from autopipe.core.pipeline import Pipeline
from autopipe.core.steps import PrintStep

pipeline = Pipeline(name="test_module")
pipeline.add_step(PrintStep(name="hello", message="hello world"))
"""
        module_file = tmp_path / "test_pipeline.py"
        module_file.write_text(module_content)
        pipeline = load_pipeline_from_module(str(module_file))
        assert pipeline.name == "test_module"
        assert "hello" in pipeline.steps

    def test_load_module_without_pipeline_raises(self, tmp_path):
        module_content = "x = 42\n"
        module_file = tmp_path / "no_pipeline.py"
        module_file.write_text(module_content)
        with pytest.raises((ValueError, AttributeError)):
            load_pipeline_from_module(str(module_file))

    def test_load_nonexistent_file_raises(self):
        with pytest.raises(ValueError):
            load_pipeline_from_module("/nonexistent/path/pipeline.py")


class TestLoadPipelineFromYaml:
    def test_load_valid_yaml(self, tmp_path):
        yaml_content = """
name: test_yaml
steps:
  - name: hello
    type: print
    params:
      message: hello from yaml
"""
        yaml_file = tmp_path / "pipeline.yaml"
        yaml_file.write_text(yaml_content)
        pipeline = load_pipeline_from_yaml(str(yaml_file))
        assert pipeline.name == "test_yaml"
        assert "hello" in pipeline.steps


class TestRun:
    def test_run_unsupported_format(self):
        with pytest.raises(ValueError, match="Unsupported file format"):
            run("pipeline.json")
