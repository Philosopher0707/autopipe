"""Scheduling utilities for hyperparameter search."""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass
class ResourceStatus:
    """Resource status for scheduling."""

    cpu_available: float = 1.0
    memory_available_gb: float = 8.0
    gpu_available: int = 0
    gpu_memory_gb: float = 0.0
    queue_depth: int = 0
    avg_trial_runtime: float = 60.0  # seconds


class EarlyStoppingCallback:
    """Callback for early stopping in hyperparameter search."""

    def __init__(
        self,
        patience: int = 20,
        min_delta: float = 0.0,
        mode: str = "min",
        min_trials: int = 30,
    ):
        self.patience = patience
        self.min_delta = min_delta
        self.mode = mode
        self.min_trials = min_trials

        self.best_value = float("inf") if mode == "min" else float("-inf")
        self.counter = 0
        self.trial_count = 0

    def __call__(self, result: Any) -> bool:
        """Check if search should stop.

        Returns True if search should stop.
        """
        self.trial_count += 1

        if self.trial_count < self.min_trials:
            return False

        value = result.get("value", 0.0)

        improved = False
        if self.mode == "min":
            improved = value < self.best_value - self.min_delta
        else:
            improved = value > self.best_value + self.min_delta

        if improved:
            self.best_value = value
            self.counter = 0
            return False

        self.counter += 1
        return self.counter >= self.patience


class ResourceScheduler(ABC):
    """Abstract base class for resource-aware scheduling."""

    @abstractmethod
    def recommend_resource(self, trial_id: int, resource_status: ResourceStatus) -> Dict[str, Any]:
        """Recommend resource allocation for a trial."""

    @abstractmethod
    def update_load(self, trial_id: int, resource_usage: Dict[str, float]):
        """Update scheduler with actual resource usage."""


class AdaptiveScheduler(ResourceScheduler):
    """Adaptive resource scheduler based on trial history."""

    def __init__(
        self,
        initial_batch_size: int = 32,
        max_batch_size: int = 256,
        initial_lr: float = 0.001,
    ):
        self.initial_batch_size = initial_batch_size
        self.max_batch_size = max_batch_size
        self.initial_lr = initial_lr

        self.trial_metrics: Dict[int, Dict] = {}
        self.average_time = None
        self.average_accuracy = None

    def recommend_resource(self, trial_id: int, resource_status: ResourceStatus) -> Dict[str, Any]:
        """Recommend resources based on available capacity.

        Increases batch size when resources are available,
        adjusts learning rate accordingly.
        """
        if resource_status.gpu_available > 0:
            # GPU available - use larger batch sizes
            if self.average_time and self.average_time < resource_status.avg_trial_runtime * 0.8:
                batch_size = min(self.max_batch_size, self.initial_batch_size * 2)
            else:
                batch_size = self.initial_batch_size

            # Linear scaling rule for learning rate
            lr = self.initial_lr * (batch_size / self.initial_batch_size)

            return {
                "batch_size": batch_size,
                "learning_rate": min(lr, 0.1),  # Cap learning rate
                "device": "cuda",
            }

        # CPU-only training
        return {
            "batch_size": min(self.initial_batch_size, 64),
            "learning_rate": self.initial_lr,
            "device": "cpu",
        }

    def update_load(self, trial_id: int, resource_usage: Dict[str, float]):
        """Update metrics from completed trials."""
        self.trial_metrics[trial_id] = resource_usage

        # Update running averages
        if "time" in resource_usage:
            times = [m["time"] for m in self.trial_metrics.values() if "time" in m]
            if times:
                self.average_time = sum(times) / len(times)

        if "accuracy" in resource_usage:
            accuracies = [m["accuracy"] for m in self.trial_metrics.values() if "accuracy" in m]
            if accuracies:
                self.average_accuracy = sum(accuracies) / len(accuracies)


