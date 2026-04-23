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
        error = StepError(step_name="my_step", message="Step failed")
        assert error.step_name == "my_step"
        assert error.message == "[my_step] Step failed"

    def test_step_error_without_name(self):
        """Test step error without name."""
        error = StepError(message="Step failed")
        assert error.step_name is None
        assert error.message == "Step failed"


class TestLLMError:
    """Tests for LLMError."""

    def test_llm_error(self):
        """Test creating an LLM error."""
        error = LLMError(
            provider="openai",
            model="gpt-4",
            message="API failed",
            details={"status_code": 500}
        )
        assert error.provider == "openai"
        assert error.model == "gpt-4"
        assert error.message == "API failed"

    def test_rate_limit_error(self):
        """Test rate limit error."""
        error = RateLimitError(
            provider="openai",
            message="Rate limit exceeded"
        )
        assert isinstance(error, LLMError)
        assert "Rate limit" in error.message

    def test_authentication_error(self):
        """Test authentication error."""
        error = AuthenticationError(message="Invalid API key")
        assert isinstance(error, LLMError)
        assert error.message == "Invalid API key"
