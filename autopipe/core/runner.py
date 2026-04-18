"""Pipeline runner."""
import importlib.util
import sys
import os
from typing import Any, Dict
from .pipeline import Pipeline
import logging

logger = logging.getLogger(__name__)

def run_pipeline(pipeline: Pipeline, initial_inputs: Dict[str, Any] = None) -> Dict[str, Any]:
    """Run a pipeline and return outputs."""
    return pipeline.run(initial_inputs)


def load_pipeline_from_module(filepath: str) -> Pipeline:
    """Load a pipeline defined in a Python module.
    
    The module should define a variable `pipeline` that is an instance of Pipeline.
    """
    spec = importlib.util.spec_from_file_location("pipeline_module", filepath)
    if spec is None:
        raise ValueError(f"Could not load module from {filepath}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except FileNotFoundError:
        raise ValueError(f"File not found: {filepath}")
    
    if not hasattr(module, "pipeline"):
        raise AttributeError("Module must define a 'pipeline' variable")
    
    pipeline = module.pipeline
    if not isinstance(pipeline, Pipeline):
        raise TypeError("'pipeline' must be an instance of Pipeline")
    
    return pipeline


def load_pipeline_from_yaml(filepath: str) -> Pipeline:
    """Load pipeline configuration from YAML."""
    import yaml
    from .loader import load_pipeline_from_config
    with open(filepath, 'r') as f:
        config = yaml.safe_load(f)
    
    return load_pipeline_from_config(config)


def run(filepath: str, initial_inputs: Dict[str, Any] = None) -> Dict[str, Any]:
    """Run a pipeline from a file.
    
    Supports .py (module) and .yaml/.yml (YAML config).
    """
    if filepath.endswith('.py'):
        pipeline = load_pipeline_from_module(filepath)
    elif filepath.endswith('.yaml') or filepath.endswith('.yml'):
        pipeline = load_pipeline_from_yaml(filepath)
    else:
        raise ValueError("Unsupported file format. Use .py or .yaml")
    
    return run_pipeline(pipeline, initial_inputs)