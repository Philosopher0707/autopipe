"""Tests for pipeline configuration models."""

import pytest

from autopipe.schemas.models import AutoPipeGlobalConfig, PipelineConfig, StepConfig


class TestStepConfig:
    """Tests for StepConfig model."""

    def test_valid_step_config(self):
        """Test creating a valid StepConfig."""
        config = StepConfig(name="test_step", type="MyStep")
        assert config.name == "test_step"
        assert config.type == "MyStep"
        assert config.params == {}
        assert config.depends_on == []

    def test_step_with_params(self):
        """Test StepConfig with parameters."""
        config = StepConfig(
            name="data_loader",
            type="DataLoaderStep",
            params={"dataset": "iris", "batch_size": 32},
        )
        assert config.params["dataset"] == "iris"
        assert config.params["batch_size"] == 32

    def test_step_with_dependencies(self):
        """Test StepConfig with dependencies."""
        config = StepConfig(
            name="trainer",
            type="TrainerStep",
            depends_on=["data_loader", "preprocessor"],
        )
        assert len(config.depends_on) == 2
        assert "data_loader" in config.depends_on

    def test_invalid_name_empty(self):
        """Test that empty name raises validation error."""
        with pytest.raises(ValueError):
            StepConfig(name="")

    def test_self_dependency_not_allowed(self):
        """Test that self-dependency raises validation error."""
        with pytest.raises(ValueError):
            StepConfig(name="test_step", depends_on=["test_step"])


class TestPipelineConfig:
    """Tests for PipelineConfig model."""

    def test_empty_pipeline(self):
        """Test creating an empty pipeline config."""
        config = PipelineConfig()
        assert config.name == "default_pipeline"
        assert config.steps == []

    def test_pipeline_with_steps(self):
        """Test pipeline with steps."""
        steps = [
            StepConfig(name="step1", type="Step1"),
            StepConfig(name="step2", type="Step2", depends_on=["step1"]),
        ]
        config = PipelineConfig(name="my_pipeline", steps=steps)
        assert len(config.steps) == 2

    def test_duplicate_step_names(self):
        """Test that duplicate step names raise validation error."""
        steps = [
            StepConfig(name="step1"),
            StepConfig(name="step1"),
        ]
        with pytest.raises(ValueError, match="Duplicate step names"):
            PipelineConfig(steps=steps)

    def test_missing_dependency(self):
        """Test that missing dependency raises validation error."""
        steps = [
            StepConfig(name="step1"),
            StepConfig(name="step2", depends_on=["nonexistent"]),
        ]
        with pytest.raises(ValueError, match="non-existent step"):
            PipelineConfig(steps=steps)

    def test_unknown_keys_are_rejected(self):
        """Typo'd keys must fail loudly, not be silently dropped."""
        with pytest.raises(ValueError, match="extra_forbidden"):
            PipelineConfig(name="x", env={"LOG_LEVEL": "INFO"})

    def test_env_and_settings_are_not_pipeline_fields(self):
        """`env:`/`settings:` were never honored by the loader — reject them."""
        with pytest.raises(ValueError):
            PipelineConfig(name="x", env={})
        with pytest.raises(ValueError):
            PipelineConfig(name="x", settings={})

    def test_description_is_accepted(self):
        config = PipelineConfig(name="x", description="a human-readable summary")
        assert config.description == "a human-readable summary"


class TestAutoPipeGlobalConfig:
    """Tests for AutoPipeGlobalConfig model."""

    def test_default_config(self):
        """Test default configuration."""
        config = AutoPipeGlobalConfig()
        assert config.debug is False
        assert config.version == "0.1.0"

    def test_debug_mode(self):
        """Test enabling debug mode."""
        config = AutoPipeGlobalConfig(debug=True)
        assert config.debug is True
