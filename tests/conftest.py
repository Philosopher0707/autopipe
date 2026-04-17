"""Test fixtures and configuration."""
import pytest
from pathlib import Path


@pytest.fixture
def sample_pipeline_config():
    """Return a sample pipeline configuration dictionary."""
    return {
        "name": "test_pipeline",
        "steps": [
            {
                "name": "load_data",
                "type": "autopipe.core.steps.DataLoaderStep",
                "params": {"dataset": "iris"},
            },
            {
                "name": "preprocess",
                "type": "autopipe.core.steps.PrintStep",
                "depends_on": ["load_data"],
            },
        ],
    }


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Return a temporary cache directory."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return cache_dir


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singleton instances between tests."""
    from autopipe.credentials.manager import _credential_manager
    from autopipe.caching.manager import _cache_instance
    from autopipe.observability.metrics import _metrics_collector
    
    global _credential_manager, _cache_instance, _metrics_collector
    
    _credential_manager = None
    _cache_instance = None
    _metrics_collector = None
    yield
    _credential_manager = None
    _cache_instance = None
    _metrics_collector = None
