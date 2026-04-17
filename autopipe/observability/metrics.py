"""Metrics collection for AutoPipe."""
import time
from typing import Any, Dict, Optional
from dataclasses import dataclass, field
from collections import defaultdict
from pathlib import Path
import json

from prometheus_client import Counter, Histogram, Gauge, start_http_server, CollectorRegistry

from ..exceptions import ConfigurationError


@dataclass
class PipelineMetrics:
    """Metrics for a single pipeline run."""
    run_id: str
    pipeline_name: str
    start_time: float = 0.0
    end_time: Optional[float] = None
    step_durations: Dict[str, float] = field(default_factory=dict)
    step_metrics: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    
    @property
    def duration_ms(self) -> Optional[float]:
        """Total pipeline duration in milliseconds."""
        if self.end_time and self.start_time:
            return (self.end_time - self.start_time) * 1000
        return None


class MetricsCollector:
    """Collect and expose metrics."""

    def __init__(
        self,
        enabled: bool = True,
        prometheus_port: Optional[int] = None,
        export_json: bool = False,
        json_path: Optional[str] = None,
    ):
        self.enabled = enabled
        self.prometheus_port = prometheus_port
        self.export_json = export_json
        self.json_path = json_path
        self._registry = CollectorRegistry()
        self._metrics: Dict[str, PipelineMetrics] = {}
        self._initialized = False
        
        if enabled and prometheus_port:
            self._init_prometheus()

    def _init_prometheus(self) -> None:
        """Initialize Prometheus metrics."""
        if self._initialized:
            return
            
        self._pipeline_runs = Counter(
            "autopipe_pipeline_runs_total",
            "Total pipeline runs",
            ["pipeline_name", "status"],
            registry=self._registry,
        )
        self._pipeline_duration = Histogram(
            "autopipe_pipeline_duration_seconds",
            "Pipeline execution duration",
            ["pipeline_name"],
            registry=self._registry,
        )
        self._step_duration = Histogram(
            "autopipe_step_duration_seconds",
            "Step execution duration",
            ["pipeline_name", "step_name"],
            registry=self._registry,
        )
        self._step_runs = Counter(
            "autopipe_step_runs_total",
            "Total step runs",
            ["pipeline_name", "step_name", "status"],
            registry=self._registry,
        )
        self._active_runs = Gauge(
            "autopipe_active_runs",
            "Number of active pipeline runs",
            ["pipeline_name"],
            registry=self._registry,
        )
        
        if self.prometheus_port:
            start_http_server(self.prometheus_port, registry=self._registry)
        
        self._initialized = True

    def start_run(self, run_id: str, pipeline_name: str) -> PipelineMetrics:
        """Start collecting metrics for a pipeline run."""
        metrics = PipelineMetrics(
            run_id=run_id,
            pipeline_name=pipeline_name,
            start_time=time.perf_counter(),
        )
        self._metrics[run_id] = metrics
        
        if self.enabled and self._initialized:
            self._active_runs.labels(pipeline_name=pipeline_name).inc()
        
        return metrics

    def end_run(
        self,
        run_id: str,
        status: str = "success",
        error: Optional[str] = None,
    ) -> None:
        """End metrics collection for a pipeline run."""
        metrics = self._metrics.get(run_id)
        if not metrics:
            return
            
        metrics.end_time = time.perf_counter()
        if error:
            metrics.errors.append(error)
        
        duration = metrics.duration_ms
        
        if self.enabled and self._initialized:
            self._active_runs.labels(pipeline_name=metrics.pipeline_name).dec()
            self._pipeline_runs.labels(
                pipeline_name=metrics.pipeline_name, status=status
            ).inc()
            if duration:
                self._pipeline_duration.labels(
                    pipeline_name=metrics.pipeline_name
                ).observe(duration / 1000)
        
        if self.export_json and self.json_path:
            self._export_to_json()

    def record_step_start(self, run_id: str, step_name: str) -> None:
        """Record step start time."""
        metrics = self._metrics.get(run_id)
        if metrics:
            metrics.step_metrics[step_name] = {"start_time": time.perf_counter()}

    def record_step_end(
        self,
        run_id: str,
        step_name: str,
        status: str = "success",
        error: Optional[str] = None,
    ) -> None:
        """Record step completion."""
        metrics = self._metrics.get(run_id)
        if not metrics:
            return
            
        step_data = metrics.step_metrics.get(step_name, {})
        start_time = step_data.get("start_time")
        
        if start_time:
            duration = (time.perf_counter() - start_time) * 1000
            metrics.step_durations[step_name] = duration
            
            if self.enabled and self._initialized:
                self._step_duration.labels(
                    pipeline_name=metrics.pipeline_name, step_name=step_name
                ).observe(duration / 1000)
                self._step_runs.labels(
                    pipeline_name=metrics.pipeline_name,
                    step_name=step_name,
                    status=status,
                ).inc()
        
        if error:
            step_data["error"] = error

    def add_step_metric(
        self, run_id: str, step_name: str, key: str, value: Any
    ) -> None:
        """Add a custom metric for a step."""
        metrics = self._metrics.get(run_id)
        if metrics:
            step_data = metrics.step_metrics.get(step_name, {})
            step_data[key] = value

    def get_metrics(self, run_id: str) -> Optional[PipelineMetrics]:
        """Get metrics for a run."""
        return self._metrics.get(run_id)

    def _export_to_json(self) -> None:
        """Export all metrics to JSON file."""
        if not self.json_path:
            return
            
        data = []
        for metrics in self._metrics.values():
            data.append({
                "run_id": metrics.run_id,
                "pipeline_name": metrics.pipeline_name,
                "start_time": metrics.start_time,
                "end_time": metrics.end_time,
                "duration_ms": metrics.duration_ms,
                "step_durations": metrics.step_durations,
                "step_metrics": metrics.step_metrics,
                "errors": metrics.errors,
            })
        
        Path(self.json_path).parent.mkdir(parents=True, exist_ok=True)
        with open(self.json_path, "w") as f:
            json.dump(data, f, indent=2)

    def clear(self) -> None:
        """Clear all collected metrics."""
        self._metrics.clear()


# Global metrics collector instance
_metrics_collector: Optional[MetricsCollector] = None


def init_metrics(
    enabled: bool = True,
    prometheus_port: Optional[int] = None,
    export_json: bool = False,
    json_path: Optional[str] = None,
) -> MetricsCollector:
    """Initialize the global metrics collector."""
    global _metrics_collector
    _metrics_collector = MetricsCollector(
        enabled=enabled,
        prometheus_port=prometheus_port,
        export_json=export_json,
        json_path=json_path,
    )
    return _metrics_collector


def get_metrics_collector() -> Optional[MetricsCollector]:
    """Get the global metrics collector."""
    return _metrics_collector
