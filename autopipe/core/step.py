"""Base Step class for pipeline steps."""
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

class Step(ABC):
    """Abstract base class for a pipeline step."""

    def __init__(self, name: str, depends_on: Optional[list[str]] = None):
        self.name = name
        self.depends_on = depends_on or []
        self.output = None
        self.metrics: Dict[str, Any] = {}

    def __repr__(self):
        return f"Step(name={self.name})"

    @abstractmethod
    def run(self, **kwargs) -> Any:
        """Execute the step logic.
        
        Returns:
            The output of this step, which will be passed to downstream steps.
        """

    def visualize(self, **kwargs):
        """Generate visualizations for this step.
        
        Subclasses can override to produce charts, graphs, etc.
        """

    def log_metrics(self, **metrics):
        """Log metrics for this step."""
        self.metrics.update(metrics)
        logger.info(f"Step {self.name} metrics: {metrics}")
