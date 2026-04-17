"""Optuna-based hyperparameter search for AutoPipe."""

from typing import Any, Callable, Dict, List, Optional, Tuple, Union
import time
from dataclasses import dataclass, field
import numpy as np

from autopipe.core.step import Step
from autopipe.exceptions import PipelineError
from .search_space import SearchSpace


@dataclass
class TrialResult:
    """Result from a single trial."""
    trial_id: int
    params: Dict[str, Any]
    value: float
    objective_values: Dict[str, float] = field(default_factory=dict)
    runtime: float = 0.0
    state: str = "COMPLETE"
    user_attrs: Dict[str, Any] = field(default_factory=dict)
    intermediate_values: List[float] = field(default_factory=list)


@dataclass
class OptunaPruner:
    """Pruning strategy for early stopping."""
    n_warmup_steps: int = 5
    n_startup_trials: int = 10
    min_resource: int = 1
    reduction_factor: float = 3.0
    pruner_type: str = "median"  # median, percentile, hyperband
    
    def get_optuna_pruner(self):
        """Get Optuna pruner instance."""
        try:
            import optuna
        except ImportError:
            raise PipelineError("Optuna is required for hyperparameter tuning")
        
        if self.pruner_type == "median":
            return optuna.pruners.MedianPruner(
                n_startup_trials=self.n_startup_trials,
                n_warmup_steps=self.n_warmup_steps,
                interval_steps=1,
            )
        elif self.pruner_type == "percentile":
            return optuna.pruners.PercentilePruner(
                percentile=25.0,
                n_startup_trials=self.n_startup_trials,
                n_warmup_steps=self.n_warmup_steps,
            )
        elif self.pruner_type == "hyperband":
            return optuna.pruners.HyperbandPruner(
                min_resource=self.min_resource,
                max_resource="auto",
                reduction_factor=self.reduction_factor,
            )
        else:
            return optuna.pruners.MedianPruner()


