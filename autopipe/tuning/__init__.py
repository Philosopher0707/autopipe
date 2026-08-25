"""AutoPipe Hyperparameter Tuning Module.

World-class hyperparameter optimization for ML/DL experiments.
Supports Optuna, Ray Tune, and custom search algorithms.
"""

from .distributed import DistributedSearch, ParallelSearch
from .optuna_search import OptunaPruner, OptunaSearchStep, suggest_hyperparameters
from .scheduler import EarlyStoppingCallback, ResourceScheduler
from .search_space import (
    Categorical,
    Continuous,
    Discrete,
    SearchSpace,
    SearchStrategy,
    categorical,
    continuous,
    discrete,
)

__all__ = [
    "Categorical",
    "Continuous",
    "Discrete",
    "DistributedSearch",
    "EarlyStoppingCallback",
    "OptunaPruner",
    "OptunaSearchStep",
    "ParallelSearch",
    "ResourceScheduler",
    "SearchSpace",
    "SearchStrategy",
    "categorical",
    "continuous",
    "discrete",
    "suggest_hyperparameters",
]
