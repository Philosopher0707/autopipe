"""Load pipeline configuration from YAML."""
import importlib
import logging
from typing import Dict, Any
from .pipeline import Pipeline
from .step import Step

logger = logging.getLogger(__name__)

def import_class(class_path: str):
    """Import a class from a dotted path."""
    module_name, class_name = class_path.rsplit('.', 1)
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as e:
        raise ValueError(f"Failed to import module '{module_name}': {e}") from e
    try:
        return getattr(module, class_name)
    except AttributeError as e:
        raise ValueError(f"Class '{class_name}' not found in module '{module_name}'") from e

def load_step_from_config(step_config: Dict[str, Any]) -> Step:
    """Create a Step instance from a config dictionary.
    
    Config format:
        name: step_name
        type: dotted.path.to.StepClass  or builtin alias
        params: { ... }  # passed to constructor
        depends_on: [list of step names]
    """
    name = step_config["name"]
    step_type = step_config.get("type", "autopipe.core.steps.PrintStep")
    params = step_config.get("params", {})
    depends_on = step_config.get("depends_on", [])
    
    # Built-in aliases for convenience
    builtin_map = {
        "print": "autopipe.core.steps.PrintStep",
        "llm": "autopipe.core.steps.LLMStep",
        "data_loader": "autopipe.steps.data.DataLoaderStep",
        "visualization": "autopipe.core.steps.VisualizationStep",
        "feature_engineering": "autopipe.core.steps.FeatureEngineeringStep",
        "fe": "autopipe.core.steps.FeatureEngineeringStep",
    }
    if step_type in builtin_map:
        step_type = builtin_map[step_type]
    
    # Import the class
    cls = import_class(step_type)
    
    # Instantiate with params
    try:
        step = cls(name=name, depends_on=depends_on, **params)
    except TypeError as e:
        raise ValueError(f"Failed to instantiate {step_type} with params {params}: {e}")
    
    return step

def load_pipeline_from_config(config: Dict[str, Any]) -> Pipeline:
    """Create a Pipeline from a config dictionary."""
    pipeline_name = config.get("name", "default_pipeline")
    pipeline = Pipeline(pipeline_name)
    
    steps = config.get("steps", [])
    for step_config in steps:
        step = load_step_from_config(step_config)
        pipeline.add_step(step)
    
    return pipeline