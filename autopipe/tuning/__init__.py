"""AutoPipe Hyperparameter Tuning Module.

Optuna-backed hyperparameter optimization with declarative search spaces.
The former DistributedSearch/KubernetesDistributedSearch module was removed:
its Kubernetes result collection raised NotImplementedError and its Hyperband
formula was wrong — see ROADMAP P4.
"""

from .optuna_search import OptunaPruner, OptunaSearchStep, suggest_hyperparameters
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
    "OptunaPruner",
    "OptunaSearchStep",
    "SearchSpace",
    "SearchStrategy",
    "categorical",
    "continuous",
    "discrete",
    "suggest_hyperparameters",
]