class OptunaSearchStep(Step):
    """World-class Optuna-based hyperparameter search step.
    
    Features:
    - TPE (Tree-structured Parzen Estimator) sampler
    - CMA-ES sampler for continuous optimization
    - Multi-objective optimization
    - Pruning with early stopping
    - Distributed optimization
    - Human-readable parameter importances
    - Parallel coordinate plots
    - Hyperparameter importance analysis
    """
    
    def __init__(
        self,
        name: str = "optuna_search",
        search_space: Optional[SearchSpace] = None,
        objective: Union[str, List[str]] = "accuracy",
        direction: Union[str, List[str]] = "maximize",
        n_trials: int = 100,
        timeout: Optional[int] = None,
        sampler: str = "tpe",
        sampler_params: Optional[Dict] = None,
        pruner: Optional[OptunaPruner] = None,
        study_name: Optional[str] = None,
        storage: Optional[str] = None,
        load_if_exists: bool = True,
        n_jobs: int = 1,
        seed: int = 42,
        show_progress_bar: bool = True,
        # AutoPipe specific
        evaluator_class = None,
        evaluator_kwargs: Optional[Dict] = None,
    ):
        """Initialize Optuna search step.
        
        Args:
            name: Step name
            search_space: Parameter search space
            objective: Metric(s) to optimize
            direction: "maximize" or "minimize" (can be list for multi-objective)
            n_trials: Number of optimization trials
            timeout: Max time in seconds
            sampler: "tpe", "cmaes", "random", "nsga2", "nsga3"
            sampler_params: Additional sampler parameters
            pruner: Pruning configuration
            study_name: Study name for persistence
            storage: Database URL for distributed optimization
            load_if_exists: Load existing study if present
            n_jobs: Number of parallel workers
            seed: Random seed
            show_progress_bar: Show optimization progress
            evaluator_class: Class that evaluates a trial (must implement `evaluate`)
            evaluator_kwargs: Additional kwargs for evaluator
        """
        super().__init__(name=name)
        self.search_space = search_space or SearchSpace()
        self.objective = [objective] if isinstance(objective, str) else objective
        self.direction = [direction] if isinstance(direction, str) else direction
        self.n_trials = n_trials
        self.timeout = timeout
        self.sampler = sampler
        self.sampler_params = sampler_params or {}
        self.pruner = pruner or OptunaPruner()
        self.study_name = study_name or f"autopipe_study_{int(time.time())}"
        self.storage = storage
        self.load_if_exists = load_if_exists
        self.n_jobs = n_jobs
        self.seed = seed
        self.show_progress_bar = show_progress_bar
        
        self.evaluator_class = evaluator_class
        self.evaluator_kwargs = evaluator_kwargs or {}
        
        self.study = None
        self.trial_results: List[TrialResult] = []
        self.best_trial = None
        
    def _get_sampler(self, optuna):
        """Create Optuna sampler."""
        if self.sampler == "tpe":
            return optuna.samplers.TPESampler(
                n_startup_trials=self.sampler_params.get("n_startup_trials", 10),
                n_ei_candidates=self.sampler_params.get("n_ei_candidates", 24),
                seed=self.seed,
                multivariate=self.sampler_params.get("multivariate", True),
                group=self.sampler_params.get("group", True),
            )
        elif self.sampler == "cmaes":
            return optuna.samplers.CmaEsSampler(
                seed=self.seed,
                warn_independent_sampling=True,
            )
        elif self.sampler == "random":
            return optuna.samplers.RandomSampler(seed=self.seed)
        elif self.sampler == "nsga2":
            return optuna.samplers.NSGAIISampler(
                seed=self.seed,
                population_size=self.sampler_params.get("population_size", 50),
            )
        elif self.sampler == "nsga3":
            return optuna.samplers.NSGAIIISampler(
                seed=self.seed,
                population_size=self.sampler_params.get("population_size", 50),
                reference_points=self.sampler_params.get("reference_points", None),
            )
        elif self.sampler == "qmc":
            return optuna.samplers.QMCSampler(
                seed=self.seed,
                qmc_type=self.sampler_params.get("qmc_type", "sobol"),
            )
        else:
            return optuna.samplers.TPESampler(seed=self.seed)
    
    def _create_study(self, optuna):
        """Create or load Optuna study."""
        directions = [d.upper() for d in self.direction]
        
        study_kwargs = {
            "study_name": self.study_name,
            "sampler": self._get_sampler(optuna),
            "pruner": self.pruner.get_optuna_pruner(),
        }
        
        if self.storage:
            study_kwargs["storage"] = self.storage
            study_kwargs["load_if_exists"] = self.load_if_exists
        
        # Multi-objective vs single-objective
        if len(directions) > 1:
            study_kwargs["directions"] = directions
            return optuna.create_study(**study_kwargs)
        else:
            study_kwargs["direction"] = directions[0]
            return optuna.create_study(**study_kwargs)
    
    def _objective(self, trial, **context):
        """Objective function for Optuna."""
        import optuna
        
        start_time = time.time()
        
        # Sample parameters from search space
        params = {}
        for name, distribution in self.search_space.parameters.items():
            try:
                params[name] = distribution.to_optuna(trial)
            except AttributeError:
                # Fallback: use suggest methods directly
                if hasattr(distribution, 'choices'):
                    params[name] = trial.suggest_categorical(name, distribution.choices)
                elif hasattr(distribution, 'low'):
                    if hasattr(distribution, 'log_scale') and distribution.log_scale:
                        params[name] = trial.suggest_float(name, distribution.low, distribution.high, log=True)
                    elif isinstance(distribution.low, int) and isinstance(distribution.high, int):
                        params[name] = trial.suggest_int(name, distribution.low, distribution.high)
                    else:
                        params[name] = trial.suggest_float(name, distribution.low, distribution.high)
        
        # Run evaluation
        evaluator = self.evaluator_class(**self.evaluator_kwargs)
        metrics = evaluator.evaluate(params, trial, **context)
        
        # Record runtime
        runtime = time.time() - start_time
        trial.set_user_attr("runtime", runtime)
        
        # Store metadata about parameters
        for key, value in metrics.items():
            if not isinstance(value, (int, float)):
                trial.set_user_attr(f"{key}_str", str(value))
        
        # Return objective values
        if len(self.objective) == 1:
            return metrics.get(self.objective[0], float('-inf') if self.direction[0] == "maximize" else float('inf'))
        
        return tuple(metrics.get(obj, 0.0) for obj in self.objective)
    
    def execute(
        self,
        train_data: Any,
        val_data: Any,
        context: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Execute hyperparameter search."""
        try:
            import optuna
        except ImportError:
            raise PipelineError("Optuna is required for hyperparameter tuning. Install with: pip install optuna")
        
        # Set verbosity
        optuna.logging.set_verbosity(optuna.logging.INFO)
        
        # Create study
        self.study = self._create_study(optuna)
        
        # Create objective wrapper
        def objective(trial):
            return self._objective(trial, train_data=train_data, val_data=val_data, context=context)
        
        # Run optimization
        self.study.optimize(
            objective,
            n_trials=self.n_trials,
            timeout=self.timeout,
            n_jobs=self.n_jobs,
            show_progress_bar=self.show_progress_bar,
        )
        
        # Collect results
        self.trial_results = []
        for trial in self.study.trials:
            if trial.state != optuna.trial.TrialState.FAIL:
                result = TrialResult(
                    trial_id=trial.number,
                    params=trial.params,
                    value=trial.value if not isinstance(trial.value, tuple) else trial.value[0],
                    objective_values={
                        k: v for k, v in trial.params.items()
                    } if trial.params else {},
                    runtime=trial.user_attrs.get("runtime", 0),
                    state=trial.state.name,
                    user_attrs=dict(trial.user_attrs),
                    intermediate_values=list(trial.intermediate_values.values()),
                )
                self.trial_results.append(result)
        
        # Store best trial
        if self.study.best_trial:
            self.best_trial = TrialResult(
                trial_id=self.study.best_trial.number,
                params=self.study.best_trial.params,
                value=self.study.best_trial.value if not isinstance(self.study.best_trial.value, tuple) else self.study.best_trial.value[0],
                runtime=0,
                state="COMPLETE",
            )
        
        # Get importances if available
        importances = None
        if len(self.study.trials) > 10:
            try:
                importances = optuna.importance.get_param_importances(self.study)
            except Exception:
                pass
        
        # Prepare results
        results = {
            "study_name": self.study_name,
            "best_trial": {
                "trial_id": self.best_trial.trial_id if self.best_trial else None,
                "params": self.best_trial.params if self.best_trial else None,
                "value": self.best_trial.value if self.best_trial else None,
            },
            "study_statistics": {
                "n_total_trials": len(self.study.trials),
                "n_complete_trials": len([t for t in self.study.trials if t.state == optuna.trial.TrialState.COMPLETE]),
                "n_pruned_trials": len([t for t in self.study.trials if t.state == optuna.trial.TrialState.PRUNED]),
                "n_failed_trials": len([t for t in self.study.trials if t.state == optuna.trial.TrialState.FAIL]),
                "best_value": self.study.best_value if self.study.best_trial else None,
            },
            "trial_results": [
                {
                    "trial_id": r.trial_id,
                    "params": r.params,
                    "value": r.value,
                    "runtime": r.runtime,
                    "state": r.state,
                }
                for r in self.trial_results
            ],
            "parameter_importances": dict(importances) if importances else None,
            "search_space": {
                name: str(type(dist).__name__)
                for name, dist in self.search_space.parameters.items()
            },
        }
        
        if context:
            context["hyperparameter_tuning"] = results
        
        return results
    
    def get_best_params(self) -> Optional[Dict[str, Any]]:
        """Get the best hyperparameters found."""
        return self.best_trial.params if self.best_trial else None
    
    def get_trials_df(self) -> "pd.DataFrame":
        """Get all trials as a DataFrame."""
        try:
            import pandas as pd
        except ImportError:
            raise PipelineError("pandas required for DataFrame output")
        
        rows = []
        for result in self.trial_results:
            row = {
                "trial_id": result.trial_id,
                "value": result.value,
                "runtime": result.runtime,
                "state": result.state,
                **result.params,
            }
            rows.append(row)
        
        return pd.DataFrame(rows)
    
    def plot_optimization_history(self):
        """Plot optimization history using Optuna visualizations."""
        try:
            import optuna.visualization as vis
            return vis.plot_optimization_history(self.study)
        except ImportError:
            raise PipelineError("Optuna visualization requires plotly")
    
    def plot_parallel_coordinate(self):
        """Plot parallel coordinate visualization."""
        try:
            import optuna.visualization as vis
            return vis.plot_parallel_coordinate(self.study)
        except ImportError:
            raise PipelineError("Optuna visualization requires plotly")
    
    def plot_param_importances(self):
        """Plot parameter importances."""
        try:
            import optuna.visualization as vis
            return vis.plot_param_importances(self.study)
        except ImportError:
            raise PipelineError("Optuna visualization requires plotly")


def suggest_hyperparameters(
    trial: Any,
    search_space: SearchSpace,
) -> Dict[str, Any]:
    """Utility function to suggest hyperparameters from a search space.
    
    Args:
        trial: Optuna trial object
        search_space: Search space to sample from
        
    Returns:
        Dictionary of suggested parameters
    """
    return search_space.to_optuna(trial)