class PopulationBasedScheduler:
    """Population Based Training (PBT) scheduler.

    Evolutionary approach to hyperparameter optimization that
    exploits and explores during training.
    """

    def __init__(
        self,
        population_size: int = 25,
        exploit_fraction: float = 0.2,
        explore_factor: float = 0.2,
        resample_probability: float = 0.25,
        hyperparam_mutations: Optional[Dict[str, Tuple[float, float]]] = None,
    ):
        self.population_size = population_size
        self.exploit_fraction = exploit_fraction
        self.explore_factor = explore_factor
        self.resample_probability = resample_probability

        self.hyperparam_mutations = hyperparam_mutations or {
            "learning_rate": (0.1, 10.0),  # Multiply/divide by this range
        }

        self.population: Dict[int, Dict] = {}
        self.generation = 0

    def select_parent(self) -> int:
        """Select a parent from the bottom exploit_fraction for exploitation."""
        sorted_pop = sorted(
            self.population.items(), key=lambda x: x[1].get("performance", 0), reverse=True
        )

        cutoff = int(len(sorted_pop) * (1 - self.exploit_fraction))
        bottom_tier = sorted_pop[cutoff:]

        if not bottom_tier:
            return sorted_pop[0][0]

        # Sample from bottom tier
        import random

        return random.choice(bottom_tier)[0]

    def mutate_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Mutate hyperparameters for exploration."""
        import random

        import numpy as np

        new_params = params.copy()

        for param_name, (low, high) in self.hyperparam_mutations.items():
            if param_name in new_params:
                if random.random() < self.resample_probability:
                    # Resample from original space
                    original = new_params[param_name]
                    if isinstance(original, float):
                        scale = random.choice([low, high])
                        new_params[param_name] = original * scale
                else:
                    # Perturb by explore_factor
                    scale = np.exp(random.uniform(-self.explore_factor, self.explore_factor))
                    new_params[param_name] *= scale

        return new_params

    def update_population(
        self, member_id: int, params: Dict[str, Any], performance: float, checkpoint_ref: str
    ):
        """Update population with trial results."""
        self.population[member_id] = {
            "params": params,
            "performance": performance,
            "checkpoint": checkpoint_ref,
            "generation": self.generation,
        }

    def should_evolve(self) -> bool:
        """Check if population is ready for evolution."""
        return len(self.population) >= self.population_size

    def evolve(self):
        """Perform one evolution step."""
        if not self.should_evolve():
            return

        # Identify bottom performers to replace
        sorted_pop = sorted(
            self.population.items(), key=lambda x: x[1].get("performance", 0), reverse=True
        )

        cutoff = int(len(sorted_pop) * (1 - self.exploit_fraction))

        # Replace bottom with mutated top
        for member_id, _ in sorted_pop[cutoff:]:
            # Exploit: copy parameters from top performer
            _top_id, top_member = sorted_pop[0]
            new_params = self.mutate_params(top_member["params"])

            # Update member
            self.population[member_id] = {
                "params": new_params,
                "performance": None,
                "checkpoint": top_member["checkpoint"],
                "generation": self.generation + 1,
            }

        self.generation += 1

    def get_best_params(self) -> Optional[Dict[str, Any]]:
        """Get best parameters from population."""
        if not self.population:
            return None

        best_id = max(
            self.population.keys(),
            key=lambda k: self.population[k].get("performance", float("-inf")),
        )
        return self.population[best_id]["params"]


class TrialScheduler:
    """Schedule trials with priority and resource management."""

    def __init__(
        self,
        max_pending: int = 10,
        max_running: int = 4,
        priority_fn: Optional[Callable] = None,
    ):
        self.max_pending = max_pending
        self.max_running = max_running
        self.priority_fn = priority_fn or (lambda trial: trial.get("priority", 0))

        self.pending_trials: List[Dict] = []
        self.running_trials: Dict[int, Dict] = {}
        self.completed_trials: List[Dict] = []

    def submit(self, trial_config: Dict[str, Any], priority: int = 0):
        """Submit a trial to the scheduler."""
        trial_config = trial_config.copy()
        trial_config["priority"] = priority
        trial_config["submitted_at"] = time.time()

        # Insert in priority order
        idx = 0
        for i, t in enumerate(self.pending_trials):
            if self.priority_fn(t) < priority:
                idx = i
                break
            idx = i + 1

        self.pending_trials.insert(idx, trial_config)

    def can_schedule(self) -> bool:
        """Check if a new trial can be scheduled."""
        return len(self.pending_trials) > 0 and len(self.running_trials) < self.max_running

    def schedule_next(self) -> Optional[Dict]:
        """Get next trial to run."""
        if not self.can_schedule():
            return None

        trial = self.pending_trials.pop(0)
        trial_id = len(self.running_trials) + len(self.completed_trials)
        trial["trial_id"] = trial_id
        trial["started_at"] = time.time()

        self.running_trials[trial_id] = trial
        return trial

    def complete_trial(self, trial_id: int, result: Dict):
        """Mark a trial as complete."""
        if trial_id in self.running_trials:
            trial = self.running_trials.pop(trial_id)
            trial["completed_at"] = time.time()
            trial["result"] = result
            self.completed_trials.append(trial)

    def get_statistics(self) -> Dict[str, Any]:
        """Get scheduler statistics."""
        return {
            "pending": len(self.pending_trials),
            "running": len(self.running_trials),
            "completed": len(self.completed_trials),
            "total": len(self.pending_trials)
            + len(self.running_trials)
            + len(self.completed_trials),
        }
