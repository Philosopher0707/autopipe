"""Tests for core pipeline functionality."""
import pytest
from unittest.mock import Mock, patch

from autopipe.core.pipeline import Pipeline
from autopipe.core.step import Step
from autopipe.core.steps import PrintStep
from autopipe.exceptions import PipelineError, StepError


class MockStep(Step):
    """Mock step for testing purposes."""
    def run(self, **kwargs):
        return None


class TestStep:
    """Tests for Step base class."""

    def test_step_creation(self):
        """Test creating a basic step."""
        step = MockStep(name="test_step")
        assert step.name == "test_step"
        assert step.depends_on == []
        assert step.output is None

    def test_step_with_dependencies(self):
        """Test creating a step with dependencies."""
        step = MockStep(name="dependent_step", depends_on=["step1", "step2"])
        assert len(step.depends_on) == 2
        assert "step1" in step.depends_on
        assert "step2" in step.depends_on

    def test_step_log_metrics(self):
        """Test logging metrics on a step."""
        step = MockStep(name="test_step")
        step.log_metrics(accuracy=0.95, loss=0.05)
        assert step.metrics["accuracy"] == 0.95
        assert step.metrics["loss"] == 0.05


class TestPipeline:
    """Tests for Pipeline class."""

    def test_pipeline_creation(self):
        """Test creating a pipeline."""
        pipeline = Pipeline("my_pipeline")
        assert pipeline.name == "my_pipeline"
        assert len(pipeline.steps) == 0

    def test_add_step(self):
        """Test adding steps to a pipeline."""
        pipeline = Pipeline("test")
        step1 = PrintStep("step1", message="Hello")
        step2 = PrintStep("step2", message="World")
        
        pipeline.add_step(step1)
        pipeline.add_step(step2)
        
        assert len(pipeline.steps) == 2
        assert pipeline.get_step("step1") == step1
        assert pipeline.get_step("step2") == step2

    def test_get_step_not_found(self):
        """Test getting a non-existent step."""
        pipeline = Pipeline("test")
        with pytest.raises(KeyError):
            pipeline.get_step("nonexistent")

    def test_dependency_graph(self):
        """Test building dependency graph."""
        pipeline = Pipeline("test")
        pipeline.add_step(PrintStep("step1"))
        pipeline.add_step(PrintStep("step2", depends_on=["step1"]))
        
        # Check dependency resolution - execution_order is now a property returning names
        order = pipeline.execution_order
        assert "step1" in order
        assert "step2" in order
        assert order.index("step1") < order.index("step2")

    def test_circular_dependency_detection(self):
        """Test that circular dependencies are detected."""
        # This requires implementing the check
        pipeline = Pipeline("test")
        step1 = PrintStep("step1", depends_on=["step2"])
        step2 = PrintStep("step2", depends_on=["step1"])
        
        pipeline.add_step(step1)
        pipeline.add_step(step2)
        
        # Should raise when trying to get execution order
        with pytest.raises(Exception):
            _ = pipeline.execution_order

    def test_run_empty_pipeline(self):
        """Test running an empty pipeline."""
        pipeline = Pipeline("empty")
        results = pipeline.run()
        assert results == {}

    def test_run_single_step(self):
        """Test running a single step pipeline."""
        pipeline = Pipeline("test")
        step = Mock(spec=Step)
        step.name = "step1"
        step.depends_on = []
        step.run.return_value = "output"
        
        pipeline.add_step(step)
        results = pipeline.run()
        
        assert "step1" in results
        step.run.assert_called_once()
