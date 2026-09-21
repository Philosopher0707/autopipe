"""Base Step class for pipeline steps."""

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .execution import CancellationToken

logger = logging.getLogger(__name__)


class Step(ABC):
    """Abstract base class for a pipeline step."""

    def __init__(self, name: str, depends_on: Optional[list[str]] = None) -> None:
        self.name = name
        self.depends_on = depends_on or []
        self.output: Any = None
        self.metrics: Dict[str, Any] = {}
        # Named input bindings (param -> upstream step), set by the loader
        # when a step declares `inputs:` in config; empty means legacy behavior.
        self.input_bindings: Dict[str, str] = {}
        # Set by the execution engine before invocation so that long-running
        # steps can cooperatively abort mid-step. Deliberately an attribute
        # rather than a run() kwarg: run() kwargs are a duck-typed data bag, so
        # a control object there would corrupt input semantics.
        self.cancellation_token: Optional[CancellationToken] = None

    def __repr__(self) -> str:
        return f"Step(name={self.name})"

    @abstractmethod
    def run(self, **kwargs: Any) -> Any:
        """Execute the step logic.

        Returns:
            The output of this step, which will be passed to downstream steps.
        """

    def visualize(self, **kwargs: Any) -> None:
        """Generate visualizations for this step.

        Subclasses can override to produce charts, graphs, etc.
        """

    def log_metrics(self, **metrics: Any) -> None:
        """Log metrics for this step."""
        self.metrics.update(metrics)
        logger.info("Step %s metrics: %s", self.name, metrics)
