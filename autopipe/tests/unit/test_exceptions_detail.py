"""Tests for exception hierarchy details not covered by test_exceptions.py."""

from autopipe.exceptions import (
    AuthenticationError,
    AutoPipeError,
    CircularDependencyError,
    LLMError,
    PipelineError,
    RateLimitError,
    StepError,
)


class TestStepError:
    def test_step_error_with_name(self):
        err = StepError("step_a", "Something went wrong")
        assert err.step_name == "step_a"
        assert "step_a" in str(err)

    def test_step_error_inherits_from_autopipe_error(self):
        assert issubclass(StepError, AutoPipeError)


class TestLLMError:
    def test_llm_error_with_provider_and_model(self):
        err = LLMError("openai", "gpt-4", "API call failed")
        assert err.provider == "openai"
        assert err.model == "gpt-4"

    def test_llm_error_inherits_from_autopipe_error(self):
        assert issubclass(LLMError, AutoPipeError)


class TestRateLimitError:
    def test_rate_limit_is_llm_error(self):
        assert issubclass(RateLimitError, LLMError)

    def test_rate_limit_creation(self):
        err = RateLimitError("openai", "gpt-4", retry_after=60)
        assert err.retry_after == 60


class TestAuthenticationError:
    def test_auth_error_is_llm_error(self):
        assert issubclass(AuthenticationError, LLMError)


class TestCircularDependencyError:
    def test_circular_dep_is_pipeline_error(self):
        assert issubclass(CircularDependencyError, PipelineError)

    def test_circular_dep_message(self):
        err = CircularDependencyError(["a", "b", "a"])
        assert "a" in str(err)
