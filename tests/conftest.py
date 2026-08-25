"""Test fixtures and configuration."""

import pytest


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
    """Reset singleton module globals between tests."""
    import autopipe.caching.manager as cache_manager
    import autopipe.credentials.manager as credentials_manager
    import autopipe.observability.metrics as metrics_module

    def _reset():
        cache_manager._cache_instance = None
        credentials_manager._credential_manager = None
        metrics_module._metrics_collector = None

    _reset()
    yield
    _reset()
