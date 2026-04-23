"""Distributed and parallel hyperparameter search."""

import os
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Type

from autopipe.core.step import Step
from autopipe.exceptions import PipelineError


@dataclass
class DistributedConfig:
    """Configuration for distributed search."""
    backend: str = "multiprocessing"  # multiprocessing, thread, ray, kubernetes
    n_workers: int = 4
    resources_per_worker: Dict[str, Any] = field(default_factory=dict)
    timeout_per_trial: Optional[int] = None
    retry_on_failure: bool = True
    max_retries: int = 3
    early_stop_fn: Optional[Callable] = None


class DistributedSearch:
    """Distributed hyperparameter search across multiple workers.
    
    Supports multiple backends:
    - multiprocessing: Local process pool
    - thread: Local thread pool (for I/O bound tasks)
    - ray: Ray Tune distributed cluster
    - kubernetes: Kubernetes cluster scaling
    """

    def __init__(
        self,
        search_step_class: Type[Step],
        config: Optional[DistributedConfig] = None,
        search_kwargs: Optional[Dict] = None,
    ):
        self.search_step_class = search_step_class
        self.config = config or DistributedConfig()
        self.search_kwargs = search_kwargs or {}

        self.results: List[Dict] = []
        self.errors: List[Dict] = []

    def _trial_worker(
        self,
        trial_config: Dict[str, Any],
        worker_id: int
    ) -> Dict:
        """Worker function for a single trial."""
        trial_id = trial_config.get("trial_id", 0)

        try:
            # Set environment for this worker
            os.environ["AUTOPYPE_WORKER_ID"] = str(worker_id)

            # Run the search step
            step = self.search_step_class(**self.search_kwargs)

            # Execute with subset of data
            result = step.execute(
                train_data=trial_config.get("train_data"),
                val_data=trial_config.get("val_data"),
            )

            return {
                "trial_id": trial_id,
                "worker_id": worker_id,
                "status": "success",
                "result": result,
                "runtime": time.time() - trial_config.get("start_time", time.time()),
            }

        except Exception as e:
            return {
                "trial_id": trial_id,
                "worker_id": worker_id,
                "status": "failed",
                "error": str(e),
                "error_type": type(e).__name__,
            }

    def run_multiprocessing(
        self,
        trial_configs: List[Dict[str, Any]],
    ) -> List[Dict]:
        """Run trials using multiprocessing."""
        n_workers = min(self.config.n_workers, len(trial_configs))
        results = []

        with ProcessPoolExecutor(max_workers=n_workers) as executor:
            # Submit all trials
            futures = {
                executor.submit(self._trial_worker, config, i): config
                for i, config in enumerate(trial_configs)
            }

            # Collect results with timeout
            for future in as_completed(futures):
                config = futures[future]
                try:
                    if self.config.timeout_per_trial:
                        result = future.result(timeout=self.config.timeout_per_trial)
                    else:
                        result = future.result()
                    results.append(result)
                except TimeoutError:
                    results.append({
                        "trial_id": config.get("trial_id"),
                        "status": "timeout",
                        "error": f"Trial exceeded {self.config.timeout_per_trial}s",
                    })
                    future.cancel()
                except Exception as e:
                    results.append({
                        "trial_id": config.get("trial_id"),
                        "status": "error",
                        "error": str(e),
                    })

        return results

    def run_threadpool(
        self,
        trial_configs: List[Dict[str, Any]],
    ) -> List[Dict]:
        """Run trials using thread pool (for I/O bound)."""
        n_workers = min(self.config.n_workers, len(trial_configs))
        results = []

        with ThreadPoolExecutor(max_workers=n_workers) as executor:
            futures = {
                executor.submit(self._trial_worker, config, i): config
                for i, config in enumerate(trial_configs)
            }

            for future in as_completed(futures):
                try:
                    result = future.result(timeout=self.config.timeout_per_trial)
                    results.append(result)
                except Exception as e:
                    results.append({
                        "status": "error",
                        "error": str(e),
                    })

        return results

    def run_ray(
        self,
        trial_configs: List[Dict[str, Any]],
    ) -> List[Dict]:
        """Run trials using Ray Tune."""
        try:
            import ray
            from ray import tune
            from ray.tune.schedulers import ASHAScheduler
        except ImportError:
            raise PipelineError(
                "Ray is required for distributed search. Install with: pip install ray[tune]"
            )

        if not ray.is_initialized():
            ray.init(ignore_reinit_error=True)

        # Convert configs to Ray Tune format
        search_space = self._get_search_space_from_configs(trial_configs)

        # Define objective wrapper
        def objective(config):
            trial_config = config.copy()
            result = self._trial_worker(trial_config, ray.get_runtime_context().get_worker_id())
            tune.report(**{
                k: v for k, v in result.get("result", {}).items()
                if isinstance(v, (int, float))
            })

        # Run with ASHA scheduling
        scheduler = ASHAScheduler(
            metric="accuracy",
            mode="max",
            max_t=100,
            grace_period=10,
            reduction_factor=2,
        )

        analysis = tune.run(
            objective,
            config=search_space,
            num_samples=len(trial_configs),
            scheduler=scheduler,
            resources_per_trial=self.config.resources_per_worker,
            verbose=1,
        )

        # Convert results
        results = []
        for trial in analysis.trials:
            results.append({
                "trial_id": trial.trial_id,
                "status": trial.status,
                "config": trial.config,
                "last_result": trial.last_result,
            })

        return results

    def _get_search_space_from_configs(self, configs: List[Dict]) -> Dict:
        """Extract search space from trial configs."""
        if not configs:
            return {}

        # Use first config to infer structure
        # This is simplified - real implementation would be more robust
        search_space = configs[0].get("search_space", {})
        return search_space

    def run(
        self,
        trial_configs: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Execute distributed search."""

        if self.config.backend == "multiprocessing":
            results = self.run_multiprocessing(trial_configs)
        elif self.config.backend == "thread":
            results = self.run_threadpool(trial_configs)
        elif self.config.backend == "ray":
            results = self.run_ray(trial_configs)
        else:
            raise PipelineError(f"Unknown backend: {self.config.backend}")

        # Aggregate results
        successful = [r for r in results if r.get("status") == "success"]
        failed = [r for r in results if r.get("status") != "success"]

        return {
            "results": results,
            "successful_trials": len(successful),
            "failed_trials": len(failed),
            "success_rate": len(successful) / len(results) if results else 0.0,
            "best_result": max(
                successful,
                key=lambda x: x.get("result", {}).get("best_value", float('-inf')),
                default=None
            ),
        }


class ParallelSearch:
    """Parallel search for faster hyperparameter optimization.
    
    Uses multiple strategies:
    - Asynchronous parallel evaluation
    - Successive halving / Hyperband
    - Population-based training
    """

    def __init__(
        self,
        initial_population: int = 64,
        reduction_factor: int = 4,
        min_resource: int = 1,
        max_resource: str = "auto",
    ):
        self.initial_population = initial_population
        self.reduction_factor = reduction_factor
        self.min_resource = min_resource
        self.max_resource = max_resource

        self.active_configs: Dict[int, Dict] = {}
        self.completed_configs: List[Dict] = []

    def successive_halving(
        self,
        configs: List[Dict],
        evaluate_fn: Callable[[Dict], float],
    ) -> Dict:
        """Run successive halving algorithm.
        
        Trains multiple configurations with minimal resources,
        eliminates worst performers, and continues with top.
        """
        n_configs = len(configs)
        n_rounds = int(_log(n_configs, self.reduction_factor))

        active = configs.copy()

        for round_idx in range(n_rounds):
            # Calculate resources for this round
            resources = self.min_resource * (self.reduction_factor ** round_idx)

            # Evaluate all active configs
            scores = []
            for config in active:
                config["resources"] = resources
                score = evaluate_fn(config)
                scores.append((config, score))

            # Sort by score
            scores.sort(key=lambda x: x[1], reverse=True)

            # Keep top 1/reduction_factor
            n_to_keep = len(active) // self.reduction_factor
            active = [c for c, s in scores[:n_to_keep]]

            if len(active) == 1:
                break

        # Return best config
        return active[0] if active else configs[0]

    def hyperband(
        self,
        config_generator: Callable[[], Dict],
        evaluate_fn: Callable[[Dict], Dict],
        max_resource: int = 81,
        eta: int = 3,
    ) -> Dict:
        """Run Hyperband algorithm.
        
        More efficient than pure successive halving by trying
        different tradeoffs between number of configs and resources.
        """
        max_iter = _log(max_resource, eta)

        best_config = None
        best_score = float('-inf')

        for s in range(max_iter):
            # Number of configs
            n = int((max_resource / max_resource) * ((eta ** max_iter) / (s + 1)))
            r = max_resource * (eta ** (-s))

            # Successive halving with (n, r)
            configs = [config_generator() for _ in range(n)]
            result = self.successive_halving_with_budget(
                configs, evaluate_fn, r, eta
            )

            if result["score"] > best_score:
                best_score = result["score"]
                best_config = result["config"]

        return {
            "best_config": best_config,
            "best_score": best_score,
        }

    def successive_halving_with_budget(
        self,
        configs: List[Dict],
        evaluate_fn: Callable,
        max_resources: float,
        eta: int,
    ) -> Dict:
        """Successive halving with specified max resources."""
        active = configs.copy()

        while len(active) > 1:
            resources = max_resources / (eta ** (len(active) - 1))

            scores = []
            for config in active:
                config["resources"] = resources
                result = evaluate_fn(config)
                scores.append((config, result.get("score", 0)))

            scores.sort(key=lambda x: x[1], reverse=True)
            n_keep = len(active) // eta
            active = [c for c, s in scores[:n_keep]]

        return {
            "config": active[0] if active else configs[0],
            "score": scores[0][1] if scores else 0,
        }


def _log(x: float, base: int) -> int:
    """Compute log with integer result."""
    import math
    return int(math.log(x) / math.log(base))


class KubernetesDistributedSearch:
    """Distributed search on Kubernetes cluster."""

    def __init__(
        self,
        namespace: str = "default",
        image: str = "autopipe:latest",
        n_workers: int = 4,
        resources: Optional[Dict] = None,
    ):
        self.namespace = namespace
        self.image = image
        self.n_workers = n_workers
        self.resources = resources or {
            "requests": {"cpu": "2", "memory": "4Gi"},
            "limits": {"cpu": "4", "memory": "8Gi"},
        }

    def deploy_workers(self, trial_configs: List[Dict]):
        """Deploy worker pods for each trial."""
        try:
            from kubernetes import client, config
        except ImportError:
            raise PipelineError("kubernetes package required. Install with: pip install kubernetes")

        config.load_kube_config()

        v1 = client.CoreV1Api()

        for i, trial_config in enumerate(trial_configs):
            job_name = f"autopipe-trial-{i}"

            # Create pod spec
            container = client.V1Container(
                name="trial-worker",
                image=self.image,
                resources=client.V1ResourceRequirements(
                    requests=self.resources["requests"],
                    limits=self.resources["limits"],
                ),
                env=[
                    client.V1EnvVar(name="TRIAL_CONFIG", value=str(trial_config)),
                    client.V1EnvVar(name="WORKER_ID", value=str(i)),
                ],
            )

            template = client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(name=job_name),
                spec=client.V1PodSpec(
                    containers=[container],
                    restart_policy="Never",
                ),
            )

            # Submit job
            v1.create_namespaced_pod(
                namespace=self.namespace,
                body=template,
            )

    def collect_results(self) -> List[Dict]:
        """Collect results from completed worker pods."""
        # Implementation would watch for pod completions
        # and collect results from logs or shared storage
        raise NotImplementedError("Kubernetes result collection not yet implemented")


class GridSearchParallel:
    """Parallel grid search implementation."""

    def __init__(
        self,
        param_grid: Dict[str, List],
        n_workers: int = 4,
    ):
        self.param_grid = param_grid
        self.n_workers = n_workers

        # Generate all combinations
        from itertools import product
        keys = list(param_grid.keys())
        values = [param_grid[k] for k in keys]

        self.combinations = [
            dict(zip(keys, combo))
            for combo in product(*values)
        ]

    def search(
        self,
        evaluate_fn: Callable[[Dict], float],
    ) -> Dict:
        """Run parallel grid search."""
        best_score = float('-inf')
        best_config = None
        all_results = []

        with ProcessPoolExecutor(max_workers=self.n_workers) as executor:
            futures = {
                executor.submit(evaluate_fn, config): config
                for config in self.combinations
            }

            for future in as_completed(futures):
                config = futures[future]
                try:
                    score = future.result()
                    all_results.append({"config": config, "score": score})

                    if score > best_score:
                        best_score = score
                        best_config = config

                except Exception as e:
                    all_results.append({"config": config, "error": str(e)})

        return {
            "best_config": best_config,
            "best_score": best_score,
            "all_results": all_results,
            "n_evaluations": len(self.combinations),
        }
