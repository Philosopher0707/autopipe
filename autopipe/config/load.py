"""Configuration and environment loading."""

import os

from dotenv import load_dotenv

load_dotenv()  # load from .env file


class Config:
    """Central configuration."""

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
