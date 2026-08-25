"""Pydantic models for configuration validation."""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class StepConfig(BaseModel):
    """Configuration for a pipeline step."""

    name: str = Field(..., min_length=1, description="Unique step name")
    type: str = Field(default="autopipe.core.steps.PrintStep", description="Step class path")
    params: Dict[str, Any] = Field(default_factory=dict, description="Step parameters")
    depends_on: List[str] = Field(default_factory=list, description="Dependency step names")
    inputs: Dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Named input bindings: maps this step's run() parameter name to "
            "the upstream step whose output feeds it. Each referenced step is "
            "treated as a dependency. When empty, all outputs of depends_on "
            "steps are passed as kwargs (legacy behavior)."
        ),
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Step name must be alphanumeric with underscores or hyphens")
        return v

    @field_validator("depends_on")
    @classmethod
    def validate_self_reference(cls, v: List[str], info) -> List[str]:
        name = info.data.get("name")
        if name and name in v:
            raise ValueError(f"Step '{name}' cannot depend on itself")
        return v


class PipelineConfig(BaseModel):
    """Configuration for a pipeline."""

    name: str = Field(default="default_pipeline", description="Pipeline name")
    env: Dict[str, str] = Field(default_factory=dict, description="Environment variables")
    settings: Dict[str, Any] = Field(default_factory=dict, description="Pipeline settings")
    steps: List[StepConfig] = Field(default_factory=list, description="Pipeline steps")

    @model_validator(mode="after")
    def validate_step_names_unique(self) -> "PipelineConfig":
        names = [step.name for step in self.steps]
        if len(names) != len(set(names)):
            from collections import Counter

            duplicates = [name for name, count in Counter(names).items() if count > 1]
            raise ValueError(f"Duplicate step names found: {duplicates}")
        return self

    @model_validator(mode="after")
    def validate_dependencies_exist(self) -> "PipelineConfig":
        names = {step.name for step in self.steps}
        for step in self.steps:
            missing = set(step.depends_on) - names
            if missing:
                raise ValueError(f"Step '{step.name}' depends on non-existent step(s): {missing}")
        return self


class LLMProviderConfig(BaseModel):
    """Configuration for an LLM provider."""

    name: Literal["openai", "anthropic", "openrouter", "ollama", "mock"]
    api_key: Optional[str] = Field(default=None, description="API key for the provider")
    base_url: Optional[str] = Field(default=None, description="Custom base URL")
    timeout: int = Field(default=120, ge=1, le=600, description="Request timeout in seconds")
    max_retries: int = Field(default=3, ge=0, le=10, description="Maximum retry attempts")
    retry_delay: float = Field(default=1.0, ge=0, description="Delay between retries in seconds")
    rate_limit_rpm: Optional[int] = Field(
        default=None, description="Rate limit (requests per minute)"
    )
    model_mappings: Dict[str, str] = Field(default_factory=dict, description="Model name mappings")


class CacheConfig(BaseModel):
    """Configuration for caching."""

    enabled: bool = Field(default=True, description="Whether caching is enabled")
    backend: Literal["memory", "disk", "redis"] = Field(default="memory")
    ttl: int = Field(default=3600, ge=0, description="Cache TTL in seconds")
    max_size: int = Field(default=10000, ge=0, description="Maximum cache entries")
    directory: str = Field(default="./.autopipe_cache", description="Disk cache directory")
    redis_url: Optional[str] = Field(default=None, description="Redis connection URL")


class LoggingConfig(BaseModel):
    """Configuration for logging."""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(default="INFO")
    format: Literal["text", "json"] = Field(default="text")
    output: Literal["stdout", "stderr", "file"] = Field(default="stdout")
    file_path: Optional[str] = Field(default=None, description="Log file path")
    rotate: bool = Field(default=False, description="Rotate log files")
    max_bytes: int = Field(default=10485760, description="Max bytes before rotation")
    backup_count: int = Field(default=5, description="Number of backup files")


class MetricsConfig(BaseModel):
    """Configuration for metrics collection."""

    enabled: bool = Field(default=True, description="Whether metrics are enabled")
    prometheus_port: Optional[int] = Field(default=None, description="Prometheus metrics port")
    export_json: bool = Field(default=False, description="Export metrics to JSON file")
    json_path: Optional[str] = Field(default=None, description="JSON metrics output path")


class TracingConfig(BaseModel):
    """Configuration for distributed tracing."""

    enabled: bool = Field(default=False, description="Whether tracing is enabled")
    service_name: str = Field(default="autopipe", description="Service name for tracing")
    jaeger_endpoint: Optional[str] = Field(default=None, description="Jaeger endpoint")
    otel_endpoint: Optional[str] = Field(default=None, description="OpenTelemetry endpoint")
    sample_rate: float = Field(default=1.0, ge=0, le=1, description="Sampling rate")


class AutoPipeGlobalConfig(BaseModel):
    """Global AutoPipe configuration."""

    debug: bool = Field(default=False, description="Enable debug mode")
    version: str = Field(default="0.1.0", description="Configuration version")
    providers: List[LLMProviderConfig] = Field(default_factory=list)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    metrics: MetricsConfig = Field(default_factory=MetricsConfig)
    tracing: TracingConfig = Field(default_factory=TracingConfig)

    @model_validator(mode="after")
    def validate_provider_names_unique(self) -> "AutoPipeGlobalConfig":
        names = [p.name for p in self.providers]
        if len(names) != len(set(names)):
            from collections import Counter

            duplicates = [name for name, count in Counter(names).items() if count > 1]
            raise ValueError(f"Duplicate provider names found: {duplicates}")
        return self


class StepOutput(BaseModel):
    """Represents step execution output."""

    step_name: str = Field(..., description="Step name")
    status: Literal["pending", "running", "success", "failed", "skipped"] = Field(default="pending")
    output: Any = Field(default=None, description="Step output")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    start_time: Optional[float] = Field(default=None, description="Start timestamp")
    end_time: Optional[float] = Field(default=None, description="End timestamp")
    duration_ms: Optional[float] = Field(default=None, description="Execution duration in ms")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Step metrics")


class PipelineRunResult(BaseModel):
    """Represents a pipeline run result."""

    pipeline_name: str = Field(..., description="Pipeline name")
    run_id: str = Field(..., description="Unique run identifier")
    status: Literal["pending", "running", "success", "failed", "partial"] = Field(default="pending")
    steps: Dict[str, StepOutput] = Field(default_factory=dict, description="Step outputs")
    start_time: Optional[float] = Field(default=None, description="Start timestamp")
    end_time: Optional[float] = Field(default=None, description="End timestamp")
    duration_ms: Optional[float] = Field(default=None, description="Total duration in ms")
    error: Optional[str] = Field(default=None, description="Error message if failed")

    @property
    def successful_steps(self) -> List[str]:
        """Return names of successful steps."""
        return [name for name, output in self.steps.items() if output.status == "success"]

    @property
    def failed_steps(self) -> List[str]:
        """Return names of failed steps."""
        return [name for name, output in self.steps.items() if output.status == "failed"]
