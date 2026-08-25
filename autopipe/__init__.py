"""AutoPipe: Automatic ML/DL pipeline framework with LLM integration."""

import sys
from typing import Any

__version__ = "0.1.0"

# Define __all__ for public API (sorted; resolved lazily via __getattr__)
__all__ = [
    "AnthropicClient",
    "ChartGenerator",
    "Config",
    "DataLoaderStep",
    "DataPreprocessorStep",
    "DataSplitterStep",
    "DataValidatorStep",
    "DriftDetectionStep",
    "EvaluationResult",
    "ExplainabilityStep",
    "FeatureEngineeringStep",
    "FeatureSelectionStep",
    "LLMClient",
    "LLMFactory",
    "ModelEvaluatorStep",
    "ModelRegistry",
    "OllamaClient",
    "OpenAIClient",
    "OpenRouterClient",
    "Pipeline",
    "PyTorchTrainerStep",
    "SearchStrategy",
    "SklearnTrainerStep",
    "Step",
    "TensorFlowTrainerStep",
    "TrainingConfig",
    "TransferLearningStep",
    "categorical",
    "continuous",
    "discrete",
    "get_registry",
    "run",
]


def __getattr__(name: str) -> Any:
    """Lazy import of submodules."""
    # Core
    if name == "Pipeline":
        from .core import Pipeline

        return Pipeline
    elif name == "Step":
        from .core import Step

        return Step

    # Data processing
    elif name in [
        "DataLoaderStep",
        "DataValidatorStep",
        "DataPreprocessorStep",
        "FeatureSelectionStep",
        "FeatureEngineeringStep",
    ]:
        from .core import steps as _core_steps
        from .steps import data as _steps_data

        module = _core_steps if name == "FeatureEngineeringStep" else _steps_data
        return getattr(module, name)
    elif name == "DataSplitterStep":
        from .steps.cross_validation import DataSplitterStep

        return DataSplitterStep

    # Training
    elif name in [
        "SklearnTrainerStep",
        "PyTorchTrainerStep",
        "TensorFlowTrainerStep",
        "TransferLearningStep",
        "TrainingConfig",
    ]:
        from .steps.deep_learning import (
            PyTorchTrainerStep,
            TensorFlowTrainerStep,
            TransferLearningStep,
        )
        from .steps.training import SklearnTrainerStep, TrainingConfig

        module_map = {
            "SklearnTrainerStep": sys.modules["autopipe.steps.training"],
            "PyTorchTrainerStep": sys.modules["autopipe.steps.deep_learning"],
            "TensorFlowTrainerStep": sys.modules["autopipe.steps.deep_learning"],
            "TransferLearningStep": sys.modules["autopipe.steps.deep_learning"],
            "TrainingConfig": sys.modules["autopipe.steps.training"],
        }
        return getattr(module_map[name], name)

    # Evaluation
    elif name in [
        "ModelEvaluatorStep",
        "ExplainabilityStep",
        "DriftDetectionStep",
        "EvaluationResult",
    ]:
        from .steps.evaluation import (
            DriftDetectionStep,
            EvaluationResult,
            ExplainabilityStep,
            ModelEvaluatorStep,
        )

        module = sys.modules["autopipe.steps.evaluation"]
        return getattr(module, name)

    # Hyperparameter tuning
    elif name in ["SearchStrategy", "continuous", "discrete", "categorical"]:
        from . import tuning as _tuning

        return getattr(_tuning, name)

    # Model registry
    elif name == "get_registry":
        from .registry import get_registry

        return get_registry
    elif name == "ModelRegistry":
        from .registry import ModelRegistry

        return ModelRegistry

    # Visualization
    elif name == "ChartGenerator":
        from .visualization import ChartGenerator

        return ChartGenerator

    # LLM
    elif name == "LLMClient":
        from .llm import LLMClient

        return LLMClient
    elif name == "OpenAIClient":
        from .llm import OpenAIClient

        return OpenAIClient
    elif name == "AnthropicClient":
        from .llm import AnthropicClient

        return AnthropicClient
    elif name == "OpenRouterClient":
        from .llm import OpenRouterClient

        return OpenRouterClient
    elif name == "OllamaClient":
        from .llm import OllamaClient

        return OllamaClient
    elif name == "LLMFactory":
        from .llm import LLMFactory

        return LLMFactory

    # Utilities
    elif name == "Config":
        from .config import Config

        return Config
    elif name == "run":
        from .core.runner import run

        return run
    else:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# Direct imports for static analyzers (Python 3.7+)
if sys.version_info >= (3, 7):
    try:
        from .config import Config as _Config
        from .core import Pipeline as _Pipeline
        from .core import Step as _Step
        from .core.runner import run as _run
        from .llm import LLMClient as _LLMClient
        from .llm import LLMFactory as _LLMFactory
        from .visualization import ChartGenerator as _ChartGenerator

        Pipeline = _Pipeline
        Step = _Step
        ChartGenerator = _ChartGenerator
        LLMClient = _LLMClient
        LLMFactory = _LLMFactory
        Config = _Config
        run = _run

        del _Pipeline, _Step, _ChartGenerator, _LLMClient, _LLMFactory, _Config, _run
    except ImportError:
        pass
