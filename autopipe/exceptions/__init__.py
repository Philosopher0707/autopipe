"""Custom exceptions for AutoPipe."""


class AutoPipeError(Exception):
    """Base exception for AutoPipe."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ConfigurationError(AutoPipeError):
    """Raised when there's a configuration error."""
    pass


class ValidationError(AutoPipeError):
    """Raised when validation fails."""
    pass


class PipelineError(AutoPipeError):
    """Raised when pipeline execution fails."""
    pass


class StepError(AutoPipeError):
    """Raised when a step fails."""

    def __init__(self, step_name: str | None = None, message: str = "", details: dict | None = None):
        full_message = f"[{step_name}] {message}" if step_name else message
        super().__init__(full_message, details)
        self.step_name = step_name


class DependencyError(PipelineError):
    """Raised when there's a dependency resolution error."""
    pass


class CircularDependencyError(DependencyError):
    """Raised when circular dependencies are detected."""
    pass


class LLMError(AutoPipeError):
    """Raised when LLM operations fail."""

    def __init__(
        self,
        provider: str | None = None,
        model: str | None = None,
        message: str = "",
        details: dict | None = None
    ):
        super().__init__(message, details)
        self.provider = provider
        self.model = model


class PiAgentError(LLMError):
    """Raised specifically when the pi coding agent fails."""

    def __init__(
        self,
        step_name: str | None = None,
        message: str = "",
        details: dict | None = None,
    ):
        super().__init__(message=message, details=details)
        self.step_name = step_name


class RateLimitError(LLMError):
    """Raised when rate limit is exceeded."""

    def __init__(self, provider: str | None = None, model: str | None = None, message: str = "", retry_after: int | None = None, details: dict | None = None):
        super().__init__(provider=provider, model=model, message=message, details=details)
        self.retry_after = retry_after


class AuthenticationError(LLMError):
    """Raised when authentication fails."""
    pass


class CacheError(AutoPipeError):
    """Raised when cache operations fail."""
    pass


class VisualizationError(AutoPipeError):
    """Raised when visualization fails."""
    pass


class DataLoadingError(AutoPipeError):
    """Raised when data loading fails."""
    pass
