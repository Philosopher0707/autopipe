"""Dashboard state — PipelineState dataclass and PipelineWatcher protocol."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol


class StepStatus(Enum):
    """Lifecycle state of a single step."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class StepState:
    """Mutable state for one pipeline step."""
    name: str
    status: StepStatus = StepStatus.PENDING
    output: Any = None
    error: Any = None
    start_time: float = 0.0
    end_time: float = 0.0

    @property
    def duration_seconds(self) -> float:
        if self.end_time and self.start_time:
            return self.end_time - self.start_time
        return 0.0


@dataclass
class PipelineState:
    """Shared mutable state for the pipeline + dashboard.

    Fields mirror wandb_tui.py RunState where applicable:
    - pipeline_name, state, elapsed_seconds, current_step, step_states
    - Metric histories (train_acc_hist, train_loss_hist, etc.)
    - System metric histories (cpu_pct_hist, gpu_pct_hist, etc.)
    """
    pipeline_name: str
    state: str = "pending"  # pending | running | completed | failed | paused
    elapsed_seconds: float = 0.0
    current_step: str | None = None
    step_states: dict[str, StepState] = field(default_factory=dict)
    pipeline_output: dict[str, Any] | None = None
    error: BaseException | None = None
    _start_time: float = field(default=0.0, repr=False)

    # Metric histories — populated as steps complete (simulated converging values)
    train_acc_hist: list = field(default_factory=list)
    train_loss_hist: list = field(default_factory=list)
    val_acc_hist: list = field(default_factory=list)
    val_loss_hist: list = field(default_factory=list)
    epoch_acc_hist: list = field(default_factory=list)
    epoch_loss_hist: list = field(default_factory=list)

    # System metrics — populated by _sample_system()
    cpu_pct_hist: list = field(default_factory=list)
    gpu_pct_hist: list = field(default_factory=list)
    gpu_temp_hist: list = field(default_factory=list)
    cpu_temp_hist: list = field(default_factory=list)
    cpu_power_hist: list = field(default_factory=list)
    disk_pct_hist: list = field(default_factory=list)

    @property
    def step_count(self) -> int:
        return sum(1 for s in self.step_states.values() if s.status == StepStatus.COMPLETED)

    def add_step(self, name: str) -> None:
        self.step_states[name] = StepState(name=name)

    def start_step(self, name: str) -> None:
        self.current_step = name
        self.step_states[name].status = StepStatus.RUNNING
        self.step_states[name].start_time = time.time()
        self.state = "running"

    def finish_step(self, name: str, output: Any = None) -> None:
        self.step_states[name].status = StepStatus.COMPLETED
        self.step_states[name].output = output
        self.step_states[name].end_time = time.time()
        self.current_step = None
        if all(s.status == StepStatus.COMPLETED for s in self.step_states.values()):
            self.state = "completed"
        elif self.state != "failed":
            self.state = "running"

    def fail_step(self, name: str, error: BaseException) -> None:
        self.step_states[name].status = StepStatus.FAILED
        self.step_states[name].error = error
        self.step_states[name].end_time = time.time()
        self.current_step = None
        self.state = "failed"
        self.error = error


class PipelineWatcher(Protocol):
    """Protocol for pipeline execution callbacks."""

    def before_pipeline(self, state: PipelineState) -> None:
        """Called once before any step runs."""
        ...

    def before_step(self, state: PipelineState, step_name: str) -> None:
        """Called before each step's run() method."""
        ...

    def after_step(self, state: PipelineState, step_name: str, output: Any) -> None:
        """Called after each step's run() method completes."""
        ...

    def after_pipeline(self, state: PipelineState) -> None:
        """Called once after all steps finish (success or failure)."""
        ...

    def on_error(self, state: PipelineState, step_name: str, error: BaseException) -> None:
        """Called when a step raises an exception."""
        ...
