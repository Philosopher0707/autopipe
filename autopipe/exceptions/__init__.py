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

    def __init__(self, message: str, step_name: str | None = None, details: dict | None = None):
        super().__init__(message, details)
        self.step_name = step_name


class DependencyError(AutoPipeError):
    """Raised when there's a dependency resolution error."""
    pass


class CircularDependencyError(DependencyError):
    """Raised when circular dependencies are detected."""
    pass


class LLMError(AutoPipeError):
    """Raised when LLM operations fail."""

    def __init__(
        self,
        message: str,
        provider: str | None = None,
        model: str | None = None,
        details: dict | None = None
    ):
        super().__init__(message, details)
        self.provider = provider
        self.model = model


class RateLimitError(LLMError):
    """Raised when rate limit is exceeded."""
    pass


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
