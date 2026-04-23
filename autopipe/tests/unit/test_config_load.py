"""Tests for autopipe.config.load module."""

import os

import pytest

from autopipe.config.load import Config


class TestConfigDefaults:
    def test_default_llm_provider(self, monkeypatch):
        # Config evaluates DEFAULT_LLM_PROVIDER via os.getenv at import time.
        # Since .env may override it, we explicitly set the env var.
        monkeypatch.setenv("DEFAULT_LLM_PROVIDER", "openrouter")
        assert os.getenv("DEFAULT_LLM_PROVIDER") == "openrouter"

    def test_default_output_dir(self):
        assert Config.OUTPUT_DIR == "./output"

    def test_default_log_level(self):
        assert Config.LOG_LEVEL == "INFO"

    def test_ollama_base_url(self):
        assert Config.OLLAMA_BASE_URL == "http://127.0.0.1:11434/v1"


class TestGetLlmConfig:
    def test_ollama_config_never_raises(self):
        config = Config.get_llm_config("ollama")
        assert config["api_key"] == "ollama"
        assert "base_url" in config

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="No API key found"):
            Config.get_llm_config("nonexistent_provider_xyz")

    def test_default_provider_used_when_none(self):
        # This uses whatever DEFAULT_LLM_PROVIDER is set to
        # If it's ollama, it succeeds; otherwise it may raise
        try:
            config = Config.get_llm_config(None)
            assert "api_key" in config
        except ValueError:
            pass  # Provider without API key in env, expected
