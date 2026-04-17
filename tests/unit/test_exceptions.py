"""Tests for exceptions."""
import pytest

from autopipe.exceptions import (
    AutoPipeError,
    ConfigurationError,
    PipelineError,
    StepError,
    LLMError,
    RateLimitError,
    AuthenticationError,
)


class TestAutoPipeError:
    """Tests for base AutoPipeError."""

    def test_basic_error(self):
        """Test creating a basic error."""
        error = AutoPipeError("Something went wrong")
        assert error.message == "Something went wrong"
        assert error.details == {}
        assert str(error) == "Something went wrong"

    def test_error_with_details(self):
        """Test error with additional details."""
        error = AutoPipeError(
            "Config error",
            details={"key": "invalid", "expected": "string"}
        )
        assert error.details["key"] == "invalid"


class TestStepError:
    """Tests for StepError."""

    def test_step_error(self):
        """Test creating a step error."""
        error = StepError("Step failed", step_name="my_step")
        assert error.step_name == "my_step"
        assert error.message == "Step failed"

    def test_step_error_without_name(self):
        """Test step error without name."""
        error = StepError("Step failed")
        assert error.step_name is None


class TestLLMError:
    """Tests for LLMError."""

    def test_llm_error(self):
        """Test creating an LLM error."""
        error = LLMError(
            "API failed",
            provider="openai",
            model="gpt-4",
            details={"status_code": 500}
        )
        assert error.provider == "openai"
        assert error.model == "gpt-4"

    def test_rate_limit_error(self):
        """Test rate limit error."""
        error = RateLimitError(
            "Rate limit exceeded",
            provider="openai"
        )
        assert isinstance(error, LLMError)
        assert "Rate limit" in error.message

    def test_authentication_error(self):
        """Test authentication error."""
        error = AuthenticationError("Invalid API key")
        assert isinstance(error, LLMError)
        assert error.message == "Invalid API key"
