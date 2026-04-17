"""AutoPipe Experiment Tracking Module.

World-class experiment tracking for ML/DL experiments.
Supports MLflow, Weights & Biases, and custom trackers.
"""

from .base import BaseTracker, Run, Experiment
from .mlflow_tracker import MLflowTracker
from .wandb_tracker import WandbTracker
from .composite_tracker import CompositeTracker
from .artifacts import Artifact, ArtifactRegistry, ModelArtifact, DatasetArtifact
from .registry import ModelRegistry, ExperimentRegistry

__all__ = [
    "BaseTracker",
    "Run",
    "Experiment",
    "MLflowTracker",
    "WandbTracker",
    "CompositeTracker",
    "Artifact",
    "ArtifactRegistry",
    "ModelArtifact",
    "DatasetArtifact",
    "ModelRegistry",
    "ExperimentRegistry",
]