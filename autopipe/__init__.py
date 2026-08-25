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
    "HyperparameterTuner",
    "LLMClient",
    "LLMFactory",
    "LocalModelRegistry",
    "ModelEvaluatorStep",
    "OllamaClient",
    "OpenAIClient",
    "OpenRouterClient",
    "PiCodingResult",
    "PiCodingStep",
    "PiToolCall",
    "PiTurn",
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
        from .core.steps import FeatureEngineeringStep
        from .steps.data import (
            DataLoaderStep,
            DataPreprocessorStep,
            DataValidatorStep,
            FeatureSelectionStep,
        )

        module = sys.modules["autopipe.steps.data"]
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
    elif name in ["HyperparameterTuner", "SearchStrategy", "continuous", "discrete", "categorical"]:
        from .tuning import HyperparameterTuner, SearchStrategy, categorical, continuous, discrete

        module = sys.modules["autopipe.tuning"]
        return getattr(module, name)

    # Model registry
    elif name == "get_registry":
        from .registry import get_registry

        return get_registry
    elif name == "LocalModelRegistry":
        from .registry import LocalModelRegistry

        return LocalModelRegistry

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

    # Pi coding
    elif name == "PiCodingStep":
        from .steps.pi_coding import PiCodingStep

        return PiCodingStep
    elif name in ["PiCodingResult", "PiToolCall", "PiTurn"]:
        from .steps.pi_coding_models import PiCodingResult, PiToolCall, PiTurn

        module = sys.modules["autopipe.steps.pi_coding_models"]
        return getattr(module, name)

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
        from .steps.pi_coding import PiCodingStep as _PiCodingStep
        from .steps.pi_coding_models import PiCodingResult as _PiCodingResult
        from .steps.pi_coding_models import PiToolCall as _PiToolCall
        from .steps.pi_coding_models import PiTurn as _PiTurn
        from .visualization import ChartGenerator as _ChartGenerator

        Pipeline = _Pipeline
        Step = _Step
        ChartGenerator = _ChartGenerator
        LLMClient = _LLMClient
        LLMFactory = _LLMFactory
        PiCodingStep = _PiCodingStep
        PiCodingResult = _PiCodingResult
        PiToolCall = _PiToolCall
        PiTurn = _PiTurn
        Config = _Config
        run = _run

        del _Pipeline, _Step, _ChartGenerator, _LLMClient, _LLMFactory, _Config, _run
    except ImportError:
        pass
