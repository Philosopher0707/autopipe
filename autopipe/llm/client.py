"""LLM client supporting multiple providers."""
import os
import json
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
import logging
import requests

logger = logging.getLogger(__name__)


class LLMClient(ABC):
    """Abstract LLM client."""
    
    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """Generate text from prompt."""
        pass
    
    @abstractmethod
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Chat completion."""
        pass


class OllamaClient(LLMClient):
    """Ollama API client (OpenAI-compatible).
    
    Supports local Ollama server and Ollama Cloud.
    Uses OpenAI-compatible API with custom base URL.
    """
    
    def __init__(
        self, 
        api_key: Optional[str] = None, 
        model: str = "llama3.1",
        base_url: Optional[str] = None
    ):
        self.api_key = api_key or os.getenv("OLLAMA_API_KEY", "ollama")
        self.model = model
        # Default to local Ollama; should end with /v1 for OpenAI compatibility
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1")
        
        # Ensure base_url ends with /v1 (not /v1/chat/completions)
        if self.base_url.endswith("/v1/chat/completions"):
            self.base_url = self.base_url.replace("/v1/chat/completions", "/v1")
        elif not self.base_url.endswith("/v1"):
            self.base_url = self.base_url.rstrip("/") + "/v1"
        
        # Verify Ollama is reachable
        self._verify_connection()
    
    def _verify_connection(self) -> None:
        """Verify Ollama server is reachable."""
        try:
            # Check if Ollama is running by fetching models
            response = requests.get(
                f"{self.base_url}/models",
                headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {},
                timeout=5
            )
            if response.status_code == 404:
                # Alternative health check for some Ollama versions
                base = self.base_url.replace("/v1", "")
                requests.get(f"{base}/api/tags", timeout=5)
        except requests.exceptions.ConnectionError:
            logger.warning(
                f"Could not connect to Ollama at {self.base_url}. "
                "Ensure Ollama is running: ollama serve"
            )
        except Exception as e:
            logger.debug(f"Ollama connection check failed: {e}")
    
    def _get_available_models(self) -> List[str]:
        """Get list of available models from Ollama."""
        try:
            # Try OpenAI-compatible endpoint first
            response = requests.get(
                f"{self.base_url}/models",
                headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {},
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                return [m.get("id", m.get("name")) for m in data.get("data", [])]
        except Exception:
            pass
        
        # Fallback to native Ollama API
        try:
            base = self.base_url.replace("/v1", "")
            response = requests.get(f"{base}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get("models", [])
                return [m.get("name") for m in models]
        except Exception:
            pass
        
        return []
        
    def generate(self, prompt: str, **kwargs) -> str:
        """Generate text using chat completions endpoint."""
        messages = [{"role": "user", "content": prompt}]
        return self.chat(messages, **kwargs)
    
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Chat completion using OpenAI-compatible endpoint."""
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        data = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            **kwargs
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=data,
                timeout=kwargs.get("timeout", 120)
            )
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except requests.exceptions.ConnectionError as e:
            raise ValueError(
                f"Cannot connect to Ollama at {self.base_url}. "
                "Is Ollama running? Run: ollama serve"
            ) from e
        except requests.exceptions.HTTPError as e:
            if response.status_code == 404:
                # Model not found
                available = self._get_available_models()
                if available:
                    raise ValueError(
                        f"Model '{self.model}' not found. "
                        f"Available models: {', '.join(available[:5])}..."
                    ) from e
                else:
                    raise ValueError(
                        f"Model '{self.model}' not found. "
                        "Run 'ollama pull <model>' to download."
                    ) from e
            raise


class OpenAIClient(LLMClient):
    """OpenAI API client."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not set in environment")
        self.model = model
        self.base_url = "https://api.openai.com/v1"
        
    def generate(self, prompt: str, **kwargs) -> str:
        """Generate using completions endpoint."""
        # Use chat completion for newer models
        messages = [{"role": "user", "content": prompt}]
        return self.chat(messages, **kwargs)
    
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Chat completion."""
        import openai
        openai.api_key = self.api_key
        response = openai.chat.completions.create(
            model=self.model,
            messages=messages,
            **kwargs
        )
        return response.choices[0].message.content


class AnthropicClient(LLMClient):
    """Anthropic Claude API client."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "claude-3-5-sonnet-20241022"):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set in environment")
        self.model = model
        
    def generate(self, prompt: str, **kwargs) -> str:
        """Generate using messages endpoint."""
        messages = [{"role": "user", "content": prompt}]
        return self.chat(messages, **kwargs)
    
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Anthropic messages API."""
        import anthropic
        client = anthropic.Anthropic(api_key=self.api_key)
        response = client.messages.create(
            model=self.model,
            messages=messages,
            **kwargs
        )
        return response.content[0].text


class OpenRouterClient(LLMClient):
    """OpenRouter API client."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "google/gemma-4-26b-a4b-it:free"):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not set in environment")
        self.model = model
        self.base_url = "https://openrouter.ai/api/v1"
        
    def generate(self, prompt: str, **kwargs) -> str:
        """Generate using completions endpoint."""
        messages = [{"role": "user", "content": prompt}]
        return self.chat(messages, **kwargs)
    
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """OpenRouter chat completion."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/autopipe",
            "X-Title": "AutoPipe"
        }
        data = {
            "model": self.model,
            "messages": messages,
            **kwargs
        }
        response = requests.post(f"{self.base_url}/chat/completions", headers=headers, json=data)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]


class LLMFactory:
    """Factory to create LLM clients based on provider."""
    
    # Auto-detect Ollama models by name pattern
    OLLAMA_MODEL_PATTERNS = [
        "llama", "mistral", "codellama", "deepseek", 
        "phi", "gemma", "qwen", "mixtral", "neural-chat",
        "nous-hermes", "wizard", "dolphin", "yi", "falcon"
    ]
    
    @staticmethod
    def create_client(provider: str, **kwargs) -> LLMClient:
        """Create an LLM client.
        
        Args:
            provider: One of 'openai', 'anthropic', 'openrouter', 'ollama'.
            **kwargs: Passed to client constructor.
            
        Returns:
            LLMClient instance.
        """
        provider = provider.lower()
        if provider == "openai":
            return OpenAIClient(**kwargs)
        elif provider == "anthropic":
            return AnthropicClient(**kwargs)
        elif provider == "openrouter":
            return OpenRouterClient(**kwargs)
        elif provider == "ollama":
            return OllamaClient(**kwargs)
        else:
            raise ValueError(f"Unsupported provider: {provider}")
    
    @classmethod
    def detect_provider(cls, model_name: Optional[str] = None) -> str:
        """Auto-detect provider based on model name or environment.
        
        Args:
            model_name: Optional model name to check patterns against.
            
        Returns:
            Provider name string.
        """
        # Check for explicit Ollama environment
        if os.getenv("OLLAMA_BASE_URL"):
            return "ollama"
        
        # Check model name patterns
        if model_name:
            model_lower = model_name.lower()
            if model_lower.startswith("ollama/"):
                return "ollama"
            for pattern in cls.OLLAMA_MODEL_PATTERNS:
                if model_lower.startswith(pattern):
                    return "ollama"
        
        # Check for other provider API keys
        if os.getenv("OPENAI_API_KEY"):
            return "openai"
        if os.getenv("ANTHROPIC_API_KEY"):
            return "anthropic"
        if os.getenv("OPENROUTER_API_KEY"):
            return "openrouter"
        
        # Default to Ollama if available
        return "ollama"