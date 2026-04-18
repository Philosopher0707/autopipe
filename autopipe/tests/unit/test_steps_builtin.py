"""Tests for autopipe.core.steps builtin step implementations."""

import pytest
from autopipe.core.steps import PrintStep, DataLoaderStep, VisualizationStep
from autopipe.core.step import Step


class TestPrintStep:
    def test_run_returns_first_kwarg(self):
        step = PrintStep(name="test", message="hello")
        result = step.run(data="my_data")
        assert result == "my_data"

    def test_run_no_kwargs_returns_none(self):
        step = PrintStep(name="test", message="hello")
        result = step.run()
        assert result is None

    def test_run_with_message(self):
        step = PrintStep(name="test", message="Custom: {x}")
        result = step.run(x=42)
        assert result == 42

    def test_step_name(self):
        step = PrintStep(name="my_step")
        assert step.name == "my_step"

    def test_depends_on(self):
        step = PrintStep(name="child", depends_on=["parent"])
        assert step.depends_on == ["parent"]


class TestDataLoaderStep:
    def test_load_iris(self):
        step = DataLoaderStep(name="load_iris", dataset="iris")
        result = step.run()
        assert hasattr(result, "shape")  # DataFrame
        assert result.shape[0] == 150
        assert "target" in result.columns
        assert step.metrics["rows"] == 150

    def test_load_diabetes(self):
        step = DataLoaderStep(name="load_diabetes", dataset="diabetes")
        result = step.run()
        assert hasattr(result, "shape")
        assert result.shape[0] == 442
        assert "target" in result.columns

    def test_unknown_dataset_raises(self):
        step = DataLoaderStep(name="bad", dataset="nonexistent")
        with pytest.raises(ValueError, match="Unknown dataset"):
            step.run()


class TestVisualizationStep:
    def test_run_with_dict_of_numbers(self):
        step = VisualizationStep(name="viz")
        result = step.run(accuracy=0.95, loss=0.05)
        assert isinstance(result, dict)
        assert "chart_accuracy" in result or "chart_loss" in result

    def test_run_with_empty_kwargs(self):
        step = VisualizationStep(name="viz")
        result = step.run()
        assert isinstance(result, dict)
        assert len(result) == 0


class TestStepAbstract:
    def test_cannot_instantiate_step_directly(self):
        with pytest.raises(TypeError):
            Step(name="bad")