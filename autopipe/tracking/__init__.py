"""AutoPipe Tracking Module.

Run/experiment tracking abstractions and a local in-memory tracker.
MLflow/W&B integrations are planned; see ROADMAP.md.
"""

from .base import BaseTracker, Experiment, LocalTracker, Run

__all__ = [
    "BaseTracker",
    "Experiment",
    "LocalTracker",
    "Run",
]
