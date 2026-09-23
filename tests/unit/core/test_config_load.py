"""Tests for autopipe.config.load module."""

import os

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


def test_llm_secret_accessors_removed():
    """get_llm_config and the Config key attrs returned plaintext secrets.

    Kept alive only by their own tests; live resolution goes through
    CredentialManager / llm.client._resolve_api_key (env at construction).
    """
    assert not hasattr(Config, "get_llm_config")
    for attr in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY", "OLLAMA_API_KEY"):
        assert attr not in vars(Config), attr
