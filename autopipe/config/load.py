"""Configuration and environment loading."""

import os
from typing import Any, Dict

from dotenv import load_dotenv

load_dotenv()  # load from .env file


class Config:
    """Central configuration."""

    # LLM API keys
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
    OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "ollama")

    # LLM Base URLs
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1")

    # Default provider and model
    DEFAULT_LLM_PROVIDER = os.getenv("DEFAULT_LLM_PROVIDER", "openrouter")
    DEFAULT_LLM_MODEL = os.getenv("DEFAULT_LLM_MODEL", "google/gemma-4-26b-a4b-it:free")
    OLLAMA_DEFAULT_MODEL = os.getenv("OLLAMA_DEFAULT_MODEL", "llama3.1")

    # Pipeline defaults
    OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./output")
    FIGURES_DIR = os.getenv("FIGURES_DIR", "./figures")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    @classmethod
    def get_llm_config(cls, provider: str = None) -> Dict[str, Any]:
        """Get configuration for a given provider."""
        provider = provider or cls.DEFAULT_LLM_PROVIDER
        key_map = {
            "openai": cls.OPENAI_API_KEY,
            "anthropic": cls.ANTHROPIC_API_KEY,
            "openrouter": cls.OPENROUTER_API_KEY,
            "ollama": cls.OLLAMA_API_KEY,
        }
        base_url_map = {
            "ollama": cls.OLLAMA_BASE_URL,
        }

        api_key = key_map.get(provider)
        base_url = base_url_map.get(provider)

        if provider == "ollama":
            # Ollama doesn't strictly require API key for local
            return {
                "api_key": api_key or "ollama",
                "base_url": base_url,
                "model": cls.OLLAMA_DEFAULT_MODEL,
            }

        if not api_key:
            raise ValueError(f"No API key found for provider {provider}")

        return {
            "api_key": api_key,
            "model": cls.DEFAULT_LLM_MODEL,
        }
