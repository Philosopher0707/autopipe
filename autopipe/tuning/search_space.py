"""Search spaces for hyperparameter tuning."""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List


class SearchStrategy(Enum):
    """Search strategies for hyperparameter tuning."""

    BAYESIAN = "bayesian"
    RANDOM = "random"
    GRID = "grid"
    TPE = "tpe"
    CMAES = "cmaes"


@dataclass
class SearchParameter:
    """Base class for search parameters."""

    name: str
    param_type: str

    def to_dict(self) -> Dict:
        return {"name": self.name, "type": self.param_type}


@dataclass
class Continuous:
    """Continuous parameter with range."""

    name: str
    low: float
    high: float
    log_scale: bool = False

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "type": "continuous",
            "low": self.low,
            "high": self.high,
            "log_scale": self.log_scale,
        }


@dataclass
class Discrete:
    """Discrete parameter with range."""

    name: str
    low: int
    high: int

    def to_dict(self) -> Dict:
        return {"name": self.name, "type": "discrete", "low": self.low, "high": self.high}


@dataclass
class Categorical:
    """Categorical parameter with choices."""

    name: str
    choices: List[Any]

    def to_dict(self) -> Dict:
        return {"name": self.name, "type": "categorical", "choices": self.choices}


class SearchSpace:
    """Define search space for hyperparameter optimization."""

    def __init__(self):
        self.parameters: Dict[str, Any] = {}

    def add(self, param: Continuous | Discrete | Categorical):
        """Add a parameter to the search space."""
        self.parameters[param.name] = param

    def sample(self, strategy: SearchStrategy = SearchStrategy.RANDOM) -> Dict[str, Any]:
        """Sample a point from the search space."""
        import random

        sample = {}
        for name, param in self.parameters.items():
            if isinstance(param, Continuous):
                if param.log_scale:
                    import math

                    log_low = math.log(param.low)
                    log_high = math.log(param.high)
                    sample[name] = math.exp(random.uniform(log_low, log_high))
                else:
                    sample[name] = random.uniform(param.low, param.high)
            elif isinstance(param, Discrete):
                sample[name] = random.randint(param.low, param.high)
            elif isinstance(param, Categorical):
                sample[name] = random.choice(param.choices)
        return sample

    def to_dict(self) -> Dict:
        """Convert search space to dictionary."""
        return {name: param.to_dict() for name, param in self.parameters.items()}


# Convenient factory functions
def continuous(low: float, high: float, log_scale: bool = False) -> Continuous:
    """Create a continuous parameter."""
    return Continuous(name="", low=low, high=high, log_scale=log_scale)


def discrete(low: int, high: int) -> Discrete:
    """Create a discrete parameter."""
    return Discrete(name="", low=low, high=high)


def categorical(choices: List[Any]) -> Categorical:
    """Create a categorical parameter."""
    return Categorical(name="", choices=choices)
