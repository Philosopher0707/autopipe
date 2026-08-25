"""Base classes for experiment tracking."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

if TYPE_CHECKING:
    import pandas as pd


@dataclass
class Run:
    """Single experiment run representation."""

    run_id: str
    experiment_id: str
    run_name: Optional[str] = None
    status: str = "RUNNING"
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    params: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, List[float]] = field(default_factory=dict)
    tags: Dict[str, str] = field(default_factory=dict)
    artifacts: List[str] = field(default_factory=list)

    def __post_init__(self):
        if self.start_time is None:
            self.start_time = datetime.now()

    def log_param(self, key: str, value: Any):
        """Log a parameter."""
        self.params[key] = value

    def log_params(self, params: Dict[str, Any]):
        """Log multiple parameters."""
        self.params.update(params)

    def log_metric(self, key: str, value: float, step: Optional[int] = None):
        """Log a metric at a specific step."""
        if key not in self.metrics:
            self.metrics[key] = []

        entry = {"value": value, "step": step, "timestamp": datetime.now()}
        self.metrics[key].append(entry)

    def log_metrics(self, metrics: Dict[str, float], step: Optional[int] = None):
        """Log multiple metrics."""
        for key, value in metrics.items():
            self.log_metric(key, value, step)

    def set_tag(self, key: str, value: str):
        """Set a tag."""
        self.tags[key] = value

    def get_tags(self) -> Dict[str, str]:
        """Get all tags."""
        return self.tags.copy()

    def finish(self):
        """Mark run as finished."""
        self.status = "FINISHED"
        self.end_time = datetime.now()

    def to_dict(self) -> Dict:
        """Convert run to dictionary."""
        return {
            "run_id": self.run_id,
            "experiment_id": self.experiment_id,
            "run_name": self.run_name,
            "status": self.status,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "params": self.params,
            "metrics": {k: [m["value"] for m in v] for k, v in self.metrics.items()},
            "tags": self.tags,
            "artifacts": self.artifacts,
        }


@dataclass
class Experiment:
    """Experiment representation."""

    experiment_id: str
    name: str
    artifact_location: Optional[str] = None
    tags: Dict[str, str] = field(default_factory=dict)
    created_time: Optional[datetime] = None

    def __post_init__(self):
        if self.created_time is None:
            self.created_time = datetime.now()

    def to_dict(self) -> Dict:
        """Convert experiment to dictionary."""
        return {
            "experiment_id": self.experiment_id,
            "name": self.name,
            "artifact_location": self.artifact_location,
            "tags": self.tags,
            "created_time": self.created_time.isoformat() if self.created_time else None,
        }


class BaseTracker(ABC):
    """Abstract base class for experiment trackers."""

    def __init__(self, experiment_name: str = "default", **kwargs):
        self.experiment_name = experiment_name
        self.experiment_id: Optional[str] = None
        self.current_run: Optional[Run] = None
        self.runs: List[Run] = []
        self.metadata: Dict[str, Any] = {}

    @abstractmethod
    def start_run(
        self,
        run_id: Optional[str] = None,
        run_name: Optional[str] = None,
        nested: bool = False,
        tags: Optional[Dict[str, str]] = None,
    ) -> Run:
        """Start a new run."""

    @abstractmethod
    def end_run(self, status: str = "FINISHED"):
        """End the current run."""

    @abstractmethod
    def log_param(self, key: str, value: Any):
        """Log a parameter."""

    @abstractmethod
    def log_params(self, params: Dict[str, Any]):
        """Log multiple parameters."""

    @abstractmethod
    def log_metric(self, key: str, value: float, step: Optional[int] = None):
        """Log a metric."""

    @abstractmethod
    def log_metrics(self, metrics: Dict[str, float], step: Optional[int] = None):
        """Log multiple metrics."""

    @abstractmethod
    def set_tag(self, key: str, value: str):
        """Set a tag."""

    @abstractmethod
    def log_artifact(self, local_path: str, artifact_path: Optional[str] = None):
        """Log an artifact."""

    @abstractmethod
    def log_artifacts(self, local_dir: str, artifact_path: Optional[str] = None):
        """Log all artifacts from a directory."""

    @abstractmethod
    def log_model(self, model: Any, artifact_path: str, **kwargs):
        """Log a model."""

    @abstractmethod
    def get_run(self, run_id: str) -> Optional[Run]:
        """Get a run by ID."""

    @abstractmethod
    def search_runs(
        self,
        experiment_ids: Optional[List[str]] = None,
        filter_string: str = "",
        run_view_type: str = "ACTIVE_ONLY",
        max_results: int = 1000,
        order_by: Optional[List[str]] = None,
    ) -> List[Run]:
        """Search for runs."""

    def log_system_metrics(self):
        """Log system metrics (GPU, CPU, memory)."""
        import platform

        import psutil

        self.log_params(
            {
                "system_platform": platform.platform(),
                "system_processor": platform.processor(),
                "system_cores": psutil.cpu_count(),
                "system_memory_gb": psutil.virtual_memory().total / (1024**3),
            }
        )

        # Log GPU info if available
        try:
            import GPUtil

            gpus = GPUtil.getGPUs()
            for i, gpu in enumerate(gpus):
                self.log_params(
                    {
                        f"gpu_{i}_name": gpu.name,
                        f"gpu_{i}_memory_mb": gpu.memoryTotal,
                    }
                )
        except ImportError:
            pass

    def log_text(self, text: str, artifact_file: str):
        """Log text as an artifact."""

    def log_dict(self, dictionary: Dict, artifact_file: str):
        """Log a dictionary as an artifact."""

    def log_figure(self, figure: Any, artifact_file: str):
        """Log a matplotlib figure."""

    def log_image(self, image: Any, artifact_file: str):
        """Log an image."""

    def log_table(
        self,
        data: Union[Dict, "pd.DataFrame"],
        artifact_file: str,
    ):
        """Log a table."""


class LocalTracker(BaseTracker):
    """Simple local experiment tracker.

    Stores experiments in memory with optional persistence.
    """

    def __init__(
        self,
        experiment_name: str = "default",
        artifact_dir: str = "./.autopipe_artifacts",
        **kwargs,
    ):
        super().__init__(experiment_name, **kwargs)
        self.artifact_dir = artifact_dir
        import os

        os.makedirs(artifact_dir, exist_ok=True)

        # Create experiment
        self.experiment_id = self._generate_id()
        self.experiments: Dict[str, Experiment] = {
            self.experiment_id: Experiment(
                experiment_id=self.experiment_id,
                name=experiment_name,
                artifact_location=artifact_dir,
            )
        }

    def _generate_id(self) -> str:
        """Generate unique ID."""
        import uuid

        return str(uuid.uuid4())

    def start_run(
        self,
        run_id: Optional[str] = None,
        run_name: Optional[str] = None,
        nested: bool = False,
        tags: Optional[Dict[str, str]] = None,
    ) -> Run:
        """Start a new run."""
        if run_id is None:
            run_id = self._generate_id()

        if self.current_run is not None and not nested:
            self.end_run()

        run = Run(
            run_id=run_id,
            experiment_id=self.experiment_id,
            run_name=run_name or f"run_{len(self.runs)}",
            tags=tags or {},
        )

        self.current_run = run
        self.runs.append(run)
        return run

    def end_run(self, status: str = "FINISHED"):
        """End the current run."""
        if self.current_run:
            self.current_run.status = status
            self.current_run.finish()
            self.current_run = None

    def log_param(self, key: str, value: Any):
        """Log a parameter."""
        if self.current_run:
            self.current_run.log_param(key, value)

    def log_params(self, params: Dict[str, Any]):
        """Log multiple parameters."""
        if self.current_run:
            self.current_run.log_params(params)

    def log_metric(self, key: str, value: float, step: Optional[int] = None):
        """Log a metric."""
        if self.current_run:
            self.current_run.log_metric(key, value, step)

    def log_metrics(self, metrics: Dict[str, float], step: Optional[int] = None):
        """Log multiple metrics."""
        if self.current_run:
            self.current_run.log_metrics(metrics, step)

    def set_tag(self, key: str, value: str):
        """Set a tag."""
        if self.current_run:
            self.current_run.set_tag(key, value)

    def log_artifact(self, local_path: str, artifact_path: Optional[str] = None):
        """Log an artifact."""
        import os
        import shutil

        if self.current_run:
            dest_dir = os.path.join(self.artifact_dir, self.current_run.run_id, artifact_path or "")
            os.makedirs(dest_dir, exist_ok=True)

            if os.path.isfile(local_path):
                shutil.copy(local_path, dest_dir)
            else:
                shutil.copytree(local_path, dest_dir, dirs_exist_ok=True)

            self.current_run.artifacts.append(local_path)

    def log_artifacts(self, local_dir: str, artifact_path: Optional[str] = None):
        """Log all artifacts from a directory."""
        import os

        if os.path.isdir(local_dir):
            for root, _dirs, files in os.walk(local_dir):
                for file in files:
                    full_path = os.path.join(root, file)
                    self.log_artifact(full_path, artifact_path)

    def log_model(self, model: Any, artifact_path: str, **kwargs):
        """Log a model."""

    def get_run(self, run_id: str) -> Optional[Run]:
        """Get a run by ID."""
        for run in self.runs:
            if run.run_id == run_id:
                return run
        return None

    def search_runs(
        self,
        experiment_ids: Optional[List[str]] = None,
        filter_string: str = "",
        run_view_type: str = "ACTIVE_ONLY",
        max_results: int = 1000,
        order_by: Optional[List[str]] = None,
    ) -> List[Run]:
        """Search for runs."""
        if run_view_type == "ACTIVE_ONLY":
            return [r for r in self.runs if r.status == "RUNNING"][:max_results]

        return self.runs[:max_results]
